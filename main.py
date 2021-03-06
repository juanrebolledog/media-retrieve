#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pyItunes import *
import sqlite3
from optparse import OptionParser, OptionGroup
import shutil
from urlparse import urlparse
from urllib import unquote
import HTMLParser
import os
import subprocess
import logging
import json
import itertools


try:
    meta_dir = os.path.join(os.path.expanduser('~'), '.media-retrieve')

    if not os.path.isdir(meta_dir):
        os.makedirs(meta_dir)

    config_file = os.path.join(meta_dir, 'config.json')

    with open(config_file) as file:
        CONFIG = json.load(file)

except Exception as e:
    exit('You need to create a config file')


logger = logging.getLogger(__name__)

hdlr = logging.FileHandler(os.path.join(meta_dir, 'app.log'))
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


conn = sqlite3.connect(os.path.join(meta_dir, 'media-retrieve.db'))
conn.row_factory = sqlite3.Row
c = conn.cursor()


def parse_library(options):
    reset_db(options)
    logger.info('Reading Library')
    if options.verbose:
        print 'Reading Library'

    pl = XMLLibraryParser(CONFIG['app']['itunes_library'])
    l = Library(pl.dictionary)

    if options.verbose:
        print 'Tracks:'

    for song in l.songs:
        if song.kind == 'Audio Apple Lossless' or song.kind == 'Archivo de audio MPEG':
            h = HTMLParser.HTMLParser()
            location = h.unescape(song.location.decode('utf-8'))

            track = {
                'track': h.unescape(song.name.decode('utf-8')),
                'kind': song.kind,
                'filename': urlparse(unquote(location), allow_fragments=False).path
            }

            if song.album_artist:
                track['album_artist'] = h.unescape(song.album_artist.decode('utf-8'))
            else:
                track['album_artist'] = None

            if song.artist:
                track['artist'] = h.unescape(song.artist.decode('utf-8'))
            else:
                track['artist'] = None

            if song.album:
                track['album'] = h.unescape(song.album.decode('utf-8'))
            else:
                track['album'] = None

            logger.info(track['filename'])
            if options.verbose:
                try:
                    print 'Add :: {0} - {1} - {2}'.format(h.unescape(track['artist'].encode('utf-8')), h.unescape(track['album'].encode('utf-8')), h.unescape(track['track'].encode('utf-8')))
                except Exception as e:
                    print e
                    print track
                    exit()

            insert(track)

    conn.commit()
    return True


def insert(track):
    track = (track['artist'], track['album'], track['album_artist'], track['track'], track['filename'], track['kind'])
    c.execute('INSERT INTO tracks (artist, album, album_artist, track, filename, kind) VALUES (?, ?, ?, ?, ?, ?)', track)


def reset_db(options):
    logger.info('Resetting DB')
    if options.verbose:
        print 'Resetting DB'
    c.execute('DROP TABLE IF EXISTS tracks')
    c.execute('CREATE TABLE [tracks] ([id] INTEGER PRIMARY KEY AUTOINCREMENT, [artist] TEXT, [album] TEXT, [album_artist] TEXT, [track] TEXT, [filename] TEXT, [kind] TEXT);')


def find(options):
    conditions = {}
    values = ()
    cmd = 'SELECT * FROM tracks'

    if options.artist or options.album or options.track:
        cmd += ' WHERE'

        if options.artist:
            conditions['artist'] = options.artist.decode('utf-8')

        if options.album:
            conditions['album'] = options.album.decode('utf-8')

        if options.track:
            conditions['track'] = options.track.decode('utf-8')

    i = 0
    for field in conditions:
        if i == 0:
            cmd += ' {0}=?'.format(field)
        else:
            cmd += ' AND {0}=?'.format(field)
        i += 1
        values = values + (conditions[field],)

    c.execute(cmd, values)

    return c.fetchall()


def retrieve(options):
    songs = find(options)
    song_left = song_count = len(songs)

    for song in songs:
        song_left -= 1
        logger.info('[{1}/{2}] Copying "{0}"'.format(song['filename'], song_left, song_count))

        if options.verbose:
            print '[{1}/{2}] Copying "{0}"'.format(song['filename'], song_left, song_count)

        file_name = os.path.basename(song['filename'])

        if not os.path.isdir(CONFIG['app']['data_dir']):
            os.makedirs(CONFIG['app']['data_dir'])

        dir_name = os.path.join(CONFIG['app']['data_dir'], song['album'])
        final_name = os.path.join(dir_name, file_name)

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        if not os.path.exists(final_name) and not os.path.exists('{0}.mp3'.format(final_name)):

            try:
                if song['kind'] == 'Audio Apple Lossless':
                    cmd = [ CONFIG['app']['xld_bin'], '-f', 'mp3', '-o', '{0}.mp3'.format(final_name), song['filename'] ]
                    subprocess.call(cmd)
                else:
                    shutil.copyfile(song['filename'], final_name)
                if options.verbose:
                    logger.info('Copy OK')
                    print 'Copy OK'
            except:
                logger.warning('Copy failed for "{0}"'.format(song['filename']))
                if options.verbose:
                    print 'Copy failed'

        else:
            logger.info('Already exists, skipping.')
            if options.verbose:
                print 'Already exists, skipping.'


if __name__ == '__main__':

    parser = OptionParser()

    parser.add_option('-s', '--scan', action='store_true', dest='scan')
    parser.add_option('-x', '--reset', action='store_true', dest='reset')
    parser.add_option('-f', '--find', action='store_true', dest='find')

    group = OptionGroup(parser, "Find Options")
    group.add_option('-a', '--artist', action='store', type='string', dest='artist')
    group.add_option('-b', '--album', action='store', type='string', dest='album')
    group.add_option('-t', '--track', action='store', type='string', dest='track')
    parser.add_option_group(group)

    parser.add_option('-r', '--retrieve', action='store_true', dest='retrieve')
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose')
    (options, args) = parser.parse_args()

    if options.find:
        groups = []
        artists = []
        data = sorted(find(options), key=lambda t: t['artist'])

        for k, g in itertools.groupby(data, lambda t: t['artist']):
            for i, v in itertools.groupby(g, lambda a: a['album']):
                groups.append(list(v))

        for result in find(options):
            try:
                print 'Track: {0} | Artist: {1} | Album: {2}'.format(result['track'].encode('utf-8'), result['artist'].encode('utf-8'), result['album'].encode('utf-8'))
            except:
                pass

    elif options.scan:
        parse_library(options)

    elif options.reset:
        reset_db(options)

    elif options.retrieve:
        retrieve(options)
