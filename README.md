# plex_playlist_importer
Script to create playlists in plex from M3U files

Your plex account name will need to be added to the script and the path to plex sqlite file will probably need to be modified.

The script runs from command line with an .m3u filepath passed as an arg, the script get the tracks from the plex database, match them to what is in the M3U file and creates a plex playlist.

I have a plex server with M3U files stored on the same machine under linux and my M3U files are generated on a separate machine and so the script assumes that the filepaths in the playlist need the server name removed for the path to match what plex has stored. This will need to be modified for other users.

The script also removes an index (natural_sort_order) from a plex table, this seems to have no ill effects and I assume that plex rebuilds this index.
