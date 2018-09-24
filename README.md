# PacTrack
A pacman hook implementation to convert Arch Linux package groups into metapackages

To install:
1. Copy PacTrack.py to a suitable location
2. Place pactrak.hook in /etc/pacman/hooks and update it to refer to the location of PacTrack.py
3. Add XferCommand = /path/to/PacTrack.py SYNC "%u" "%o" to pacman.conf

To configure:
1. Adjust the location of the dependency config files and repository in PacTrack.py
2. Create files in /etc/pactrack/dependencymods/<package name> to modify dependencies for individual packages at sync-time.
   Each simple text file simply contains a list of dependencies to add or remove from the package being synced, like so:
   
   /etc/pactrack/dependencymods/foo contains:
   
   +bar
   
   -another-bar
   
   
   This would add "bar" as a dependency for "foo" and remove "another-bar" as a dependency. Do not include version numbers as 
   part of the dependency changes, and consider all changes carefully.
    
