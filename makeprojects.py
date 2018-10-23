#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Create projects from a json description file
# for XCode, Visual Studio, CodeBlocks and
# other IDEs
#
# Copyright Rebecca Ann Heineman
#
# This source is free for anyone's use
# on the condition that Rebecca's credit is acknowledged
#

import os
import json
import glob
import shutil
import sys
import platform
import argparse
import uuid
import hashlib
import subprocess

#
# Class description for a solution file to create
#

class SolutionData:
	workingDir = None
	kind = 'tool'
	projectname = 'project'
	ide = 'vs2010'
	platform = 'windows'
	configurations = ['Debug','Internal','Release']
	finalfolder = None
	exclude = []
	defines = []
	sourcefolders = ['.']
	includefolders = []
		
#
# When scanning for files, return each entry here
#

class SourceFile:
	# File base name with extension
	filename = ''
	# Directory the file is found in
	directory = ''
	# File type h,hpp,c,cpp,text.xcconfig,lib
	type = 'cpp'
	# Filename UUID used by XCode
	uuid = ''
	# Filetype UUID used by XCode
	typeuuid = ''

#
# Node class for creating directory trees
# Needed for some projects that have to store
# file entries in nested trees
#

class node(object):
	def __init__(self, value, children = []):
		self.value = value
		self.children = children
	def __repr__(self, level=0):
		ret = "\t"*level+repr(self.value)+"\n"
		for child in self.children:
			ret += child.__repr__(level+1)
		return ret

#
# Acceptable input files and which buckets they fall into
#

codeExtensions = [
	['.c','cpp'],
	['.cpp','cpp'],
	['.hpp','h'],
	['.h','h'],
	['.hh','h'],
	['.i','h'],
	['.inc','h'],
	['.rc','windowsresource'],
	['.r','macresource'],
	['.rsrc','macresource'],
	['.hlsl','hlsl']
	]

#
# Given a pathname, detect if the folder exists
# If not, create it
#

def createfolderifneeded(foldername):
	if not os.path.isdir(foldername):
		os.makedirs(foldername)
		
#
# Convert a string to a string array
#

def converttoarray(input):
	# If empty, return an empty array
	if input==None:
		input = []
	elif not type(input) is list:
		# Convert a single entry into an array
		input = [input]
	return input

#
# Convert a filename from linux/mac to windows format
#

def converttowindowsslashes(input):
	return input.replace('/','\\')
	
#
# Convert a filename from windows to linux/mac format
#

def converttolinuxslashes(input):
	return input.replace('\\','/')

#
# Convert a filename from linux/mac to windows format
# and ensure the last character is a slash
# This is needed for visual studio projects
#

def converttowindowsslasheswithendslash(input):
	input = converttowindowsslashes(input)
	if not input.endswith('\\'):
		input.append('\\')
	return input
		
#
# Create the ide code from the ide type
#

def getidecode(solution):
	idecode = None
	if solution.ide=='xcode3':
		idecode = 'xc3'
	elif solution.ide=='xcode4':
		idecode = 'xc4'
	elif solution.ide=='xcode5':
		idecode = 'xc5'
	elif solution.ide=='vs2003':
		idecode = 'vc7'
	elif solution.ide=='vs2005':
		idecode = 'vc8'
	elif solution.ide=='vs2008':
		idecode = 'vc9'
	elif solution.ide=='vs2010':
		idecode = 'v10'
	elif solution.ide=='vs2012':
		idecode = 'v11'
	elif solution.ide=='codeblocks':
		idecode = 'cdb'
	elif solution.ide=='watcom':
		idecode = 'wat'
	elif solution.ide=='codewarrior' and solution.platform=='windows':
		idecode = 'cw9'
	elif solution.ide=='codewarrior' and solution.platform=='mac':
		idecode = 'c10'
	return idecode

#
# Create the platform code from the platform type
#

def getplatformcode(platform):
	platformcode = None
	if platform=='windows':
		platformcode = 'win'
	elif platform=='macosx':
		platformcode = 'osx'
	elif platform=='linux':
		platformcode = 'lnx'
	elif platform=='ps3':
		platformcode = 'ps3'
	elif platform=='ps4':
		platformcode = 'ps4'
	elif platform=='xbox':
		platformcode = 'xbx'
	elif platform=='xbox360':
		platformcode = 'x36'
	elif platform=='xboxone':
		platformcode = 'one'
	elif platform=='shield':
		platformcode = 'shi'
	elif platform=='ios':
		platformcode = 'ios'
	elif platform=='mac':
		platformcode = 'mac'
	elif platform=='msdos':
		platformcode = 'dos'
	elif platform=='beos':
		platformcode = 'bos'
	elif platform=='ouya':
		platformcode = 'oya'
	return platformcode

#
# Create the platform codes from the platform type for Visual Studio
#

def getvsplatform(platform):
	platforms = None
	if platform=='windows':
		platforms = ['Win32','x64']
	elif platform=='ps3':
		platforms = ['PS3']
	elif platform=='ps4':
		platforms = ['ORBIS']
	elif platform=='xbox':
		platforms = ['Xbox']
	elif platform=='xbox360':
		platforms = ['Xbox 360']
	elif platform=='xboxone':
		platforms = ['Xbox ONE']
	elif platform=='shield':
		platforms = ['Tegra-Android']
	elif platform=='android':
		platforms = ['Android']
	return platforms
	
#
# Create the platform codes from the platform type for Visual Studio
#

def getconfigurationcode(configuration):
	code = 'unk'
	if configuration=='Debug':
		code = 'dbg'
	elif configuration=='Release':
		code = 'rel'
	elif configuration=='Internal':
		code = 'int'
	elif configuration=='Profile':
		code = 'pro'
	return code

#
# Given a base directory and a relative directory
# for all the files that are to be included in the project
#

def scandirectory(solution,directory,codefiles):

	#
	# Is this a valid directory?
	#
	searchDir = os.path.join(solution.workingDir,directory)
	if os.path.isdir(searchDir):

		#
		# Scan the directory
		#

		nameList = os.listdir(searchDir)
		for baseName in nameList:

			#
			# Is this file in the exclusion list?
			#

			testName = baseName.lower()
			skip = False
			for exclude in solution.exclude:
				if testName==exclude.lower():
					skip = True
					break

			if skip==True:
				continue

			#
			# Is it a file? (Skip links and folders)
			#
			
			fileName = os.path.join(searchDir,baseName)
			if os.path.isfile(fileName):
				
				#
				# Check against the extension list (Skip if not on the list)
				#
				
				for extension in codeExtensions:
					if testName.endswith(extension[0]):
						#
						# If the directory is the root, then don't prepend a directory
						#
						if directory=='.':
							addedname = baseName
						else:
							addedname = directory + os.sep + baseName
						
						#
						# Create a new entry
						#
						fileentry = SourceFile()
						fileentry.filename = addedname
						fileentry.directory = searchDir
						fileentry.type = extension[1]
						codefiles.append(fileentry)
						break
					
	return codefiles

#
# Obtain the list of source files
#

def getfilelist(solution):

	#
	# Get the files in the directory list
	#
	
	codefiles = []
	includedirectories = []
	for sourcefolder in solution.sourcefolders:
	
		#
		# Scan the folder for files
		#
		
		oldcount = len(codefiles)
		codefiles = scandirectory(solution,sourcefolder,codefiles)
		# If new files were found, add this directory to the included folders list
		if len(codefiles)!=oldcount:
			includedirectories.append(sourcefolder)

	codefiles = sorted(codefiles,cmp=lambda x,y: cmp(converttowindowsslashes(x.filename),converttowindowsslashes(y.filename)))
	return codefiles,includedirectories

#
# Prune the file list for a specific type
#

def pickfromfilelist(codefiles,type):
	filelist = []
	for codefile in codefiles:
		if codefile.type == type:
			filelist.append(codefile)
	return filelist

#
# Given a filename with a directory, extract the filename, leaving only the directory
#

def extractgroupname(name):
	index = name.rfind('\\')
	if index==-1:
		index = name.rfind('/')
		if index==-1:
			return ''

	#
	# Remove the filename
	#
	newname = name[0:index]
	
	#
	# If there are ..\ at the beginning, remove them
	#
	
	while newname.startswith('..\\') or newname.startswith('../'):
		newname = newname[3:len(newname)]
	
	#
	# If there is a .\, remove the single prefix
	#
	
	if newname.startswith('.\\') or newname.startswith('./'):
		newname = newname[2:len(newname)]

	return newname
	
	
###################################
#                                 #
# Visual Studio 2003-2013 support #
#                                 #
###################################

#
# Create Visual Studio .sln file for Visual Studio 2003-2013
#

def createslnfile(solution):
	
	#
	# First, create the specific year and version codes needed
	#
	
	if solution.ide=='vs2003':
		formatversion = '8.00'
		yearversion = '2003'
		projectsuffix = '.vcproj'
	elif solution.ide=='vs2005':
		formatversion = '9.00'
		yearversion = '2005'
		projectsuffix = '.vcproj'
	elif solution.ide=='vs2008':
		formatversion = '10.00'
		yearversion = '2008'
		projectsuffix = '.vcproj'
	elif solution.ide=='vs2010':
		formatversion = '11.00'
		yearversion = '2010'
		projectsuffix = '.vcxproj'
	elif solution.ide=='vs2012':
		formatversion = '12.00'
		yearversion = '2012'
		projectsuffix = '.vcxproj'
	elif solution.ide=='vs2013':
		formatversion = '12.00'
		yearversion = '2013'
		projectsuffix = '.vcxproj'
	else:
		# Not supported yet
		return 10,None
	
	#
	# Determine the filename (Sans extension)
	#
	
	idecode = getidecode(solution)
	platformcode = getplatformcode(solution.platform)
	projectfilename = str(solution.projectname + idecode + platformcode)
	solutionuuid = str(uuid.uuid3(uuid.NAMESPACE_DNS,str(projectfilename))).upper()
	
	#
	# Let's create the solution file!
	#
	
	solutionpathname = os.path.join(solution.workingDir,projectfilename + '.sln')
	
	#
	# Start writing the project file
	#
	fp = open(solutionpathname,'w')
	
	#
	# Save off the UTF-8 header marker
	#
	fp.write('\xef\xbb\xbf\n')
	
	#
	# Save off the format header
	#
	fp.write('Microsoft Visual Studio Solution File, Format Version ' + formatversion + '\n')
	fp.write('# Visual Studio ' + yearversion + '\n')

	fp.write('Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "' + solution.projectname + '", "' + projectfilename + projectsuffix + '", "{' + solutionuuid + '}"\n')
	fp.write('EndProject\n')
	
	fp.write('Global\n')

	#
	# Write out the SolutionConfigurationPlatforms
	#
	
	vsplatforms = getvsplatform(solution.platform)
	fp.write('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n')
	for target in solution.configurations:
		for vsplatform in vsplatforms:
			token = target + '|' + vsplatform
			fp.write('\t\t' + token + ' = ' + token + '\n')
	fp.write('\tEndGlobalSection\n')

	#
	# Write out the ProjectConfigurationPlatforms
	#
	
	fp.write('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n')
	for target in solution.configurations:
		for vsplatform in vsplatforms:
			token = target + '|' + vsplatform
			fp.write('\t\t{' + solutionuuid + '}.' + token + '.ActiveCfg = ' + token + '\n')
			fp.write('\t\t{' + solutionuuid + '}.' + token + '.Build.0 = ' + token + '\n')
	fp.write('\tEndGlobalSection\n')

	
	#
	# Hide nodes section
	#
	
	fp.write('\tGlobalSection(SolutionProperties) = preSolution\n')
	fp.write('\t\tHideSolutionNode = FALSE\n')
	fp.write('\tEndGlobalSection\n')
	
	#
	# Close it up!
	#
	
	fp.write('EndGlobal\n')	
	fp.close()
	return 0,projectfilename
	
