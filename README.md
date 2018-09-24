# PacTrack
An ALPM hook implementation to convert Arch Linux package groups into metapackages

To use:
1. Copy PacTrack.py to a suitable location
2. Place pactrak.hook in /etc/pacman/hooks and update it to refer to the location of PacTrack.py
3. Add XferCommand = /path/to/PacTrack.py SYNC "%u" "%o" to pacman.conf
