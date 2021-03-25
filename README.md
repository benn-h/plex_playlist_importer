# plex_playlist_importer
Script to create playlists in plex from M3U files

I have a plex server with M3U files stored n the same machine under linux.

Run script from terminal passing .m3u filepath as an arg, the script get the tracks from the plex database, matches them to what is in the M3U file and creates a playlist.

My M3U files are generated on a separate machine and so the script assumes that the filepaths in the playlist need the server name removed for the path to match what plex has. This will need to be modified for other users.

The script also removes an index (natural_sort_order) from a plex table, this seems to have no ill effects and I assume that plex rebuilds this index.