#
# Dump out a recursive tree of files to reconstruct a
# directory hiearchy for a file list
#
# Used by Visual Studio 2003, 2005 and 2008
#

def dumptreevs2005(indent,string,entry,fp,groups):
	for item in entry:
		if item!='':
			fp.write('\t'*indent + '<Filter Name="' + item + '">\n')
		if string=='':
			merged = item
		else:
			merged = string + '\\' + item
		if merged in groups:
			if item!='':
				tabs = '\t'*(indent+1)
			else:
				tabs = '\t'*indent
			sortlist = sorted(groups[merged],cmp=lambda x,y: cmp(x,y))
			for file in sortlist:
				fp.write(tabs + '<File RelativePath="' + file + '" />\n')					
		key = entry[item]
		# Recurse down the tree
		if type(key) is dict:
			dumptreevs2005(indent+1,merged,key,fp,groups)
		if item!='':
			fp.write('\t'*indent + '</Filter>\n')
	
#
# Create the solution and project file for visual studio 2005
#

def createvs2005solution(solution):
	error,projectfilename = createslnfile(solution)
	if error!=0:
		return error
		
	#
	# Now, let's create the project file
	#
	
	codefiles,includedirectories = getfilelist(solution)
	platformcode = getplatformcode(solution.platform)
	solutionuuid = str(uuid.uuid3(uuid.NAMESPACE_DNS,str(projectfilename))).upper()
	projectpathname = os.path.join(solution.workingDir,projectfilename + '.vcproj')
	fp = open(projectpathname,'w')
	
	#
	# Save off the xml header
	#
	
	fp.write('<?xml version="1.0" encoding="utf-8"?>\n')
	fp.write('<VisualStudioProject\n')
	fp.write('\tProjectType="Visual C++"\n')
	fp.write('\tVersion="8.00"\n')
	fp.write('\tName="' + solution.projectname + '"\n')
	fp.write('\tProjectGUID="{' + solutionuuid + '}"\n')
	fp.write('\t>\n')

	#
	# Write the project platforms
	#

	fp.write('\t<Platforms>\n')
	for vsplatform in getvsplatform(solution.platform):
		fp.write('\t\t<Platform Name="' + vsplatform + '" />\n')
	fp.write('\t</Platforms>\n')

	#
	# Write the project configurations
	#
	
	fp.write('\t<Configurations>\n')
	for target in solution.configurations:
		for vsplatform in getvsplatform(solution.platform):
			token = target + '|' + vsplatform
			fp.write('\t\t<Configuration\n')
			fp.write('\t\t\tName="' + token + '"\n')
			fp.write('\t\t\tOutputDirectory="bin\\"\n')
			if vsplatform=='x64':
				platformcode2 = 'w64'
			elif vsplatform=='Win32':
				platformcode2 = 'w32'
			else:
				platformcode2 = platformcode
			intdirectory = solution.projectname + getidecode(solution) + platformcode2 + getconfigurationcode(target)
			fp.write('\t\t\tIntermediateDirectory="temp\\' + intdirectory + '"\n')
			if solution.kind=='library':
				# Library
				fp.write('\t\t\tConfigurationType="4"\n')
			else:
				# Application
				fp.write('\t\t\tConfigurationType="1"\n')
			fp.write('\t\t\tUseOfMFC="0"\n')
			fp.write('\t\t\tATLMinimizesCRunTimeLibraryUsage="false"\n')
			# Unicode
			fp.write('\t\t\tCharacterSet="1"\n')
			fp.write('\t\t\t>\n')

			fp.write('\t\t\t<Tool\n')
			fp.write('\t\t\t\tName="VCCLCompilerTool"\n')
			fp.write('\t\t\t\tPreprocessorDefinitions="')
			if target=='Release':
				fp.write('NDEBUG')
			else:
				fp.write('_DEBUG')
			if vsplatform=='x64':
				fp.write(';WIN64;_WINDOWS')
			elif vsplatform=='Win32':
				fp.write(';WIN32;_WINDOWS')
			for item in solution.defines:
				fp.write(';' + item)
			fp.write('"\n')

			fp.write('\t\t\t\tStringPooling="true"\n')
			fp.write('\t\t\t\tExceptionHandling="0"\n')
			fp.write('\t\t\t\tStructMemberAlignment="4"\n')
			fp.write('\t\t\t\tEnableFunctionLevelLinking="true"\n')
			fp.write('\t\t\t\tFloatingPointModel="2"\n')
			fp.write('\t\t\t\tRuntimeTypeInfo="false"\n')
			fp.write('\t\t\t\tPrecompiledHeaderFile=""\n')
			# 8 byte alignment
			fp.write('\t\t\t\tWarningLevel="4"\n')
			fp.write('\t\t\t\tSuppressStartupBanner="true"\n')
			if solution.kind=='library' or target!='Release':
				fp.write('\t\t\t\tDebugInformationFormat="3"\n')
				fp.write('\t\t\t\tProgramDataBaseFileName="$(OutDir)\$(TargetName).pdb"\n')
			else:
				fp.write('\t\t\t\tDebugInformationFormat="0"\n')
			
			fp.write('\t\t\t\tCallingConvention="1"\n')
			fp.write('\t\t\t\tCompileAs="2"\n')
			fp.write('\t\t\t\tFavorSizeOrSpeed="1"\n')
			# Disable annoying nameless struct warnings since windows headers trigger this
			fp.write('\t\t\t\tDisableSpecificWarnings="4201"\n')

			if target=='Debug':
				fp.write('\t\t\t\tOptimization="0"\n')
			else:
				fp.write('\t\t\t\tOptimization="2"\n')
				fp.write('\t\t\t\tInlineFunctionExpansion="2"\n')
				fp.write('\t\t\t\tEnableIntrinsicFunctions="true"\n')
				fp.write('\t\t\t\tOmitFramePointers="true"\n')
			if target=='Release':
				fp.write('\t\t\t\tBufferSecurityCheck="false"\n')
				fp.write('\t\t\t\tRuntimeLibrary="0"\n')
			else:
				fp.write('\t\t\t\tBufferSecurityCheck="true"\n')
				fp.write('\t\t\t\tRuntimeLibrary="1"\n')
				
			#
			# Include directories
			#
			fp.write('\t\t\t\tAdditionalIncludeDirectories="')
			addcolon = False
			included = includedirectories + solution.includefolders
			if len(included):
				for dir in included:
					if addcolon==True:
						fp.write(';')
					fp.write(converttowindowsslashes(dir))
					addcolon = True
			if platformcode=='win':
				if addcolon==True:
					fp.write(';')
				fp.write('$(SDKS)\windows\directx9;$(SDKS)\windows\opengl')
				addcolon = True
			fp.write('"\n')
			fp.write('\t\t\t/>\n')
			
			fp.write('\t\t\t<Tool\n')
			fp.write('\t\t\t\tName="VCResourceCompilerTool"\n')
			fp.write('\t\t\t\tCulture="1033"\n')
			fp.write('\t\t\t/>\n')
			
			if solution.kind=='library':
				fp.write('\t\t\t<Tool\n')
				fp.write('\t\t\t\tName="VCLibrarianTool"\n')
				fp.write('\t\t\t\tOutputFile="&quot;$(OutDir)' + intdirectory + '.lib&quot;"\n')
				fp.write('\t\t\t\tSuppressStartupBanner="true"\n')
				fp.write('\t\t\t/>\n')
				if solution.finalfolder!=None:
					finalfolder = converttowindowsslasheswithendslash(solution.finalfolder)
					fp.write('\t\t\t<Tool\n')
					fp.write('\t\t\t\tName="VCPostBuildEventTool"\n')
					fp.write('\t\t\t\tDescription="Copying $(TargetName)$(TargetExt) to ' + finalfolder + '"\n')
					fp.write('\t\t\t\tCommandLine="&quot;$(perforce)\p4&quot; edit &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; edit &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;')
					fp.write('copy /Y &quot;$(OutDir)$(TargetName)$(TargetExt)&quot; &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('copy /Y &quot;$(OutDir)$(TargetName).pdb&quot; &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; revert -a &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; revert -a &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;"\n')
					fp.write('\t\t\t/>\n')
			else:
				fp.write('\t\t\t<Tool\n')
				fp.write('\t\t\t\tName="VCLinkerTool"\n')
				fp.write('\t\t\t\tOutputFile="&quot;$(OutDir)' + intdirectory + '.exe&quot;"\n')
				fp.write('\t\t\t\tAdditionalLibraryDirectories="')
				addcolon = False
				for item in solution.includefolders:
					if addcolon==True:
						fp.write(';')
					fp.write(converttowindowsslashes(item))
					addcolon = True
					
				if addcolon==True:
					fp.write(';')
				fp.write('$(SDKS)\windows\opengl"\n')
				if solution.kind=='tool':
					# main()
					fp.write('\t\t\t\tSubSystem="1"\n')
				else:
					# WinMain()
					fp.write('\t\t\t\tSubSystem="2"\n')
				fp.write('\t\t\t/>\n')
			fp.write('\t\t</Configuration>\n')

	fp.write('\t</Configurations>\n')	
		
	#
	# Save out the filenames
	#
	
	listh = pickfromfilelist(codefiles,'h')
	listcpp = pickfromfilelist(codefiles,'cpp')
	listwindowsresource = []
	listhlsl = []
	if platformcode=='win':
		listwindowsresource = pickfromfilelist(codefiles,'windowsresource')
		listhlsl = pickfromfilelist(codefiles,'hlsl')
	
	alllists = listh + listcpp + listwindowsresource
	if len(alllists):

		#	
		# Create groups first since Visual Studio uses a nested tree structure
		# for file groupings
		#
		
		groups = dict()
		for item in alllists:
			groupname = converttowindowsslashes(extractgroupname(item.filename))
			# Put each filename in its proper group
			if groupname in groups:
				groups[groupname].append(converttowindowsslashes(item.filename))
			else:
				# New group!
				groups[groupname] = [converttowindowsslashes(item.filename)]
		
		#
		# Create a recursive tree in order to store out the file list
		#

		fp.write('\t<Files>\n')
		tree = dict()
		for group in groups:
			#
			# Get the depth of the tree needed
			#
			
			parts = group.split('\\')
			next = tree
			#
			# Iterate over every part
			#
			for x in xrange(len(parts)):
				# Already declared?
				if not parts[x] in next:
					next[parts[x]] = dict()
				# Step into the tree
				next = next[parts[x]]

		# Use this tree to play back all the data
		dumptreevs2005(2,'',tree,fp,groups)
		fp.write('\t</Files>\n')
		
	fp.write('</VisualStudioProject>\n')
	fp.close()

	return 0

			
#
# Create the solution and project file for visual studio 2008
#

def createvs2008solution(solution):
	error,projectfilename = createslnfile(solution)
	if error!=0:
		return error
	#
	# Now, let's create the project file
	#
	
	codefiles,includedirectories = getfilelist(solution)
	platformcode = getplatformcode(solution.platform)
	solutionuuid = str(uuid.uuid3(uuid.NAMESPACE_DNS,str(projectfilename))).upper()
	projectpathname = os.path.join(solution.workingDir,projectfilename + '.vcproj')
	fp = open(projectpathname,'w')
	
	#
	# Save off the xml header
	#
	
	fp.write('<?xml version="1.0" encoding="utf-8"?>\n')
	fp.write('<VisualStudioProject\n')
	fp.write('\tProjectType="Visual C++"\n')
	fp.write('\tVersion="9.00"\n')
	fp.write('\tName="' + solution.projectname + '"\n')
	fp.write('\tProjectGUID="{' + solutionuuid + '}"\n')
	fp.write('\t>\n')

	#
	# Write the project platforms
	#

	fp.write('\t<Platforms>\n')
	for vsplatform in getvsplatform(solution.platform):
		fp.write('\t\t<Platform Name="' + vsplatform + '" />\n')
	fp.write('\t</Platforms>\n')

	#
	# Write the project configurations
	#
	
	fp.write('\t<Configurations>\n')
	for target in solution.configurations:
		for vsplatform in getvsplatform(solution.platform):
			token = target + '|' + vsplatform
			fp.write('\t\t<Configuration\n')
			fp.write('\t\t\tName="' + token + '"\n')
			fp.write('\t\t\tOutputDirectory="bin\\"\n')
			if vsplatform=='x64':
				platformcode2 = 'w64'
			elif vsplatform=='Win32':
				platformcode2 = 'w32'
			else:
				platformcode2 = platformcode
			intdirectory = solution.projectname + getidecode(solution) + platformcode2 + getconfigurationcode(target)
			fp.write('\t\t\tIntermediateDirectory="temp\\' + intdirectory + '\\"\n')
			if solution.kind=='library':
				# Library
				fp.write('\t\t\tConfigurationType="4"\n')
			else:
				# Application
				fp.write('\t\t\tConfigurationType="1"\n')
			fp.write('\t\t\tUseOfMFC="0"\n')
			fp.write('\t\t\tATLMinimizesCRunTimeLibraryUsage="false"\n')
			# Unicode
			fp.write('\t\t\tCharacterSet="1"\n')
			fp.write('\t\t\t>\n')

			fp.write('\t\t\t<Tool\n')
			fp.write('\t\t\t\tName="VCCLCompilerTool"\n')
			fp.write('\t\t\t\tPreprocessorDefinitions="')
			if target=='Release':
				fp.write('NDEBUG')
			else:
				fp.write('_DEBUG')
			if vsplatform=='x64':
				fp.write(';WIN64;_WINDOWS')
			elif vsplatform=='Win32':
				fp.write(';WIN32;_WINDOWS')
			for item in solution.defines:
				fp.write(';' + item)
			fp.write('"\n')

			fp.write('\t\t\t\tStringPooling="true"\n')
			fp.write('\t\t\t\tExceptionHandling="0"\n')
			fp.write('\t\t\t\tStructMemberAlignment="4"\n')
			fp.write('\t\t\t\tEnableFunctionLevelLinking="true"\n')
			fp.write('\t\t\t\tFloatingPointModel="2"\n')
			fp.write('\t\t\t\tRuntimeTypeInfo="false"\n')
			fp.write('\t\t\t\tPrecompiledHeaderFile=""\n')
			# 8 byte alignment
			fp.write('\t\t\t\tWarningLevel="4"\n')
			fp.write('\t\t\t\tSuppressStartupBanner="true"\n')
			if solution.kind=='library' or target!='Release':
				fp.write('\t\t\t\tDebugInformationFormat="3"\n')
				fp.write('\t\t\t\tProgramDataBaseFileName="$(OutDir)\$(TargetName).pdb"\n')
			else:
				fp.write('\t\t\t\tDebugInformationFormat="0"\n')
			
			fp.write('\t\t\t\tCallingConvention="1"\n')
			fp.write('\t\t\t\tCompileAs="2"\n')
			fp.write('\t\t\t\tFavorSizeOrSpeed="1"\n')
			# Disable annoying nameless struct warnings since windows headers trigger this
			fp.write('\t\t\t\tDisableSpecificWarnings="4201"\n')

			if target=='Debug':
				fp.write('\t\t\t\tOptimization="0"\n')
				# Necessary to quiet Visual Studio 2008 warnings
				fp.write('\t\t\t\tEnableIntrinsicFunctions="true"\n')
			else:
				fp.write('\t\t\t\tOptimization="2"\n')
				fp.write('\t\t\t\tInlineFunctionExpansion="2"\n')
				fp.write('\t\t\t\tEnableIntrinsicFunctions="true"\n')
				fp.write('\t\t\t\tOmitFramePointers="true"\n')
			if target=='Release':
				fp.write('\t\t\t\tBufferSecurityCheck="false"\n')
				fp.write('\t\t\t\tRuntimeLibrary="0"\n')
			else:
				fp.write('\t\t\t\tBufferSecurityCheck="true"\n')
				fp.write('\t\t\t\tRuntimeLibrary="1"\n')
				
			#
			# Include directories
			#
			fp.write('\t\t\t\tAdditionalIncludeDirectories="')
			addcolon = False
			included = includedirectories + solution.includefolders
			if len(included):
				for dir in included:
					if addcolon==True:
						fp.write(';')
					fp.write(converttowindowsslashes(dir))
					addcolon = True
			if platformcode=='win':
				if addcolon==True:
					fp.write(';')
				fp.write('$(SDKS)\windows\directx9;$(SDKS)\windows\opengl')
				addcolon = True
			fp.write('"\n')
			fp.write('\t\t\t/>\n')
			
			fp.write('\t\t\t<Tool\n')
			fp.write('\t\t\t\tName="VCResourceCompilerTool"\n')
			fp.write('\t\t\t\tCulture="1033"\n')
			fp.write('\t\t\t/>\n')
			
			if solution.kind=='library':
				fp.write('\t\t\t<Tool\n')
				fp.write('\t\t\t\tName="VCLibrarianTool"\n')
				fp.write('\t\t\t\tOutputFile="&quot;$(OutDir)' + intdirectory + '.lib&quot;"\n')
				fp.write('\t\t\t\tSuppressStartupBanner="true"\n')
				fp.write('\t\t\t/>\n')
				if solution.finalfolder!=None:
					finalfolder = converttowindowsslasheswithendslash(solution.finalfolder)
					fp.write('\t\t\t<Tool\n')
					fp.write('\t\t\t\tName="VCPostBuildEventTool"\n')
					fp.write('\t\t\t\tDescription="Copying $(TargetName)$(TargetExt) to ' + finalfolder + '"\n')
					fp.write('\t\t\t\tCommandLine="&quot;$(perforce)\p4&quot; edit &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; edit &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;')
					fp.write('copy /Y &quot;$(OutDir)$(TargetName)$(TargetExt)&quot; &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('copy /Y &quot;$(OutDir)$(TargetName).pdb&quot; &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; revert -a &quot;' + finalfolder + '$(TargetName)$(TargetExt)&quot;&#x0D;&#x0A;')
					fp.write('&quot;$(perforce)\p4&quot; revert -a &quot;' + finalfolder + '$(TargetName).pdb&quot;&#x0D;&#x0A;"\n')
					fp.write('\t\t\t/>\n')
			else:
				fp.write('\t\t\t<Tool\n')
				fp.write('\t\t\t\tName="VCLinkerTool"\n')
				fp.write('\t\t\t\tOutputFile="&quot;$(OutDir)' + intdirectory + '.exe&quot;"\n')
				fp.write('\t\t\t\tAdditionalLibraryDirectories="')
				addcolon = False
				for item in solution.includefolders:
					if addcolon==True:
						fp.write(';')
					fp.write(converttowindowsslashes(item))
					addcolon = True
					
				if addcolon==True:
					fp.write(';')
				fp.write('$(SDKS)\windows\opengl"\n')
				if solution.kind=='tool':
					# main()
					fp.write('\t\t\t\tSubSystem="1"\n')
				else:
					# WinMain()
					fp.write('\t\t\t\tSubSystem="2"\n')
				fp.write('\t\t\t/>\n')
			fp.write('\t\t</Configuration>\n')

	fp.write('\t</Configurations>\n')	
		
	#
	# Save out the filenames
	#
	
	listh = pickfromfilelist(codefiles,'h')
	listcpp = pickfromfilelist(codefiles,'cpp')
	listwindowsresource = []
	listhlsl = []
	if platformcode=='win':
		listwindowsresource = pickfromfilelist(codefiles,'windowsresource')
		listhlsl = pickfromfilelist(codefiles,'hlsl')
	
	alllists = listh + listcpp + listwindowsresource
	if len(alllists):

		#	
		# Create groups first
		#
		
		groups = dict()
		for item in alllists:
			groupname = converttowindowsslashes(extractgroupname(item.filename))
			# Put each filename in its proper group
			if groupname in groups:
				groups[groupname].append(converttowindowsslashes(item.filename))
			else:
				# New group!
				groups[groupname] = [converttowindowsslashes(item.filename)]
		
		#
		# Create a recursive tree in order to store out the file list
		#

		fp.write('\t<Files>\n')
		tree = dict()
		for group in groups:
			#
			# Get the depth of the tree needed
			#
			
			parts = group.split('\\')
			next = tree
			#
			# Iterate over every part
			#
			for x in xrange(len(parts)):
				# Already declared?
				if not parts[x] in next:
					next[parts[x]] = dict()
				# Step into the tree
				next = next[parts[x]]

		# Use this tree to play back all the data
		dumptreevs2005(2,'',tree,fp,groups)
		fp.write('\t</Files>\n')
		
	fp.write('</VisualStudioProject>\n')
	fp.close()
		
	return 0
	
#
# Create the solution and project file for visual studio 2010
#

def createvs2010solution(solution):
	
	error,projectfilename = createslnfile(solution)
	if error!=0:
		return error
		
	#
	# Now, let's create the project file
	#
	
	codefiles,includedirectories = getfilelist(solution)
	platformcode = getplatformcode(solution.platform)
	solutionuuid = str(uuid.uuid3(uuid.NAMESPACE_DNS,str(projectfilename))).upper()
	projectpathname = os.path.join(solution.workingDir,projectfilename + '.vcxproj')
	fp = open(projectpathname,'w')
	
	#
	# Save off the xml header
	#
	
	fp.write('<?xml version="1.0" encoding="utf-8"?>\n')
	fp.write('<Project DefaultTargets="Build" ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n')

	#
	# nVidia Shield projects have a version header
	#

	if solution.platform=='shield':
		fp.write('\t<PropertyGroup Label="NsightTegraProject">\n')
		fp.write('\t\t<NsightTegraProjectRevisionNumber>4</NsightTegraProjectRevisionNumber>\n')
		fp.write('\t</PropertyGroup>\n')

	#
	# Write the project configurations
	#

	fp.write('\t<ItemGroup Label="ProjectConfigurations">\n')
	for target in solution.configurations:
		for vsplatform in getvsplatform(solution.platform):
			token = target + '|' + vsplatform
			fp.write('\t\t<ProjectConfiguration Include="' + token + '">\n')		
			fp.write('\t\t\t<Configuration>' + target + '</Configuration>\n')
			fp.write('\t\t\t<Platform>' + vsplatform + '</Platform>\n')
			fp.write('\t\t</ProjectConfiguration>\n')
	fp.write('\t</ItemGroup>\n')
	
	#
	# Write the project globals
	#
	
	fp.write('\t<PropertyGroup Label="Globals">\n')
	fp.write('\t\t<ProjectName>' + solution.projectname + '</ProjectName>\n')
	if solution.finalfolder!=None:
		final = converttowindowsslasheswithendslash(solution.finalfolder)
		fp.write('\t\t<FinalFolder>' + final + '</FinalFolder>\n')
	fp.write('\t\t<ProjectGuid>{' + solutionuuid + '}</ProjectGuid>\n')
	fp.write('\t</PropertyGroup>\n')	
	
	#
	# Add in the project includes
	#

	fp.write('\t<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />\n')
	if solution.kind=='library':
		fp.write('\t<Import Project="$(SDKS)\\visualstudio\\burger.libv10.props" />\n')
	elif solution.kind=='tool':
		fp.write('\t<Import Project="$(SDKS)\\visualstudio\\burger.toolv10.props" />\n')
	else:
		fp.write('\t<Import Project="$(SDKS)\\visualstudio\\burger.gamev10.props" />\n')	
	fp.write('\t<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />\n')
	fp.write('\t<ImportGroup Label="ExtensionSettings" />\n')
	fp.write('\t<ImportGroup Label="PropertySheets" />\n')
	fp.write('\t<PropertyGroup Label="UserMacros" />\n')

	#
	# Insert compiler settings
	#
	
	if len(includedirectories) or \
		len(solution.includefolders) or \
		len(solution.defines):
		fp.write('\t<ItemDefinitionGroup>\n')
		
		#
		# Handle global compiler defines
		#
		
		if len(includedirectories) or \
			len(solution.includefolders) or \
			len(solution.defines):
			fp.write('\t\t<ClCompile>\n')
	
			# Include directories
			if len(includedirectories) or len(solution.includefolders):
				fp.write('\t\t\t<AdditionalIncludeDirectories>')
				for dir in includedirectories:
					fp.write('$(ProjectDir)' + converttowindowsslashes(dir) + ';')
				for dir in solution.includefolders:
					fp.write(converttowindowsslashes(dir) + ';')
				fp.write('%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>\n')

			# Global defines
			if len(solution.defines):
				fp.write('\t\t\t<PreprocessorDefinitions>')
				for define in solution.defines:
					fp.write(define + ';')
				fp.write('%(PreprocessorDefinitions)</PreprocessorDefinitions>\n')
	
			fp.write('\t\t</ClCompile>\n')

		#
		# Handle global linker defines
		#
		
		if len(solution.includefolders):
			fp.write('\t\t<Link>\n')
	
			# Include directories
			if len(solution.includefolders):
				fp.write('\t\t\t<AdditionalLibraryDirectories>')
				for dir in solution.includefolders:
					fp.write(converttowindowsslashes(dir) + ';')
				fp.write('%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>\n')

			fp.write('\t\t</Link>\n')

		fp.write('\t</ItemDefinitionGroup>\n')

	#
	# This is needed for the PS3 and PS4 targets :(
	#
	
	if platformcode=='ps3' or platformcode=='ps4':
		fp.write('\t<ItemDefinitionGroup Condition="\'$(BurgerConfiguration)\'!=\'Release\'">\n')
		fp.write('\t\t<ClCompile>\n')
		fp.write('\t\t\t<PreprocessorDefinitions>_DEBUG;%(PreprocessorDefinitions)</PreprocessorDefinitions>\n')
		fp.write('\t\t</ClCompile>\n')
		fp.write('\t</ItemDefinitionGroup>\n')
		fp.write('\t<ItemDefinitionGroup Condition="\'$(BurgerConfiguration)\'==\'Release\'">\n')
		fp.write('\t\t<ClCompile>\n')
		fp.write('\t\t\t<PreprocessorDefinitions>NDEBUG;%(PreprocessorDefinitions)</PreprocessorDefinitions>\n')
		fp.write('\t\t</ClCompile>\n')
		fp.write('\t</ItemDefinitionGroup>\n')

	#
	# Insert the source files
	#
	
	listh = pickfromfilelist(codefiles,'h')
	listcpp = pickfromfilelist(codefiles,'cpp')
	listwindowsresource = []
	listhlsl = []
	if platformcode=='win':
		listwindowsresource = pickfromfilelist(codefiles,'windowsresource')
		listhlsl = pickfromfilelist(codefiles,'hlsl')

	#
	# Any source files for the item groups?
	#
	
	if len(listh) or \
		len(listcpp) or \
		len(listwindowsresource) or \
		len(listhlsl):

		fp.write('\t<ItemGroup>\n')
		for item in listh:
			fp.write('\t\t<ClInclude Include="' + converttowindowsslashes(item.filename) + '" />\n')
		for item in listcpp:
			fp.write('\t\t<ClCompile Include="' + converttowindowsslashes(item.filename) + '" />\n')
		for item in listwindowsresource:
			fp.write('\t\t<ResourceCompile Include="' + converttowindowsslashes(item.filename) + '" />\n')
		for item in listhlsl:
			fp.write('\t\t<HLSL Include="' + converttowindowsslashes(item.filename) + '">\n')
			fp.write('\t\t\t<VariableName>g_DisplayDirectX8BitPS</VariableName>\n')
			fp.write('\t\t\t<TargetProfile>ps_2_0</TargetProfile>\n')
			fp.write('\t\t\t<ObjectFileName>%(RootDir)%(Directory)%(FileName).h</ObjectFileName>\n')
			fp.write('\t\t</HLSL>\n')
		fp.write('\t</ItemGroup>\n')	
	
	#
	# Close up the project file!
	#
	
	fp.write('\t<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />\n')
	fp.write('\t<ImportGroup Label="ExtensionTargets" />\n')
	fp.write('</Project>\n')
	fp.close()

	#
	# Is there need for a filter file? (Only for Visual Studio 2010 and up)
	#
	
	# 
	# Create the filter filename
	#
		
	filterpathname = os.path.join(solution.workingDir,projectfilename + '.vcxproj.filters')
	fp = open(filterpathname,'w')
		
	#
	# Stock header
	#
		
	fp.write('<?xml version="1.0" encoding="utf-8"?>\n')
	fp.write('<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n')

	groups = []
	fp.write('\t<ItemGroup>\n')

	for item in listh:
		groupname = converttowindowsslashes(extractgroupname(item.filename))
		if groupname!='':
			fp.write('\t\t<ClInclude Include="' + converttowindowsslashes(item.filename) + '">\n')
			fp.write('\t\t\t<Filter>' + groupname + '</Filter>\n')
			groups.append(groupname)
			fp.write('\t\t</ClInclude>\n')

	for item in listcpp:
		groupname = converttowindowsslashes(extractgroupname(item.filename))
		if groupname!='':
			fp.write('\t\t<ClCompile Include="' + converttowindowsslashes(item.filename) + '">\n')
			fp.write('\t\t\t<Filter>' + groupname + '</Filter>\n')
			groups.append(groupname)
			fp.write('\t\t</ClCompile>\n')

	for item in listwindowsresource:
		groupname = converttowindowsslashes(extractgroupname(item.filename))
		if groupname!='':
			fp.write('\t\t<ResourceCompile Include="' + converttowindowsslashes(item.filename) + '">\n')
			fp.write('\t\t\t<Filter>' + groupname + '</Filter>\n')
			groups.append(groupname)
			fp.write('\t\t</ResourceCompile>\n')

	for item in listhlsl:
		groupname = converttowindowsslashes(extractgroupname(item.filename))
		if groupname!='':
			fp.write('\t\t<HLSL Include="' + converttowindowsslashes(item.filename) + '">\n')
			fp.write('\t\t\t<Filter>' + groupname + '</Filter>\n')
			groups.append(groupname)
			fp.write('\t\t</HLSL>\n')
	
	groupset = set(groups)
	if len(groupset):
		for group in groupset:
			group = converttowindowsslashes(group)
			fp.write('\t\t<Filter Include="' + group + '">\n')
			groupuuid = str(uuid.uuid3(uuid.NAMESPACE_DNS,str(projectfilename + group))).upper()
			fp.write('\t\t\t<UniqueIdentifier>{' + groupuuid + '}</UniqueIdentifier>\n')
			fp.write('\t\t</Filter>\n')

	fp.write('\t</ItemGroup>\n')
	fp.write('</Project>\n')
	fp.close()
	
	#
	# Uh oh, filters weren't needed at all!
	#
	
	if len(groupset)==0:
		os.remove(filterpathname)
			
	return 0



###################################
#                                 #
# Xcode 3, 4 and 5 support        #
#                                 #
###################################		

#
# Given a string, create a 96 bit unique hash for XCode
#

def xcodeuuid(input):
	input = hashlib.md5(str(input).replace('/','\\')).hexdigest()
	input = input.upper()
	# Take the hash string and only use the top 96 bits
	input = input[0:24]
	return input

#
# Dump out a recursive tree of files to reconstruct a
# directory hiearchy
#

def dumptreevsxcode(string,entry,xcodepbxgroups,groups):
	children = []
	for item in entry:
		children.append(item)
		key = entry[item]
		if string=='':
			merged = item
		else:
			merged = string + '/' + item
		if type(key) is dict:
			dumptreevsxcode(merged,key,xcodepbxgroups,groups)
	
	if string=='':
		return children
		
	if string in groups:
		sortlist = sorted(groups[string],cmp=lambda x,y: cmp(converttolinuxslashes(x.filename),converttolinuxslashes(y.filename)))
		path = converttolinuxslashes(sortlist[0].filename)
	else:
		sortlist = []
		path = '<group>'
		
	index = string.rfind('/')
	if index==-1:
		base = string
	else:
		base = string[index+1:]

	index = path.rfind('/')
	if index!=-1:
		path = path[0:index]

	uuid = xcodeuuid('PBXGroup!' + base)
	out = '\t\t' + uuid + ' /* ' + base + ' */ = {\n' + \
		'\t\t\tisa = PBXGroup;\n' + \
		'\t\t\tchildren = (\n'
	for item in children:
		out = out + '\t\t\t\t' +  xcodeuuid('PBXGroup!' + item) + ' /* ' + item + ' */,\n'
	for item in sortlist:
		basename = os.path.basename(item.filename)
		out = out + '\t\t\t\t' + item.uuid + ' /* ' + basename + ' */,\n'
	out = out + '\t\t\t);\n' + \
		'\t\t\tname = ' + base + ';\n' + \
		'\t\t\tpath = ' + path + ';\n' + \
		'\t\t\tsourceTree = SOURCE_ROOT;\n' + \
		'\t\t};\n'
	xcodepbxgroups.append([uuid,out])
	return []
	
#
# Create a project file for XCode version 3.??
#

def createxcodesolution(solution,xcodeversion):
	#
	# Determine the filename (Sans extension)
	#
	
	codefiles,includedirectories = getfilelist(solution)
	
	#
	# Ensure the slashes are correct for XCode
	#
	
	for fixup in codefiles:
		fixup.filename = converttolinuxslashes(fixup.filename)

	#
	# Sort the file names
	#
	
	codefiles = sorted(codefiles,cmp=lambda x,y: cmp(x.filename,y.filename))

	#
	# Determine the ide and target type for the final file name
	#

	idecode = getidecode(solution)
	platformcode = getplatformcode(solution.platform)
	projectnamecode = str(solution.projectname + idecode + platformcode)
	
	#
	# Let's create the solution file!
	#
	
	solutionfoldername = os.path.join(solution.workingDir,projectnamecode + '.xcodeproj')
	createfolderifneeded(solutionfoldername)
	projectfilename = os.path.join(solutionfoldername,'project.pbxproj')

	#
	# Create semi-global uuids
	#
	
	rootuuid = xcodeuuid('PBXProjectRoot' + projectnamecode)
	shellscriptuuid = xcodeuuid('PBXShellScriptBuildPhase' + projectnamecode)
	frameworksuuid = xcodeuuid('PBXFrameworksBuildPhase' + projectnamecode)
	sourcesuuid = xcodeuuid('PBXSourcesBuildPhase' + projectnamecode)
	headersuuid = xcodeuuid('PBXHeadersBuildPhase' + projectnamecode)
	nativetargetuuid = xcodeuuid('PBXNativeTarget' + projectnamecode)
	tonativetargetuuid = xcodeuuid('ToPBXNativeTarget' + projectnamecode)
	pbxprojectuuid = xcodeuuid('PBXProject' + projectnamecode)
	projectnameuuid = xcodeuuid(solution.projectname)
	if solution.kind=='library':
		frameworks = []
		configfilename = 'burger.libxcoosx.xcconfig'
	else:
		frameworks = ['AppKit.framework']
		configfilename = 'burger.toolxcoosx.xcconfig'
	configfileuuid = xcodeuuid(configfilename)
	
	fp = open(projectfilename,'w')
	
	#
	# Write the XCode header
	#
	
	fp.write('// !$*UTF8*$!\n')
	fp.write('{\n')
	
	#
	# Always present in an XCode file
	#
	
	fp.write('\tarchiveVersion = 1;\n')
	fp.write('\tclasses = {\n')
	fp.write('\t};\n')
	
	#
	# 42 = XCode 2.4
	# 44 = XCode 3.0
	# 45 = XCode 3.1
	# 46 = XCode 3.2
	#
	
	fp.write('\tobjectVersion = 45;\n')
	fp.write('\tobjects = {\n\n')

	#
	# PBXBuildFile section
	#
	
	fp.write('/* Begin PBXBuildFile section */\n')

	#
	# Store the entire file list, however, only process types that
	# are relevant to the mac
	#

	toprocess = []
	for item in codefiles:
		if item.type == 'cpp':
			type = 'Sources'
		elif item.type == 'h':
			type = 'Headers'
		else:
			continue
		item.uuid = xcodeuuid(item.filename)
		item.typeuuid = xcodeuuid(item.filename + ':' + type)
		toprocess.append(item)
		
	for framework in frameworks:
		item = SourceFile()
		item.filename = framework
		item.type = 'frameworks'
		item.uuid = xcodeuuid(item.filename)
		item.typeuuid = xcodeuuid(item.filename+':Frameworks')
		toprocess.append(item)
	
	#
	# For reasons only Apple knows, it's sorted by the file type uuid
	#
	
	codefiles = sorted(toprocess,cmp=lambda x,y: cmp(x.typeuuid,y.typeuuid))
	for item in codefiles:
		basename = os.path.basename(item.filename)
		if item.type == 'cpp':
			type = 'Sources'
		elif item.type == 'frameworks':
			type = 'Frameworks'
		else:
		#elif item.type == 'h':
			type = 'Headers'
		fp.write('\t\t' + item.typeuuid + ' /* ' + basename + ' in ' + type + ' */ = {isa = PBXBuildFile; fileRef = ' + item.uuid + ' /* ' + basename + ' */; };\n')
		
	fp.write('/* End PBXBuildFile section */\n\n')
	
	#
	# PBXFileReference
	#
	
	fp.write('/* Begin PBXFileReference section */\n')
	
	toprocess = codefiles
	entry1 = SourceFile()
	entry1.filename = configfilename
	entry1.uuid = configfileuuid
	entry1.type = 'text.xcconfig'
	toprocess.append(entry1)
	
	#
	# Insert the output file
	#
	
	entry2 = SourceFile()
	if solution.kind=='library':
		outputfilename = 'libburgerbase' + idecode + 'osx.a'
		entry2.type = 'lib'
	else:
		outputfilename = solution.projectname
		entry2.type = 'exe'
	
	outputuuid = xcodeuuid(outputfilename + ':' + projectnamecode)
	entry2.filename = outputfilename
	entry2.uuid = outputuuid
	toprocess.append(entry2)	

	toprocess = sorted(toprocess,cmp=lambda x,y: cmp(x.uuid,y.uuid))
	for item in toprocess:
		basename = os.path.basename(item.filename)
		if item.type == 'lib':
			fp.write('\t\t' + item.uuid + ' /* ' + basename + ' */ = {isa = PBXFileReference; explicitFileType = archive.ar; includeInIndex = 0; path = ' + basename + '; sourceTree = BUILT_PRODUCTS_DIR; };\n')
			continue
		elif item.type == 'exe':
			fp.write('\t\t' + item.uuid + ' /* ' + basename + ' */ = {isa = PBXFileReference; explicitFileType = "compiled.mach-o.executable"; includeInIndex = 0; path = ' + basename + '; sourceTree = BUILT_PRODUCTS_DIR; };\n')
			continue
		elif item.type == 'frameworks':
			fp.write('\t\t' + item.uuid + ' /* ' + basename + ' */ = {isa = PBXFileReference; lastKnownFileType = wrapper.framework; name = ' + basename + '; path = System/Library/Frameworks/' + basename + '; sourceTree = SDKROOT; };\n')
			continue
		elif item.type == 'text.xcconfig':
			fp.write('\t\t' + item.uuid + ' /* ' + basename + ' */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = ' + item.type + '; name = ' + basename + '; path = xcode/' + basename + '; sourceTree = SDKS; };\n')
			continue
		elif item.type == 'cpp':
			type = 'sourcecode.cpp.cpp'
		else:
			type = 'sourcecode.c.h'
		fp.write('\t\t' + item.uuid + ' /* ' + basename + ' */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = ' + type + '; name = ' + basename + '; path = ' + item.filename + '; sourceTree = SOURCE_ROOT; };\n')

	fp.write('/* End PBXFileReference section */\n\n')
	
	toprocess.remove(entry1)
	toprocess.remove(entry2)
	
	#
	# PBXFrameworksBuildPhase
	#
	
	fp.write('/* Begin PBXFrameworksBuildPhase section */\n')
	fp.write('\t\t' + frameworksuuid + ' /* Frameworks */ = {\n')
	fp.write('\t\t\tisa = PBXFrameworksBuildPhase;\n')
	fp.write('\t\t\tbuildActionMask = 2147483647;\n')
	fp.write('\t\t\tfiles = (\n')
	for framework in frameworks:
		fp.write('\t\t\t\t' + xcodeuuid(framework+':Frameworks') + ' /* ' + framework + ' in Frameworks */,\n')	
	fp.write('\t\t\t);\n')
	fp.write('\t\t\trunOnlyForDeploymentPostprocessing = 0;\n')
	fp.write('\t\t};\n')
	fp.write('/* End PBXFrameworksBuildPhase section */\n\n')
	
	#
	# PBXGroup
	#
	
	#	
	# Create groups first since XCode uses a nested tree structure
	# for file groupings
	#
		
	groups = dict()
	for item in codefiles:
		groupname = extractgroupname(item.filename)
		# Put each filename in its proper group
		if groupname in groups:
			groups[groupname].append(item)
		else:
			# New group!
			groups[groupname] = [item]
		
	#
	# Create a recursive tree in order to store out the file list
	#

	tree = dict()
	for group in groups:
		#
		# Get the depth of the tree needed
		#
		parts = group.split('/')
		next = tree
		#
		# Iterate over every part
		#
		for x in xrange(len(parts)):
			# Already declared?
			if not parts[x] in next:
				next[parts[x]] = dict()
			# Step into the tree
			next = next[parts[x]]

	# Use this tree to play back all the data

	xcodepbxgroups = []
	productsuuid = '1AB674ADFE9D54B511CA2CBB'

	out = '\t\t' + productsuuid + ' /* Products */ = {\n' + \
		'\t\t\tisa = PBXGroup;\n' + \
		'\t\t\tchildren = (\n' + \
		'\t\t\t\t' + outputuuid + ' /* ' + outputfilename + ' */,\n' + \
		'\t\t\t);\n' + \
		'\t\t\tname = Products;\n' + \
		'\t\t\tsourceTree = "<group>";\n' + \
		'\t\t};\n'
	xcodepbxgroups.append([productsuuid,out])

	list = dumptreevsxcode('',tree,xcodepbxgroups,groups)

	#
	# Root group
	#
	
	if '' in groups:
		sortlist = sorted(groups[''],cmp=lambda x,y: cmp(x.filename,y.filename))
	else:
		sortlist = []
		
	out = '\t\t' + projectnameuuid + ' /* ' + solution.projectname + ' */ = {\n' + \
		'\t\t\tisa = PBXGroup;\n' + \
		'\t\t\tchildren = (\n'
	for item in list:
		if item=='':
			continue
		out = out + '\t\t\t\t' +  xcodeuuid('PBXGroup!' + item) + ' /* ' + item + ' */,\n'
	for item in sortlist:
		if item.uuid==outputuuid:
			continue
		basename = os.path.basename(item.filename)
		out = out + '\t\t\t\t' + item.uuid + ' /* ' + basename + ' */,\n'
	out = out + '\t\t\t\t' + productsuuid + ' /* Products */,\n' + \
		'\t\t\t);\n' + \
		'\t\t\tname = ' + solution.projectname + ';\n' + \
		'\t\t\tsourceTree = "<group>";\n' + \
		'\t\t};\n'
	xcodepbxgroups.append([projectnameuuid,out])
	
	# 
	# Sort by UUID
	#
	
	xcodepbxgroups = sorted(xcodepbxgroups,cmp=lambda x,y: cmp(x[0],y[0]))

	fp.write('/* Begin PBXGroup section */\n')
	for xcpbxgroup in xcodepbxgroups:
		fp.write(xcpbxgroup[1])
	fp.write('/* End PBXGroup section */\n\n')

	#
	# PBXHeadersBuildPhase
	#
	
	fp.write('/* Begin PBXHeadersBuildPhase section */\n')
	fp.write('\t\t' + headersuuid + ' /* Headers */ = {\n')
	fp.write('\t\t\tisa = PBXHeadersBuildPhase;\n')
	fp.write('\t\t\tbuildActionMask = 2147483647;\n')
	fp.write('\t\t\tfiles = (\n')
	codefiles = sorted(codefiles,cmp=lambda x,y: cmp(os.path.basename(x.filename),os.path.basename(y.filename)))
	for item in codefiles:
		if item.type=='h':
			basename = os.path.basename(item.filename)
			fp.write('\t\t\t\t' + item.typeuuid + ' /* ' + basename + ' in Headers */,\n')

	fp.write('\t\t\t);\n')
	fp.write('\t\t\trunOnlyForDeploymentPostprocessing = 0;\n')
	fp.write('\t\t};\n')
	fp.write('/* End PBXHeadersBuildPhase section */\n\n')

	#
	# PBXNativeTarget
	#

	fp.write('/* Begin PBXNativeTarget section */\n')
	fp.write('\t\t' + tonativetargetuuid + ' /* ' + projectnamecode + ' */ = {\n')
	fp.write('\t\t\tisa = PBXNativeTarget;\n')
	fp.write('\t\t\tbuildConfigurationList = ' + nativetargetuuid + ' /* Build configuration list for PBXNativeTarget "' + projectnamecode + '" */;\n')
	fp.write('\t\t\tbuildPhases = (\n')
	fp.write('\t\t\t\t' + headersuuid + ' /* Headers */,\n')
	fp.write('\t\t\t\t' + sourcesuuid + ' /* Sources */,\n')
	fp.write('\t\t\t\t' + frameworksuuid + ' /* Frameworks */,\n')
	if solution.finalfolder!=None:
		fp.write('\t\t\t\t' + shellscriptuuid + ' /* ShellScript */,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\tbuildRules = (\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\tdependencies = (\n')
	fp.write('\t\t\t);\n')
	if solution.kind=='library':
		fp.write('\t\t\tname = ' + projectnamecode + ';\n')
	else:
		fp.write('\t\t\tname = ' + solution.projectname + ';\n')

	fp.write('\t\t\tproductName = ' + solution.projectname + ';\n')
	fp.write('\t\t\tproductReference = ' + outputuuid + ' /* ' + outputfilename + ' */;\n')
	if solution.kind=='library':
		fp.write('\t\t\tproductType = "com.apple.product-type.library.static";\n')
	else:
		fp.write('\t\t\tproductType = "com.apple.product-type.tool";\n')
	fp.write('\t\t};\n')
	fp.write('/* End PBXNativeTarget section */\n\n')

	#
	# PBXProject
	#

	fp.write('/* Begin PBXProject section */\n')
	fp.write('\t\t' + rootuuid + ' /* Project object */ = {\n')
	fp.write('\t\t\tisa = PBXProject;\n')
	fp.write('\t\t\tattributes = {\n')
	fp.write('\t\t\t\tBuildIndependentTargetsInParallel = YES;\n')
	fp.write('\t\t\t};\n')
	fp.write('\t\t\tbuildConfigurationList = ' + pbxprojectuuid + ' /* Build configuration list for PBXProject "' + projectnamecode + '" */;\n')
	fp.write('\t\t\tcompatibilityVersion = "Xcode 3.1";\n')
	if xcodeversion>3:
		fp.write('\t\t\tdevelopmentRegion = English;\n')
	fp.write('\t\t\thasScannedForEncodings = 1;\n')
	fp.write('\t\t\tknownRegions = (\n')
	fp.write('\t\t\t\ten,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\tmainGroup = ' + projectnameuuid + ' /* ' + solution.projectname + ' */;\n')
	fp.write('\t\t\tprojectDirPath = "";\n')
	fp.write('\t\t\tprojectRoot = "";\n')
	fp.write('\t\t\ttargets = (\n')
	fp.write('\t\t\t\t' + tonativetargetuuid + ' /* ' + projectnamecode + ' */,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t};\n')
	fp.write('/* End PBXProject section */\n\n')

	#
	# PBXShellScriptBuildPhase
	#

	if solution.finalfolder!=None:
		fp.write('/* Begin PBXShellScriptBuildPhase section */\n')
		fp.write('\t\t' + shellscriptuuid + ' /* ShellScript */ = {\n')
		fp.write('\t\t\tisa = PBXShellScriptBuildPhase;\n')
		fp.write('\t\t\tbuildActionMask = 2147483647;\n')
		fp.write('\t\t\tfiles = (\n')
		fp.write('\t\t\t);\n')
		fp.write('\t\t\tinputPaths = (\n')
		fp.write('\t\t\t\t"$(CONFIGURATION_BUILD_DIR)/${EXECUTABLE_NAME}",\n')
		fp.write('\t\t\t);\n')
		fp.write('\t\t\toutputPaths = (\n')
		if solution.kind=='library':
			fp.write('\t\t\t\t"' + solution.finalfolder + '${FINAL_OUTPUT}",\n')
		else:
			fp.write('\t\t\t\t"' + solution.finalfolder + '${PRODUCT_NAME}",\n')
		fp.write('\t\t\t);\n')
		fp.write('\t\t\trunOnlyForDeploymentPostprocessing = 0;\n')
		fp.write('\t\t\tshellPath = /bin/sh;\n')
		finalfolder = solution.finalfolder.replace('(','{')
		finalfolder = finalfolder.replace(')','}')
		if solution.kind=='library':
			fp.write('\t\t\tshellScript = "${SDKS}/macosx/bin/p4 edit ' + finalfolder + '${FINAL_OUTPUT}\\n${CP} ${CONFIGURATION_BUILD_DIR}/${EXECUTABLE_NAME} ' + finalfolder + '${FINAL_OUTPUT}\\n\\n";\n')
		else:
			fp.write('\t\t\tshellScript = "if [ \\"${CONFIGURATION}\\" == \\"Release\\" ]; then\\n${SDKS}/macosx/bin/p4 edit ' + finalfolder + '${PRODUCT_NAME}\\n${CP} ${CONFIGURATION_BUILD_DIR}/${EXECUTABLE_NAME} ' + finalfolder + '${PRODUCT_NAME}\\nfi\\n";\n')
		fp.write('\t\t\tshowEnvVarsInLog = 0;\n')
		fp.write('\t\t};\n')
		fp.write('/* End PBXShellScriptBuildPhase section */\n\n')

	#
	# PBXSourcesBuildPhase
	#

	fp.write('/* Begin PBXSourcesBuildPhase section */\n')
	fp.write('\t\t' + sourcesuuid + ' /* Sources */ = {\n')
	fp.write('\t\t\tisa = PBXSourcesBuildPhase;\n')
	fp.write('\t\t\tbuildActionMask = 2147483647;\n')
	fp.write('\t\t\tfiles = (\n')
	for item in codefiles:
		if item.type=='cpp':
			basename = os.path.basename(item.filename)
			fp.write('\t\t\t\t' + xcodeuuid(item.filename+':Sources') + ' /* ' + basename + ' in Sources */,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\trunOnlyForDeploymentPostprocessing = 0;\n')
	fp.write('\t\t};\n')
	fp.write('/* End PBXSourcesBuildPhase section */\n\n')

	#
	# XCBuildConfiguration
	#
	
	xcbuildconfigurations = []
	for item in solution.configurations:
		uuid = xcodeuuid('PBXNativeTarget' + item)
		out = '\t\t' + uuid + ' /* ' + item + ' */ = {\n' + \
		'\t\t\tisa = XCBuildConfiguration;\n'
#		'\t\t\tbaseConfigurationReference = ' + configfileuuid + ' /* ' + configfilename + ' */;\n'
		out = out + '\t\t\tbuildSettings = {\n' + \
			'\t\t\t};\n' + \
			'\t\t\tname = ' + item + ';\n' + \
			'\t\t};\n'
		xcbuildconfigurations.append([uuid,out])

	for item in solution.configurations:
		uuid = xcodeuuid('PBXProject' + item)
		out = '\t\t' + uuid + ' /* ' + item + ' */ = {\n' + \
			'\t\t\tisa = XCBuildConfiguration;\n' + \
			'\t\t\tbaseConfigurationReference = ' + configfileuuid + ' /* ' + configfilename + ' */;\n' + \
			'\t\t\tbuildSettings = {\n' + \
			'\t\t\t};\n' + \
			'\t\t\tname = ' + item + ';\n' + \
			'\t\t};\n'
		xcbuildconfigurations.append([uuid,out])

	# 
	# Sort by UUID
	#
	
	xcbuildconfigurations = sorted(xcbuildconfigurations,cmp=lambda x,y: cmp(x[0],y[0]))

	fp.write('/* Begin XCBuildConfiguration section */\n')
	for xcbuildconfig in xcbuildconfigurations:
		fp.write(xcbuildconfig[1])
	fp.write('/* End XCBuildConfiguration section */\n\n')

	#
	# XCConfigurationList
	#

	if 'Release' in solution.configurations:
		defaultconfiguration = 'Release'
	else:
		defaultconfiguration = solution.configurations[0]
		
	fp.write('/* Begin XCConfigurationList section */\n')
	fp.write('\t\t' + nativetargetuuid + ' /* Build configuration list for PBXNativeTarget "' + projectnamecode + '" */ = {\n')
	fp.write('\t\t\tisa = XCConfigurationList;\n')
	fp.write('\t\t\tbuildConfigurations = (\n')
	for item in solution.configurations:
		fp.write('\t\t\t\t' + xcodeuuid('PBXNativeTarget' + item) + ' /* ' + item + ' */,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\tdefaultConfigurationIsVisible = 0;\n')
	fp.write('\t\t\tdefaultConfigurationName = ' + defaultconfiguration + ';\n')
	fp.write('\t\t};\n')
	fp.write('\t\t' + pbxprojectuuid + ' /* Build configuration list for PBXProject "' + projectnamecode + '" */ = {\n')
	fp.write('\t\t\tisa = XCConfigurationList;\n')
	fp.write('\t\t\tbuildConfigurations = (\n')
	for item in solution.configurations:
		fp.write('\t\t\t\t' + xcodeuuid('PBXProject' + item) + ' /* ' + item + ' */,\n')
	fp.write('\t\t\t);\n')
	fp.write('\t\t\tdefaultConfigurationIsVisible = 0;\n')
	fp.write('\t\t\tdefaultConfigurationName = ' + defaultconfiguration + ';\n')
	fp.write('\t\t};\n')
	fp.write('/* End XCConfigurationList section */\n')

	#
	# Close up the project file
	#
	
	fp.write('\t};\n')
	fp.write('\trootObject = ' + rootuuid + ' /* Project object */;\n')
	fp.write('}\n')
	fp.close()
	
	return 0


#
# Dump out a recursive tree of files to reconstruct a
# directory hiearchy for codewarrior
#

def dumptreecodewarrior(indent,string,entry,fp,groups):
	for item in entry:
		if item!='':
			fp.write('\t'*indent + '<GROUP><NAME>' + item + '</NAME>\n')
		if string=='':
			merged = item
		else:
			merged = string + '\\' + item
		if merged in groups:
			if item!='':
				tabs = '\t'*(indent+1)
			else:
				tabs = '\t'*indent
			sortlist = sorted(groups[merged],cmp=lambda x,y: cmp(x,y))
			for file in sortlist:
				fp.write(tabs + '<FILEREF>\n')
				fp.write(tabs + '\t<TARGETNAME>Win32 Release</TARGETNAME>\n')
				fp.write(tabs + '\t<PATHTYPE>Name</PATHTYPE>\n')
				fp.write(tabs + '\t<PATH>' + os.path.basename(file) + '</PATH>\n')
				fp.write(tabs + '\t<PATHFORMAT>Windows</PATHFORMAT>\n')
				fp.write(tabs + '</FILEREF>\n')
				
		key = entry[item]
		if type(key) is dict:
			dumptreecodewarrior(indent+1,merged,key,fp,groups)
		if item!='':
			fp.write('\t'*indent + '</GROUP>\n')
			
#
# Create a codewarrior 9.4 project
#

def createcodewarriorsolution(solution):
		
	#
	# Now, let's create the project file
	#
	
	codefiles,includedirectories = getfilelist(solution)
	platformcode = getplatformcode(solution.platform)
	idecode = getidecode(solution)
	projectfilename = str(solution.projectname + idecode + platformcode)
	projectpathname = os.path.join(solution.workingDir,projectfilename + '.mcp.xml')

	#
	# Save out the filenames
	#
	
	listh = pickfromfilelist(codefiles,'h')
	listcpp = pickfromfilelist(codefiles,'cpp')
	listwindowsresource = []
	if platformcode=='win':
		listwindowsresource = pickfromfilelist(codefiles,'windowsresource')
	
	alllists = listh + listcpp + listwindowsresource

	fp = open(projectpathname,'w')
	
	#
	# Save the standard XML header for CodeWarrior
	#
	
	fp.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n')
	fp.write('<?codewarrior exportversion="1.0.1" ideversion="5.0" ?>\n')

	#
	# Begin the project object
	#
	
	fp.write('<PROJECT>\n')

	#
	# Create all of the project targets
	#
	
	fp.write('\t<TARGETLIST>\n')
		
	#
	# Begin with a fake project that will build all of the other projects
	#
	
	fp.write('\t\t<TARGET>\n')
	fp.write('\t\t\t<NAME>Everything</NAME>\n')
	fp.write('\t\t\t<SETTINGLIST>\n')
	fp.write('\t\t\t\t<SETTING><NAME>Linker</NAME><VALUE>None</VALUE></SETTING>\n')
	fp.write('\t\t\t\t<SETTING><NAME>Targetname</NAME><VALUE>Everything</VALUE></SETTING>\n')
	fp.write('\t\t\t</SETTINGLIST>\n')
	fp.write('\t\t\t<FILELIST>\n')
	fp.write('\t\t\t</FILELIST>\n')
	fp.write('\t\t\t<LINKORDER>\n')
	fp.write('\t\t\t</LINKORDER>\n')
	if len(solution.configurations)!=0:
		fp.write('\t\t\t<SUBTARGETLIST>\n')
		for target in solution.configurations:
			if solution.platform=='windows':
				platformcode2 = 'Win32'
			else:
				platformcode2 = solution.platform
			fp.write('\t\t\t\t<SUBTARGET>\n')
			fp.write('\t\t\t\t\t<TARGETNAME>' + platformcode2 + ' ' + target + '</TARGETNAME>\n')	
			fp.write('\t\t\t\t</SUBTARGET>\n')
		fp.write('\t\t\t</SUBTARGETLIST>\n')
	fp.write('\t\t</TARGET>\n')

	#
	# Output each target
	#
	
	for target in solution.configurations:
	
		# Create the target name
		
		if solution.platform=='windows':
			platformcode2 = 'Win32'
		else:
			platformcode2 = solution.platform
		fp.write('\t\t<TARGET>\n')
		fp.write('\t\t\t<NAME>' + platformcode2 + ' ' + target + '</NAME>\n')	
		
		#
		# Store the settings for the target
		#
		
		fp.write('\t\t\t<SETTINGLIST>\n')
		
		#
		# Choose the target platform via the linker
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>Linker</NAME><VALUE>Win32 x86 Linker</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>Targetname</NAME><VALUE>' + platformcode2 + ' ' + target + '</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>OutputDirectory</NAME>\n')
		fp.write('\t\t\t\t\t<SETTING><NAME>Path</NAME><VALUE>bin</VALUE></SETTING>\n')
		fp.write('\t\t\t\t\t<SETTING><NAME>PathFormat</NAME><VALUE>Windows</VALUE></SETTING>\n')
		fp.write('\t\t\t\t\t<SETTING><NAME>PathRoot</NAME><VALUE>Project</VALUE></SETTING>\n')
		fp.write('\t\t\t\t</SETTING>\n')
		
		#
		# User include folders
		#
		
		if len(includedirectories)!=0:
			fp.write('\t\t\t\t<SETTING><NAME>UserSearchPaths</NAME>\n')
			for dirnameentry in includedirectories:
				fp.write('\t\t\t\t\t<SETTING>\n')
				fp.write('\t\t\t\t\t\t<SETTING><NAME>SearchPath</NAME>\n')
				fp.write('\t\t\t\t\t\t\t<SETTING><NAME>Path</NAME><VALUE>' + converttowindowsslashes(dirnameentry) + '</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathFormat</NAME><VALUE>Windows</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathRoot</NAME><VALUE>Project</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t\t</SETTING>\n')
				fp.write('\t\t\t\t\t\t<SETTING><NAME>Recursive</NAME><VALUE>false</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t\t<SETTING><NAME>FrameworkPath</NAME><VALUE>false</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t\t<SETTING><NAME>HostFlags</NAME><VALUE>All</VALUE></SETTING>\n')
				fp.write('\t\t\t\t\t</SETTING>\n')
			fp.write('\t\t\t\t</SETTING>\n')

		#
		# Operating system include folders
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>SystemSearchPaths</NAME>\n')
		for dirnameentry in ['windows\perforce','windows\opengl','windows\directx9']:
			fp.write('\t\t\t\t\t<SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>SearchPath</NAME>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>Path</NAME><VALUE>' + dirnameentry + '</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathFormat</NAME><VALUE>Windows</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathRoot</NAME><VALUE>SDKS</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t</SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>Recursive</NAME><VALUE>false</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>FrameworkPath</NAME><VALUE>false</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>HostFlags</NAME><VALUE>All</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t</SETTING>\n')

		for dirnameentry in ['MSL','Win32-x86 Support']:
			fp.write('\t\t\t\t\t<SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>SearchPath</NAME>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>Path</NAME><VALUE>' + dirnameentry + '</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathFormat</NAME><VALUE>Windows</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t\t<SETTING><NAME>PathRoot</NAME><VALUE>CodeWarrior</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t</SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>Recursive</NAME><VALUE>true</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>FrameworkPath</NAME><VALUE>false</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t\t<SETTING><NAME>HostFlags</NAME><VALUE>All</VALUE></SETTING>\n')
			fp.write('\t\t\t\t\t</SETTING>\n')

		fp.write('\t\t\t\t</SETTING>\n')

		#
		# Library/Application?
		#
		
		if solution.platform=='windows':
			platformcode2 = 'w32'
		else:
			platformcode2 = solution.platform
		if solution.kind=='library':
			fp.write('\t\t\t\t<SETTING><NAME>MWProject_X86_type</NAME><VALUE>Library</VALUE></SETTING>\n')
			fp.write('\t\t\t\t<SETTING><NAME>MWProject_X86_outfile</NAME><VALUE>' + solution.projectname + idecode + platformcode2 + getconfigurationcode(target) + '.lib</VALUE></SETTING>\n')
		else:
			fp.write('\t\t\t\t<SETTING><NAME>MWProject_X86_type</NAME><VALUE>Application</VALUE></SETTING>\n')
			fp.write('\t\t\t\t<SETTING><NAME>MWProject_X86_outfile</NAME><VALUE>' + solution.projectname + idecode + platformcode2 + getconfigurationcode(target) + '.exe</VALUE></SETTING>\n')

		#
		# Compiler settings for the front end
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_cplusplus</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_templateparser</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_instance_manager</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_enableexceptions</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_useRTTI</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_booltruefalse</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_wchar_type</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_ecplusplus</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_dontinline</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_inlinelevel</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_autoinline</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_defer_codegen</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_bottomupinline</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_ansistrict</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_onlystdkeywords</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_trigraphs</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_arm</NAME><VALUE>0</VALUE></SETTING>\n')		
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_checkprotos</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_c99</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_gcc_extensions</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_enumsalwaysint</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_unsignedchars</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_poolstrings</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWFrontEnd_C_dontreusestrings</NAME><VALUE>0</VALUE></SETTING>\n')

		#
		# Preprocessor settings
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_PrefixText</NAME><VALUE>#define ')
		if target=='Release':
			fp.write('NDEBUG\n')
		else:
			fp.write('_DEBUG\n')
		if platformcode2=='w32':
			fp.write('#define WIN32_LEAN_AND_MEAN\n#define WIN32\n')
		for defineentry in solution.defines:
			fp.write('#define ' + defineentry + '\n')
		fp.write('</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_MultiByteEncoding</NAME><VALUE>encASCII_Unicode</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_PCHUsesPrefixText</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_EmitPragmas</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_KeepWhiteSpace</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_EmitFullPath</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_KeepComments</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_EmitFile</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>C_CPP_Preprocessor_EmitLine</NAME><VALUE>false</VALUE></SETTING>\n')

		#
		# Warnings panel
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_illpragma</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_possunwant</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_pedantic</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_illtokenpasting</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_hidevirtual</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_implicitconv</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_impl_f2i_conv</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_impl_s2u_conv</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_impl_i2f_conv</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_ptrintconv</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_unusedvar</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_unusedarg</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_resultnotused</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_missingreturn</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_no_side_effect</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_extracomma</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_structclass</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_emptydecl</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_filenamecaps</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_filenamecapssystem</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_padding</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_undefmacro</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warn_notinlined</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWWarning_C_warningerrors</NAME><VALUE>0</VALUE></SETTING>\n')

		#
		# X86 code gen
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_runtime</NAME><VALUE>Custom</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_processor</NAME><VALUE>PentiumIV</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_use_extinst</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_extinst_mmx</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_extinst_3dnow</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_extinst_cmov</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_extinst_sse</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_extinst_sse2</NAME><VALUE>0</VALUE></SETTING>\n')

		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_use_mmx_3dnow_convention</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_vectorize</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_profile</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_readonlystrings</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_alignment</NAME><VALUE>bytes8</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_intrinsics</NAME><VALUE>1</VALUE></SETTING>\n')
		if target=='Debug':
			fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_optimizeasm</NAME><VALUE>0</VALUE></SETTING>\n')
			fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_disableopts</NAME><VALUE>1</VALUE></SETTING>\n')
		else:
			fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_optimizeasm</NAME><VALUE>1</VALUE></SETTING>\n')
			fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_disableopts</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_relaxieee</NAME><VALUE>1</VALUE></SETTING>\n')

		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_exceptions</NAME><VALUE>ZeroOverhead</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWCodeGen_X86_name_mangling</NAME><VALUE>MWWin32</VALUE></SETTING>\n')
		
		#
		# Global optimizations
		#
		
		if target=='Debug':
			fp.write('\t\t\t\t<SETTING><NAME>GlobalOptimizer_X86__optimizationlevel</NAME><VALUE>Level0</VALUE></SETTING>\n')
		else:
			fp.write('\t\t\t\t<SETTING><NAME>GlobalOptimizer_X86__optimizationlevel</NAME><VALUE>Level4</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>GlobalOptimizer_X86__optfor</NAME><VALUE>Size</VALUE></SETTING>\n')

		#
		# x86 disassembler
		#
		
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showHeaders</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showSectHeaders</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showSymTab</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showCode</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showData</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showDebug</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showExceptions</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showRelocation</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showRaw</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showAllRaw</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showSource</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showHex</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showComments</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_resolveLocals</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_resolveRelocs</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_showSymDefs</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_unmangle</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>PDisasmX86_verbose</NAME><VALUE>false</VALUE></SETTING>\n')

		#
		# x86 linker settings
		#

		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_linksym</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_linkCV</NAME><VALUE>1</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_symfullpath</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_linkdebug</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_debuginline</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_subsystem</NAME><VALUE>Unknown</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_entrypointusage</NAME><VALUE>Default</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_entrypoint</NAME><VALUE></VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_codefolding</NAME><VALUE>Any</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_usedefaultlibs</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_adddefaultlibs</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_mergedata</NAME><VALUE>true</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_zero_init_bss</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_generatemap</NAME><VALUE>0</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_checksum</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_linkformem</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_nowarnings</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_verbose</NAME><VALUE>false</VALUE></SETTING>\n')
		fp.write('\t\t\t\t<SETTING><NAME>MWLinker_X86_commandfile</NAME><VALUE></VALUE></SETTING>\n')

		#
		# Settings are done
		#
		
		fp.write('\t\t\t</SETTINGLIST>\n')
		
		#
		# Add in the list of files
		#
		
		liblist = ['user32.lib','kernel32.lib']
		if target=='Debug':
			liblist.append('MSL_All_x86_D.lib')
		else:
			liblist.append('MSL_All_x86.lib')

		if len(alllists)!=0:
			
			fp.write('\t\t\t<FILELIST>\n')
			if solution.kind!='library':
				for i in liblist:
					fp.write('\t\t\t\t<FILE>\n')
					fp.write('\t\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
					fp.write('\t\t\t\t\t<PATH>' + i + '</PATH>\n')
					fp.write('\t\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
					fp.write('\t\t\t\t\t<FILEKIND>Library</FILEKIND>\n')
					if target!='Release': 
						fp.write('\t\t\t\t\t<FILEFLAGS>Debug</FILEFLAGS>\n')
					else:
						fp.write('\t\t\t\t\t<FILEFLAGS></FILEFLAGS>\n')
					fp.write('\t\t\t\t</FILE>\n')
				
			filelist = []
			for i in alllists:
				parts = converttowindowsslashes(i.filename).split('\\')
				filelist.append(parts[len(parts)-1])
		
			filelist = sorted(filelist,cmp=lambda x,y: cmp(x,y))

			for i in filelist:
				fp.write('\t\t\t\t<FILE>\n')
				fp.write('\t\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
				fp.write('\t\t\t\t\t<PATH>' + i + '</PATH>\n')
				fp.write('\t\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
				fp.write('\t\t\t\t\t<FILEKIND>Text</FILEKIND>\n')
				if target!='Release' and (i.endswith('.c') or i.endswith('.cpp')): 
					fp.write('\t\t\t\t\t<FILEFLAGS>Debug</FILEFLAGS>\n')
				else:
					fp.write('\t\t\t\t\t<FILEFLAGS></FILEFLAGS>\n')
				fp.write('\t\t\t\t</FILE>\n')
			
			fp.write('\t\t\t</FILELIST>\n')
		
			fp.write('\t\t\t<LINKORDER>\n')
			if solution.kind!='library':
				for i in liblist:
					fp.write('\t\t\t\t<FILEREF>\n')
					fp.write('\t\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
					fp.write('\t\t\t\t\t<PATH>' + i + '</PATH>\n')
					fp.write('\t\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
					fp.write('\t\t\t\t</FILEREF>\n')
			for i in filelist:
				fp.write('\t\t\t\t<FILEREF>\n')
				fp.write('\t\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
				fp.write('\t\t\t\t\t<PATH>' + i + '</PATH>\n')
				fp.write('\t\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
				fp.write('\t\t\t\t</FILEREF>\n')
			fp.write('\t\t\t</LINKORDER>\n')
		
		fp.write('\t\t</TARGET>\n')

	#
	# All of the targets are saved
	#
	
	fp.write('\t</TARGETLIST>\n')
	
	#
	# Now output the list of targets
	#
	
	fp.write('\t<TARGETORDER>\n')
	fp.write('\t\t<ORDEREDTARGET><NAME>Everything</NAME></ORDEREDTARGET>\n')
	for target in solution.configurations:
		if solution.platform=='windows':
			platformcode2 = 'Win32'
		else:
			platformcode2 = solution.platform
		fp.write('\t\t<ORDEREDTARGET><NAME>' + platformcode2 + ' ' + target + '</NAME></ORDEREDTARGET>\n')
	fp.write('\t</TARGETORDER>\n')

	#
	# Save the file list as they are displayed in the IDE
	#
	
	if len(alllists):

		#	
		# Create groups first since CodeWarrior uses a nested tree structure
		# for file groupings
		#
		
		groups = dict()
		for item in alllists:
			groupname = converttowindowsslashes(extractgroupname(item.filename))
			# Put each filename in its proper group
			if groupname in groups:
				groups[groupname].append(converttowindowsslashes(item.filename))
			else:
				# New group!
				groups[groupname] = [converttowindowsslashes(item.filename)]
		
		#
		# Create a recursive tree in order to store out the file list
		#

		fp.write('\t<GROUPLIST>\n')
		tree = dict()
		for group in groups:
			#
			# Get the depth of the tree needed
			#
			
			parts = group.split('\\')
			next = tree
			#
			# Iterate over every part
			#
			for x in xrange(len(parts)):
				# Already declared?
				if not parts[x] in next:
					next[parts[x]] = dict()
				# Step into the tree
				next = next[parts[x]]

		# Use this tree to play back all the data
		dumptreecodewarrior(2,'',tree,fp,groups)
		
		if solution.kind!='library':
			liblist = ['user32.lib','kernel32.lib','MSL_All_x86.lib']
			fp.write('\t\t<GROUP><NAME>Libraries</NAME>\n')
			for i in liblist:
				fp.write('\t\t\t<FILEREF>\n')
				fp.write('\t\t\t\t<TARGETNAME>Win32 Release</TARGETNAME>\n')
				fp.write('\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
				fp.write('\t\t\t\t<PATH>' + i + '</PATH>\n')
				fp.write('\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
				fp.write('\t\t\t</FILEREF>\n')

			fp.write('\t\t\t<FILEREF>\n')
			fp.write('\t\t\t\t<TARGETNAME>Win32 Debug</TARGETNAME>\n')
			fp.write('\t\t\t\t<PATHTYPE>Name</PATHTYPE>\n')
			fp.write('\t\t\t\t<PATH>MSL_All_x86_D.lib</PATH>\n')
			fp.write('\t\t\t\t<PATHFORMAT>Windows</PATHFORMAT>\n')
			fp.write('\t\t\t</FILEREF>\n')
			fp.write('\t\t</GROUP>\n')
	
		fp.write('\t</GROUPLIST>\n')

	#
	# Close the file
	#
	
	fp.write('</PROJECT>\n')
	fp.close()
	
	#
	# If codewarrior is installed, create the MCP file
	#
	
	cwfile = os.getenv('CWFolder')
	if cwfile!=None and solution.platform=='windows':
		cwfile = os.path.join(cwfile,'Bin','ide')
		cmd = '"' + cwfile + '" /x "' + projectpathname + '" "' + os.path.join(solution.workingDir,projectfilename + '.mcp') + '" /s /c /q'
		sys.stdout.flush()
		error = subprocess.call(cmd,cwd=os.path.dirname(projectpathname),shell=True)
		if error==0:
			os.remove(projectpathname)
		return error
		
	return 0

#
# Given a solution type (Game, Tool, etc)
# Process all the sub sections
#

def processsolution(myjson,solution):

	error = 0
	for key in myjson.keys():
		if key=='kind' or \
			key=='projectname' or \
			key=='finalfolder' or \
			key=='platform':
			setattr(solution,key,myjson[key])
		elif key=='configurations' or \
			key=='sourcefolders' or \
			key=='exclude' or \
			key=='defines' or \
			key=='includefolders':
			setattr(solution,key,converttoarray(myjson[key]))
		else:
			print 'Unknown keyword "' + str(key) + '" with data "' + str(myjson[key]) + '" found in solution group'
			error = 1
			continue
	return solution,error

#
# The script is an array of objects containing solution settings
# and a list of ides to output scripts
#

def processeverything(myjsonlist,solution):
	error = 0
	for item in myjsonlist:
		if type(item) is dict:
			solution,error = processsolution(item,solution)
		elif item=='vs2010':
			solution.ide = item
			error = createvs2010solution(solution)
		elif item=='vs2008':
			solution.ide = item
			error = createvs2008solution(solution)
		elif item=='vs2005':
			solution.ide = item
			error = createvs2005solution(solution)
		elif item=='xcode3':
			solution.ide = item
			error = createxcodesolution(solution,3)
		elif item=='xcode4':
			solution.ide = item
			error = createxcodesolution(solution,4)
		elif item=='xcode5':
			solution.ide = item
			error = createxcodesolution(solution,5)
		elif item=='codewarrior':
			solution.ide = item
			error = createcodewarriorsolution(solution)
		else:
			print 'Saving ' + item + ' not implemented yet'
			error = 0
		if error!=0:
			break
	return error

#
# Handle the default case
#

def processdefault(solution,args):
	#
	# Build as many of the targets as requested
	#
	
	solution.projectname = os.path.basename(solution.workingDir)
	solution.kind = 'tool'
	solution.platform = 'windows'
	solution.finalfolder = '$(sdks)/windows/bin/'

	myjsonlist = []
	if args.xcode3==True:
		myjsonlist.append('xcode3')
		solution.platform = 'macosx'
		solution.finalfolder = '$(SDKS)/macosx/bin/'
	if args.xcode4==True:
		myjsonlist.append('xcode4')
		solution.platform = 'macosx'
		solution.finalfolder = '$(SDKS)/macosx/bin/'
	if args.xcode5==True:
		myjsonlist.append('xcode5')
		solution.platform = 'macosx'
		solution.finalfolder = '$(SDKS)/macosx/bin/'
	if args.vs2005==True:
		myjsonlist.append('vs2005')
	if args.vs2008==True:
		myjsonlist.append('vs2008')
	if args.vs2010==True:
		myjsonlist.append('vs2010')
	if args.codeblocks==True:
		myjsonlist.append('codeblocks')
	if args.codewarrior==True:
		myjsonlist.append('codewarrior')
	
	if len(myjsonlist)==0:
		print 'No default "projects.json" file found nor any project type specified'
		return 2 
	
	#
	# Add the folder 'source' if found
	#
	
	if os.path.isdir(os.path.join(solution.workingDir,'source')):
		solution.sourcefolders.append('source')
	return processeverything(myjsonlist,solution)

#
# Command line shell
#

	
def main():
	
	#
	# Load from here
	#
	
	workingDir = os.getcwd()
	
	# Parse the command line
	
	parser = argparse.ArgumentParser(
		description='Create project files. Copyright by Rebecca Ann Heineman. Given a .json input file, create project files')
	parser.add_argument('-xcode3', dest='xcode3', action='store_true',
		default=False,
		help='Build for Xcode 3.')
	parser.add_argument('-xcode4', dest='xcode4', action='store_true',
		default=False,
		help='Build for Xcode 4.')
	parser.add_argument('-xcode5', dest='xcode5', action='store_true',
		default=False,
		help='Build for Xcode 5.')
	parser.add_argument('-vs2005', dest='vs2005', action='store_true',
		default=False,
		help='Build for Visual Studio 2005.')
	parser.add_argument('-vs2008', dest='vs2008', action='store_true',
		default=False,
		help='Build for Visual Studio 2008.')
	parser.add_argument('-vs2010', dest='vs2010', action='store_true',
		default=False,
		help='Build for Visual Studio 2010.')
	parser.add_argument('-codeblocks', dest='codeblocks', action='store_true',
		default=False,
		help='Build for CodeBlocks 12.11')
	parser.add_argument('-codewarrior', dest='codewarrior', action='store_true',
		default=False,
		help='Build for CodeWarrior')
	parser.add_argument('-f',dest='jsonfiles',action='append',
		help='Input file to process')
	parser.add_argument('-v','-verbose',dest='verbose',action='store_true',
		default=False,
		help='Verbose output.')
	parser.add_argument('args',nargs=argparse.REMAINDER,help='project filenames')

	args = parser.parse_args()
	verbose = args.verbose
	
	#
	# Process defaults first
	#

	solution = SolutionData()
	solution.workingDir = workingDir
	
	#
	# No input file?
	#
	
	if args.jsonfiles==None:
		projectpathname = os.path.join(workingDir,'projects.json')
		if os.path.isfile(projectpathname)==True:
			args.jsonfiles = ['projects.json']
		else:
			error = processdefault(solution,args)
			return error
	
	#
	# Read in the json file
	#
	
	for input in args.jsonfiles:
		projectpathname = os.path.join(workingDir,input)
		if os.path.isfile(projectpathname)!=True:
			print input + ' was not found'
			return 2
	
	
		fp = open(projectpathname,'r')
		try:
			myjson = json.load(fp)
		except Exception as e:
			fp.close()
			print str(e) + ' in parsing ' + projectpathname
			return 2
		
		fp.close()

		#
		# Process the list of commands
		#
	
		if type(myjson) is list:
			error = processeverything(myjson,solution)
		else:
			print 'Invalid json input file!'
			error = 2
		if error!=0:
			break

	return error
	
# 
# If called as a function and not a class,
# call my main
#

if __name__ == "__main__":
	sys.exit(main())
