#!/usr/bin/env python3

##############################################################################
#                                 PacTrack                                   #
#             Package Relationship Modification Tool For Pacman              #
##############################################################################


import sys
import re
import os.path
import shutil
import subprocess
import shlex
import stat
import pwd
import grp
from pathlib import Path

# TODO:
# on-exit and on-error cleanup of /tmp etc

# ----------------------------------------------------------------------------

PACTRACK_ETC_DIR="/etc/pactrack"
PACTRACK_LIB_DIR="/var/lib/pactrack"
PACMAN_LIB_DIR="/var/lib/pacman"
META_REPOSITORY_NAME="metapackages"
META_REPOSITORY="/home/"+META_REPOSITORY_NAME
# Note: TEMP_DIR will be recreated, and so must not point to a location with
#       data in it
TEMP_DIR="/tmp/pactrack"
DEBUG=False
# ----------------------------------------------------------------------------

def debugMsg(pMessage):
	"""
	Print a message if DEBUG_LEVEL is set high enough
	Arguments:
		pDebugLevel	--	the debug level to check against
		pMessage		--	the message to print	
	Returns true if the message was printed
	"""
	if DEBUG:
		print("[DEBUG] "+pMessage)
		return True
	return False
# ----------------------------------------------------------------------------

def copyFile(pSourceFile, pDestFile):
	"""
	Copy a file, ensuring that any existing destination file can be removed 
	first
	Arguments:
		pSourceFile	--	the source filename
		pDestFile		--	the destination filename
	Returns true if the file was successfully copied
	"""
	debugMsg("Copy file '"+pSourceFile+"' to '"+pDestFile+"'")
	if not os.path.isfile(pSourceFile):
		debugMsg("Failed to copy file '"+pSourceFile+"' to '"+pDestFile+"': source is not a file or does not exist") 
		return False
	if os.path.isfile(pDestFile):
		try:
			os.unlink(pDestFile)
		except:
			debugMsg("Failed to copy file '"+pSourceFile+"' to '"+pDestFile+"': failed to remove destination file") 
			return False
	try:
		shutil.copyfile(pSourceFile, pDestFile)
	except:
		debugMsg("Failed to copy file '"+pSourceFile+"' to '"+pDestFile+"': copying failed") 
		return False
	return True

# ----------------------------------------------------------------------------

def writeFile(pFilename, pContents):
	"""
	Write specified text to a file, backing the file up first and removing the 
	backup if the write succeeds
	Arguments:
		pFileName	-- the file to write to
		pContents	-- text content to write
	Returns true if the file was successfully written
	"""
	debugMsg("Writing to file '"+pFilename+"'")
	if not directoryRequired(os.path.dirname(pFilename), False):
		return False
	if os.path.exists(pFilename+".bak"):
		print("Warning: removing existing backup file '"+pFilename+".bak'")
		try:
			os.unlink(pFilename+".bak")
		except:
			print("Warning: failed to remove backup file '"+pFilename+".bak'")
		try:
			shutil.copyfile(pFilename, pFilename+".bak")
		except:
			print("Warning: could not create file '"+pFilename+".bak'")
	returnCode=True
	try:
		outputFile = open(pFilename, "w")
		outputFile.write(pContents)
		outputFile.close()
	except:
		debugMsg("Failed to write to file '"+pFilename+"'")
		returnCode=False
		try:
			outputFile.close()
		except:
			pass
	if os.path.exists(pFilename+".bak"):
		try:
			os.unlink(pFilename+".bak")
		except:
			print("Warning: failed to remove backup file '"+pFilename+".bak'")
	return returnCode

# ----------------------------------------------------------------------------

def directoryRequired(pPath, pMustBeEmpty):
	"""
	Create a directory if it does not exist (or remove and re-create if it must
	me empty)
	Arguments:
		pPath					--	directory path that must exist
		pMustBeEmpty	--	does the directory need to be empty?
	Returns true if the directory was (re-)created successfully
	"""
# TODO: permissions
	if pMustBeEmpty:
		if os.path.isdir(pPath):
			try:
				shutil.rmtree(TEMP_DIR)
			except:
				debugMsg("Failed to remove existing directory tree '"+TEMP_DIR+"'")
				return False
	try:
		debugMsg("Creating directory '"+pPath+"'")
		os.makedirs(pPath, exist_ok=True)
	except:
		print("Error: failed to create directory '"+pPath+"'")
		return False
	return True

