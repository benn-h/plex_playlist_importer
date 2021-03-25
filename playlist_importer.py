from pathlib import Path
import sys
import datetime
import sqlite3
import uuid
from collections import namedtuple
import argparse

"""
Script to create playlists in plex from M3U files.

NEEDS
    plex account name added as ACCOUNT_NAME var.
    path to com.plexapp.plugins.library.db added to PLEX_PATH list var if different to 
        what is already there.

Run from terminal on teh same maching that plex server is running on, passing the .m3u path as an arg.
"""

parser = argparse.ArgumentParser()
parser.add_argument('plist', help='.m3u filename for import to plex db')
args = parser.parse_args()

if not args.plist.endswith('.m3u'):
    print('m3u files only...')
    sys.exit()

# You will need to add your acount name here
ACCOUNT_NAME = 'add account name here'

# Modify list to be the path to your com.plexapp.plugins.library.db file
# The follwing is where I found it on Ubuntu 18
PLEX_PATH = [
    'var',
    'lib',
    'plexmediaserver',
    'Library',
    'Application Support',
    'Plex Media Server',
    'Plug-in Support',
    'Databases',
    'com.plexapp.plugins.library.db'
    ]

ACCOUNT_ID_SQL = (
    'SELECT id FROM accounts '
    f'WHERE name="{ACCOUNT_NAME}"'
    )

PLIST_ID_SQL = (
    'SELECT id FROM metadata_items '
    'WHERE title=? AND metadata_type = 15'
    )

UPDATE_MEDIA_ITEMS = (
    'UPDATE metadata_items SET '
    'duration=?, '
    'media_item_count=? '
    'WHERE id=?'
    )

DELETE_PLIST_GEN = (
    'DELETE FROM play_queue_generators '
    'WHERE playlist_id=?'
    )

TRACK_LIST_SQL = (
    'SELECT MP.file, MET.id, MP.duration '
    'FROM media_parts AS MP '
    'JOIN media_items AS MI ON MP.media_item_id=MI.id '
    'JOIN metadata_items AS MET ON MI.metadata_item_id=MET.id '
    'WHERE audio_codec = "mp3" '
    )

METADATA_ITEMS_ENTRY = {
    'metadata_type': 15,
    'index': 0,
    'extra_data': 'pv%3AdurationInSeconds=1&pv%3Aowner=1&pv%3AsectionIDs=13',
    'absolute_index': 10,
    }

PROJECT_DIR = Path.cwd()
DB_PATH = Path(PROJECT_DIR.root).joinpath(*PLEX_PATH)
M3U = PROJECT_DIR.joinpath(args.plist)

NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
NATSORT_INDEX = 'index_title_sort_naturalsort'
plist_item = namedtuple('list_item', ['metadata_item_id', 'order', 'duration'])


def read_m3u(filepath):
    """
    M3U to list of paths modified to match those strored in plex db.
    For me this meant stripping the network location from the start of the path
    """
    with open(filepath, 'r', encoding='cp1252') as file:
        result = file.read().splitlines()
    result = [
        (x.replace('\\', '/')[9:], i * 1000) for i, x in enumerate(result, 1)]
    return result


def insert_to_table(curr, table, vals_dict):
    """Insert to sqlite table from dict."""
    SQL= 'INSERT INTO `%s` (`%s`) VALUES (%s)'
    columns = '`, `'.join(vals_dict.keys())
    p_holders =', '.join('?'*len(vals_dict))
    curr.execute(SQL % (table, columns, p_holders), tuple(vals_dict.values()))


def get_or_create_plist_id(curr, title, count, duration):
    """
    Get or create playlist entry under title, makes entries to:
        metadata_items: plist details
        metadata_item_accounts: register playlist_id to account_id
        play_queue_generators: track_id's listed
    If playlist found then delete its track entries in play_queue_generators
    Args:
        curr: sqlite cursor
        title: string
        count: int
        duration: int
    Returns:
        playlist_id: int
    """
    result = curr.execute(PLIST_ID_SQL, (title, )).fetchone()
    if result:
        # Use existing playlist
        plist_id = result[0]
        # Update duration & track count in 'metadata_items'
        curr.execute(UPDATE_MEDIA_ITEMS, (duration, count, plist_id))
        # Delete existing tracks for playlist from 'play_queue_generators'
        curr.execute(DELETE_PLIST_GEN, (plist_id, ))
        return plist_id
    # If no existing playlist under title
    # Drop problematic index before inserting new record
    curr.execute(f'DROP INDEX IF EXISTS {NATSORT_INDEX}')
    entry = {
        'media_item_count': count,
        'title': title,
        'title_sort': title,
        'duration': duration,
        'added_at': NOW,
        'updated_at': NOW,
        'guid': 'com.plexapp.agents.none: //' + str(uuid.uuid1()),
        }
    insert_to_table(curr, 'metadata_items', {**METADATA_ITEMS_ENTRY, **entry})
    plist_id = curr.lastrowid
    # Associate playlist with account
    account_id = curr.execute(ACCOUNT_ID_SQL).fetchone()[0]
    entry = {'account_id': account_id, 'metadata_item_id': plist_id}
    insert_to_table(curr, 'metadata_item_accounts', entry)
    return plist_id


def prepare_tracklist(db_tracks, m3u_path):
    """
    Take m3u and get plex db id for each track
    Args:
        db_tracks
        m3u_path: str
    Returns:
        tracklist: list of named tuples
        count: int
        duration: int
        not_found: list
    """
    db_tracks = {path: (id, duration) for path, id, duration in db_tracks}
    plist = dict(read_m3u(m3u_path))
    not_found = list(set(plist) - set(db_tracks))
    tracklist = [
        plist_item(*db_tracks[path], order)
        for path, order in plist.items()
        if path not in not_found
        ]
    count = len(tracklist)
    duration = sum([x.duration for x in tracklist])
    return tracklist, count, duration, not_found


def main():
    """
    Takes playlist.m3u file passed as arg and cretaes playlist in plex database.
    Plex playlist will have same name as file, if plex playlist already exists
    with that name, the exiting plex playlist will have its contents deleted
    and replaced with the list in the file.
    """
    with sqlite3.connect(str(DB_PATH)) as conn:
        curr = conn.cursor()
        db_tracks = curr.execute(TRACK_LIST_SQL).fetchall()
        tracklist, count, duration, not_found = prepare_tracklist(db_tracks, M3U)
        if not_found:
            not_found = '\n'.join(not_found)
            print(f'Tracks were not found in the db:\n{not_found}')
            if input('continue? y/n').lower() != 'y':
                return None
        title = M3U.stem
        PlexPlaylistID = get_or_create_plist_id(curr, title, count, duration)
        conn.commit()
        # Insert playlist items to 'play_queue_generators'
        for track in tracklist:
            entry = {
                'playlist_id': PlexPlaylistID,
                'metadata_item_id': track.metadata_item_id,
                'order': track.order,
                'created_at':NOW,
                'updated_at':NOW,
                'uri':'',
                'extra_data': '',
                }
            insert_to_table(curr, 'play_queue_generators', entry)
        conn.commit()
    print('Done...')


if __name__ == "__main__":
    main()