# ----------------------------------------------------------------------------

def downloadFile(pURL, pOutputFile, pQuiet):
	"""
	Download a file from a given URL
	Arguments:
		pURL				--	the location to download from	
		pOutputFile	--	the location to save the file
		pQuiet			-- 	whether to supress output
	Returns true if the file was downloaded successfully
	"""
	debugMsg("Downloading URL '"+pURL+"' to file '"+pOutputFile+"'")	
	#TODO: see why shlex doesn't work to construct command line
	if pQuiet:
		process = subprocess.run("/usr/bin/wget -c -q --show-progress --passive-ftp -O \""+pOutputFile+"\" \""+pURL+"\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	else:
		process = subprocess.run("/usr/bin/wget -c -q --show-progress --passive-ftp -O \""+pOutputFile+"\" \""+pURL+"\"", shell=True)
	# Clean up any partial downloads on failure 
	# Particularly for zero-byte .sig files
	if process.returncode != 0:
		try:
			if os.path.isfile(pOutputFile):	
				os.unlink(pOutputFile)
		except:
			pass
		debugMsg("Failed to download URL '"+pURL+"' to file '"+pOutputFile+"'")	
		return False
	else:
		return True

# ----------------------------------------------------------------------------

def getPackageDependencyMods(pPackageName, pDependencyMods):
	"""
	Construct a list of user-specified changes to dependencies for a given 
	package
	Arguments:
		pPackageName					--	the package to find configuration for
		pDependencyMods	(out)	--	the list of changes required, if any	
	Returns true if there are modifications and they were read successfully
	"""
	if os.path.isfile(PACTRACK_ETC_DIR+"/dependencymods/"+pPackageName):
		debugMsg("Reading dependency modifications for package '"+pPackageName+"' from '"+PACTRACK_ETC_DIR+"/dependencymods/"+pPackageName+"'")
		try:
			packageDepFile = open(PACTRACK_ETC_DIR+"/dependencymods/"+pPackageName, "r")
			for line in packageDepFile:
				line = line.replace("\n", "").strip()
				if line.startswith("+") or line.startswith("-"):
					if line[1:].replace("\n", "").strip() != "":
						if line[1:] not in pDependencyMods:
							pDependencyMods[line[1:]] = line[0]
							debugMsg("Modify dependency '"+line[1:]+"', action: '"+line[0]+"'")
			packageDepFile.close()
		except:
			try:
				packageDepFile.close()
			except:
				pass
			debugMsg("Failed to read dependency modifications from '"+PACTRACK_ETC_DIR+"/dependencymods/"+pPackageName+"'")
			return False
		return True
	else:
		debugMsg("No dependency modifications file found for package '"+pPackageName+"'")
		return False

# ----------------------------------------------------------------------------

def processPackageDesc(pFilename, pPackageName, pGroupList):
	"""
	Process a specified package description file and edit it, removing groups 
	and applying user-specified rules to dependencies
	Arguments:
		pFileName						--	the file to process
		pPackageName	(out)	--	the name of the package according to the file
		pGroupList		(out)	--	returns the list of groups that the package 
														belonged to
	Returns true if descriptor file was changed successfully
	"""
	debugMsg("Processing package description in file '"+pFilename+"'")
	packageName = ""
	packageDeps = {}
	packageDepMods = {}
	processedPackageDesc = ""
	fileContents = []
	processingRequired = 0
	# Find package name and existing dependencies
	try:
		descFile = open(pFilename, "r")
		for line in descFile:
			# Keep (raw) file contents in memory
			fileContents.append(line)
			line = line.replace("\n", "").strip()
			if line != "":
				searchSection = re.search( r'^%(.*)%$', line, re.M|re.I)
				if searchSection:
					section = searchSection.group(1)
				else:
					if section == "NAME":
						# Set first package name we encounter (just for safety)
						packageName = line if packageName == "" else packageName
					elif section == "DEPENDS":
						# Construct current dependency list
						packageDeps[line] = "+"
					elif section == "GROUPS":
						pGroupList.append(line)
						# Package will need changes to remove group membership
						processingRequired = 1
		descFile.close()
	except:
		try:
			descFile.close()
		except:	
			pass
		debugMsg("Failed to read description file '"+pFilename+"'");
		return False
	# No package name: critical error
	debugMsg("Package name according to description file: '"+packageName+"'")
	if packageName == "":
		debugMsg("No package name found in description file '"+pFilename+"'");
		return False

	# Return package name (pPackageName is an array to be able to pass by ref)
	pPackageName.append(packageName)

	# Fetch user-configured package dependency changes, if any
	if getPackageDependencyMods(packageName, packageDepMods):
		if len(packageDeps) > 0:
			# Package will need changes as dependencies need to be modified
			processingRequired = 1
	
	if processingRequired == 1:
		# Apply final dependency modifications to existing dependency list
		# This overwrites existing actions with user-specified actions and
		# adds new (dependency, action) sets if specified
		for packageName in packageDepMods:
			packageDeps[packageName] = packageDepMods[packageName]

		# Process description file and apply changes
		for line in fileContents:
			rawLine = line
			line = line.replace("\n", "").strip()
			if line != "":
				searchSection = re.search( r'^%(.*)%$', line, re.M|re.I)
				if searchSection:
					section = searchSection.group(1)
					if section == "DEPENDS":
						processedPackageDesc += rawLine
						for packageName in packageDeps:
							if packageDeps[packageName] == "+":
								processedPackageDesc += packageName+"\n"
					elif section != "GROUPS":
						processedPackageDesc += rawLine
				else:
					if section != "DEPENDS":
						if section == "OPTDEPENDS":
							optPackageName = line.split(":")[0].strip()
							if optPackageName in packageDeps:
								if packageDeps[optPackageName] != "+":
									processedPackageDesc += rawLine
								else:
									debugMsg("Removing optional dependency '"+optPackageName+"' as it is now a hard dependency")
							else:
								processedPackageDesc += rawLine
						else: 
							processedPackageDesc += rawLine
			else:
				processedPackageDesc = processedPackageDesc+rawLine
		return writeFile(pFilename, processedPackageDesc)
	else:
		debugMsg("No processing required for description file '"+pFilename+"'")
		return False
  
# ----------------------------------------------------------------------------

def processDescDatabase(pPath, pGroupList):
	"""
	Processes an extracted package database, in the form pPath/<package names>/desc
	Arguments:
		pPath							--	the location of the database
		pGroupList	(out)	--	list of groups with nested package members
	Returns true if the database was processed successfully
	"""
	debugMsg("Processing package database at '"+pPath+"'")
	for directory in os.listdir(pPath):
		if os.path.isdir(pPath+"/"+directory):	
			if os.path.isfile(pPath+"/"+directory+"/desc"):
				groupList = []
				packageName = []
				if processPackageDesc(pPath+"/"+directory+"/desc", packageName, groupList):
					# If the package belongs to one or more groups, add it to the global
					# group membership list
					for groupName in groupList:
						if groupName in pGroupList:
							if not packageName[0] in pGroupList[groupName]:
								pGroupList[groupName].append(packageName[0])
						else:
							pGroupList[groupName] = [packageName[0]]
	return True

# ----------------------------------------------------------------------------

def readGroups(pFilename, pGroups, pGroupVersions):
	"""
	Reads the contents of a groups database file, parses it and returns the content
	Arguments:
		pFileName							--	location of the database file
		pGroups					(out)	--	nested array of groups and members
		pGroupVersions	(out)	--	list of groups containing current version numbers 
	Returns true if groups were read successfully
	"""
	if os.path.isfile(pFilename):
		debugMsg("Reading groups database '"+pFilename+"'")
		try:
			groupsFile = open(pFilename, "r")
			groupName = ""
			for line in groupsFile:
				line = line.replace("\n", "").strip()
				if line != "":
					if line.upper().startswith("G:"):
						groupVersion = line.split(":",2)[1]
						groupName = line.split(":",2)[2]
						if groupVersion != "":
							try:
								pGroupVersions[groupName] = int(groupVersion)
							except:
								print("Warning: could not parse group line '"+line+"' in database '"+pFilename+"'")
								# Force entire group to fail
								groupName = ""
						else:
							# Force entire group to fail
							groupName = ""
					elif line.upper().startswith("D:"):
						if groupName != "":
							repository = line.split(":",2)[1].strip()
							packageName = line.split(":",2)[2].strip()
							if repository != "" and packageName != "":
								if groupName not in pGroups:
									pGroups[groupName] = {}
								if repository not in pGroups[groupName]:
									pGroups[groupName][repository] = [packageName]
								else:
									pGroups[groupName][repository].append(packageName)
							else:
								print("Warning: could not parse dependency line '"+line+"' in database '"+pFilename+"'")
						else:
							print("Warning: dependency '"+line+"' is not part of a group in database '"+pFilename+"'")
					else:
						print("Warning: could not parse line '"+line+"' in database '"+pFilename+"'")
			groupsFile.close()
			for groupName in pGroups:
				for repository in pGroups[groupName]:
					pGroups[groupName][repository].sort()	
			return True
		except:
			try:
				groupsFile.close()
			except:
				pass
			debugMsg("Failed to read group database file '"+pFilename+"'")
			return False
	else:
		debugMsg("Group database file '"+pFilename+"' does not exist")
		return False

# ----------------------------------------------------------------------------

def writeGroups(pFilename, pGroups, pGroupVersions):
	"""
	Writes a group database at a specified location
	Arguments:
		pFilename				--	the location of the database	
		pGroups					--	list of groups and dependencies to write
		pGroupVersions	--	list of group versions to write
	Returns true if the database is written successfully
	"""
	debugMsg("Writing group database '"+pFilename+"'")
	contents = ""
	for groupName in pGroups:
		contents += "G:"+str(pGroupVersions[groupName])+":"+groupName+"\n"
		for repository in pGroups[groupName]:
			for packageName in pGroups[groupName][repository]:
				contents += "D:"+repository+":"+packageName+"\n"
	return writeFile(pFilename, contents)

# ----------------------------------------------------------------------------

def removeExistingPackageFiles(pPackageName):
	"""
	Removes any existing package files matching a given package name in the 
	metapackage repository
	Arguments:
		pPackageName	--	the package name to match
	Returns true if any existing packages are removed without error
	"""
	for packageFile in os.listdir(META_REPOSITORY):
		if os.path.isfile(META_REPOSITORY+"/"+packageFile):	
			matchObj = re.match(r'^meta-'+pPackageName+'-[0-9]+-1-x86_64.pkg.tar.xz$', packageFile, re.M|re.I)
			if matchObj:
				print("Warning: removing existing package file '"+packageFile+"'")
				try:
					os.unlink(META_REPOSITORY+"/"+packageFile)
				except:
					print("Error: failed to remove existing package file '"+packageFile+"'")
					return False
	return True

def copyRepositoryDatabase(pDatabaseName, pSourceDir, pDestDir):
	for dbFile in os.listdir(pSourceDir):
		if os.path.isfile(pSourceDir+"/"+dbFile):
			matchObj = re.match(r'^'+META_REPOSITORY_NAME+'\.(db|files).*', dbFile, re.M|re.I)
			if matchObj:
				if os.path.islink(pSourceDir+"/"+dbFile):	
					if os.path.isfile(pDestDir+"/"+dbFile):
						try:
							os.unlink(pDestDir+"/"+dbFile)
						except:
							print("Error: failed to remove existing file/symlink '"+pDestDir+"/"+dbFile+"'")
							return False	
					try:
						os.symlink(os.readlink(pSourceDir+"/"+dbFile), pDestDir+"/"+dbFile)
					except:
						print("Error: failed to create symlink '"+pDestDir+"/"+dbFile+"'")
						return False
				else:
					if not copyFile(pSourceDir+"/"+dbFile, pDestDir+"/"+dbFile):
						print("Error: failed to copy '"+pSourceDir+"/"+dbFile+"' to '"+pDestDir+"/"+dbFile+"'")
						return False	
	return True
	




def processGroups(pRepository, pGroupList):
	"""
	Process a given list of groups in a repository, creating metapackages
	Arguments:
		pRepository	--	the repository being processed
		pGroupList	--	list of groups and members in the repository
	Returns true if the groups were processed successfully
	"""
# TODO 
# It would be nice to have more atomic repository updates
#	- copy the repo.db (and associated files, symlinks) to a temp folder
# - run repo-add and repo-remove against the temp repo.db
# - if successful:
#		copy the temp repo.db (and files, symlinks) back to the repo
#		remove old package(s)
# 	copy in new package
	groups = {}
	groupVersions = {}
	groupsChanged = []
	groupsRemoved = []
	debugMsg("Processing groups for repository '"+pRepository+"'")
	uid = pwd.getpwnam("nobody").pw_uid
	gid = grp.getgrnam("nobody").gr_gid
	# Fetch the groups database
	if not readGroups(PACTRACK_LIB_DIR+"/groups.db", groups, groupVersions):
		print("Warning: could not open database '"+PACTRACK_LIB_DIR+"/groups.db'")
	# Copy across the repository db
	if not copyRepositoryDatabase(META_REPOSITORY_NAME, META_REPOSITORY, TEMP_DIR+"/repository"):
		return False
	# Clear groups in database and not in the current group list and mark them as changed
	for groupName in groups:
		if pRepository in groups[groupName]:
			if groupName not in pGroupList:
				groups[groupName][pRepository] = []
				groupsRemoved.append(groupName)
				debugMsg("Group '"+groupName+"' no longer exists")
	
	# Amend all group dependencies according to user-specified configuration
	for groupName in pGroupList:
		dependencyMods = {}
		getPackageDependencyMods("meta-"+groupName, dependencyMods)
		for packageMod in dependencyMods:
			if dependencyMods[packageMod] == "+":
				if packageMod not in pGroupList[groupName]:
					debugMsg("Adding package '"+packageMod+"' as a dependency for group '"+groupName+"'");
					pGroupList[groupName].append(packageMod)
			elif dependencyMods[packageMod] == "-":
				if packageMod in pGroupList[groupName]:
					debugMsg("Removing package '"+packageMod+"' as a dependency for group '"+groupName+"'");
					tempDepList = []
					for dep in pGroupList[groupName]:
						if dep != packageMod:
							tempDepList.append(dep)
					pGroupList[groupName] = tempDepList

	# Compare current group list against database
	for groupName in pGroupList:
		pGroupList[groupName].sort()
		if groupName in groups:
			if pRepository not in groups[groupName]:
				groups[groupName][pRepository] = []
			if pGroupList[groupName] != groups[groupName][pRepository]:
				groups[groupName][pRepository] = pGroupList[groupName]
				groupsChanged.append(groupName)			
				debugMsg("Group '"+groupName+"' has changed")
		else:
			groups[groupName] = {}
			groups[groupName][pRepository] = pGroupList[groupName]
			groupsChanged.append(groupName)

	# Process removed groups
	for groupName in groupsRemoved:
		if removeExistingPackageFiles(groupName):
			process = subprocess.run("/usr/bin/repo-remove "+TEMP_DIR+"/repository/"+META_REPOSITORY_NAME+".db.tar.gz meta-"+groupName, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			if process.returncode != 0:
				print("Warning: failed to remove metapackage 'meta-"+groupName+"' for missing group '"+groupName+"' from repository")

	buildFailure = False
	# Build changed groups
	for groupName in groupsChanged:
		# Increment / set versions
		if groupName in groupVersions:
			groupVersions[groupName] += 1
		else:
			groupVersions[groupName] = 1
		print("Creating metapackage 'meta-"+groupName+"', version "+str(groupVersions[groupName]))
		# Set up list of dependencies for the metapackage
		groupDependencies = []
		for repository in groups[groupName]:
			for package in groups[groupName][repository]:
				groupDependencies.append(package)
		groupDependencies.sort()
		# Set up build environment
		directoryRequired(TEMP_DIR+"/build/meta-"+groupName, True)
		# Create the PKGBUILD
		if createMetaPKGBUILD(TEMP_DIR+"/build/meta-"+groupName+"/PKGBUILD", "meta-"+groupName, str(groupVersions[groupName]), groupName, groupDependencies):
			# change build directory ownership to "nobody" so that makepkg has permissions
			os.chown(TEMP_DIR+"/build/meta-"+groupName, uid, gid)
			# Build the package
			process = subprocess.run("sudo -u nobody /usr/bin/makepkg --nodeps", shell=True, cwd=TEMP_DIR+"/build/meta-"+groupName, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			if process.returncode != 0:
				buildFailure = True
				print("Error: failed to build metapackage 'meta-"+groupName+"'")
			else:
				packageFilename = "meta-"+groupName+"-"+str(groupVersions[groupName])+"-1-x86_64.pkg.tar.xz"
				# Remove existing package from temporary repository
				process = subprocess.run("/usr/bin/repo-remove "+TEMP_DIR+"/repository/"+META_REPOSITORY_NAME+".db.tar.gz meta-"+groupName, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				if process.returncode != 0:
					# This is only a failure if the package was actually in the database to start with
					if groupVersions[groupName] > 1:
						buildFailure = True
						print("Error: failed to remove metapackage 'meta-"+groupName+"' from temporary repository")
				if not buildFailure:
					# Add new package to temporary repository
					process = subprocess.run("/usr/bin/repo-add "+TEMP_DIR+"/repository/"+META_REPOSITORY_NAME+".db.tar.gz "+TEMP_DIR+"/build/meta-"+groupName+"/meta-"+groupName+"-"+str(groupVersions[groupName])+"-1-x86_64.pkg.tar.xz", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
					if process.returncode != 0:
						buildFailure = True
						print("Error: failed to add metapackage 'meta-"+groupName+"' to temporary repository")

	if not buildFailure:
		# Operate on actual repository
		# Atomicity breaks down at this point; just try to copy as much as possible
		if not copyRepositoryDatabase(META_REPOSITORY_NAME, TEMP_DIR+"/repository", META_REPOSITORY):
			print("Error: failed to copy temporary repository database in '"+TEMP_DIR+"/repository' to repository '"+META_REPOSITORY+"'")

		for groupName in groupsChanged:
			packageFilename = "meta-"+groupName+"-"+str(groupVersions[groupName])+"-1-x86_64.pkg.tar.xz"
			if not removeExistingPackageFiles(groupName):
				print("Warning: failed to remove existing packages for 'meta-"+groupName+"' in repository '"+META_REPOSITORY+"'")
			if not copyFile(TEMP_DIR+"/build/meta-"+groupName+"/"+packageFilename, META_REPOSITORY+"/"+packageFilename):
				print("Error: failed to copy package '"+TEMP_DIR+"/build/meta-"+groupName+"/"+packageFilename+"' to '"+META_REPOSITORY+"/"+packageFilename+"'")
		return writeGroups(PACTRACK_LIB_DIR+"/groups.db", groups, groupVersions)
	else:
		print("Error: not updating repository '"+META_REPOSITORY+"' due to build failure")
		return False


# ----------------------------------------------------------------------------

def processDatabase(pURL, pOutputFile):
	"""
	Process a database download request
	Arguments:
		pURL				--	the remote location of the database
		pOutputFile	--	the destination file for the database
	Returns true if the database is successfully processed
	"""
	groupList = {}
	debugMsg("Processing database from '"+pURL+"'")
	# Ensure the environment is set up
	if not (directoryRequired(PACTRACK_LIB_DIR, False) and directoryRequired(META_REPOSITORY, False)):
		return False
	if not (directoryRequired(TEMP_DIR, True) and directoryRequired(TEMP_DIR+"/database", True) and directoryRequired(TEMP_DIR+"/build", True) and directoryRequired(TEMP_DIR+"/repository", True)):
		return False
	# Download the database file
	repositoryName = os.path.basename(pOutputFile).split(".", 1)[0].strip()
	debugMsg("Repository name is '"+repositoryName+"'")
	if not downloadFile(pURL, TEMP_DIR+"/"+repositoryName+".tar", False):
		return False
	# Unpack the database file
	debugMsg("Unpacking database '"+TEMP_DIR+"/"+repositoryName+".tar' to '"+TEMP_DIR+"/database'")
	process = subprocess.run("/usr/bin/tar -C "+TEMP_DIR+"/database -xvf "+TEMP_DIR+"/"+repositoryName+".tar" , shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	if process.returncode != 0:
		return False
	debugMsg("Processing database '"+TEMP_DIR+"/database'")
	if not processDescDatabase(TEMP_DIR+"/database", groupList):
		return False
	# Re-pack the database file
	debugMsg("Packing database '"+TEMP_DIR+"/database' to '"+TEMP_DIR+"/processed-"+repositoryName+".tar'")
	process = subprocess.run("/usr/bin/tar --transform='s/\.\///' -cvf "+TEMP_DIR+"/processed-"+repositoryName+".tar -C "+TEMP_DIR+"/database ./" , shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	if process.returncode != 0:
		return False
	if processGroups(repositoryName, groupList):		
		return copyFile(TEMP_DIR+"/processed-"+repositoryName+".tar", pOutputFile)
	else:
		return False

# ----------------------------------------------------------------------------

def createMetaPKGBUILD(pFileName, pPackageName, pVersion, pGroupName, pDependencies):
	"""
	Create a specified meta package PKGBUILD with given dependencies
	Arguments:
		pFileName 		-- the file to create
		pPackageName 	-- ArchLinux package name
		pVersion			-- ArchLinux package version
		pGroupName		-- Pacman group that the PKGBUILD represents
		pDependencies	-- List of dependencies for the meta package
	Returns true if the file is created successfully
	"""
	contents = "pkgname="+pPackageName+"\n"
	contents += "pkgver="+pVersion+"\n"
	contents += "pkgrel=1\n"
	contents += "pkgdesc=\"Metapackage for group '"+pGroupName+"' (generated by PacTrack)\"\n"
	contents += "license=('GPL')\n"
	contents += "arch=('x86_64')\n"
	contents += "depends=("
	firstDependency = True
	for dependency in pDependencies:
		if firstDependency:
			firstDependency = False
			contents += "'"+dependency+"'"
		else:
			contents += " '"+dependency+"'"
	contents += ")\n"
	contents += "package() {\n"
	contents += "  echo null > /dev/null\n"
	contents += "}\n"
	return writeFile(pFileName, contents)
	
# ----------------------------------------------------------------------------

def processSync(pURL, pOutputFile):
	"""
	Process the synchronisation action
	Arguments:
		pURL				--	the URL to download
		pOutputFile	--	the destination file
	Returns true if processing is successful
	"""
	debugMsg("Downloading URL '"+pURL+"' to output file '"+pOutputFile+"'")
	if pURL.upper().startswith("CP:"):
		sourceFile = pURL.split(":", 1)[1].strip()
		debugMsg("Copying file '"+sourceFile+"' to '"+pOutputFile+"'")
		if pURL.endswith(".sig") and os.path.isfile(sourceFile):
			print("Warning: repository is signed - ensure configuration does not require this")
			return False
		else:
			return copyFile(sourceFile, pOutputFile)
	elif pOutputFile.startswith(PACMAN_LIB_DIR+"/sync"):
		debugMsg("Intercepted database download")
		if pURL.endswith(".sig"):
			if directoryRequired(TEMP_DIR, True):
				if downloadFile(pURL, TEMP_DIR+"/repo.sig", True):	
					print("Warning: repository is signed - ensure configuration does not require this")
			return False
		else:
			return processDatabase(pURL, pOutputFile)
	else:	
		return downloadFile(pURL, pOutputFile, False)
	return True

# ----------------------------------------------------------------------------

def printUsage():
	"""
	Print program usage summary
	"""
	print("Usage: PacTrack <ACTION> [ARGUMENTS]\n")
	print("Possible actions:\n")
	print("ACTION		ARGUMENTS					DESCRIPTION")
	print("------		---------					-----------")
	print("LOCAL		<none>						Process the local Pacman database")
	print("SYNC			URL, OUTPUTFILE		Download URL to OUTPUTFILE")

# ----------------------------------------------------------------------------

def main(pArgs):
	"""
	Main routine
	Arguments:
		pArgs	--	raw program arguments
	"""
	returnCode = True
	if len(pArgs) < 2:
		print("Error: no action was specified")
		printUsage()
		returnCode = False
	if pArgs[1].upper() == "LOCAL":
		groupList = {}
		return processDescDatabase(PACMAN_LIB_DIR+"/local", groupList)
	elif pArgs[1].upper() == "SYNC":
		if len(pArgs) < 4:
			print("Error: incomplete arguments supplied for this action")
			printUsage()
			returnCode = False
		returnCode = processSync(pArgs[2], pArgs[3])
	else:
		print("Unknown action '"+pArgs[1]+"'")
		printUsage()
		returnCode = False

	# Clean up temporary directory
#	if os.path.isdir(TEMP_DIR):
#		try:
#			shutil.rmtree(TEMP_DIR)
#		except:
#			print("Warning: failed to clean up temporary directory '"+TEMP_DIR+"'")

	return returnCode

# ----------------------------------------------------------------------------

if not main(sys.argv):
	sys.exit(1)
else:
	sys.exit(0)
     

