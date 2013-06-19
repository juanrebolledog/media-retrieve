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


try:
    from config import CONFIG
except Exception as e:
    exit('You need to create a config file')


logger = logging.getLogger(__name__)
hdlr = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


conn = sqlite3.connect('media-retrieve.db')
c = conn.cursor()


def parse_library(options):
    #reset_db(options)
    logger.info('Reading Library')
    if options.verbose:
        print 'Reading Library'

    pl = XMLLibraryParser(CONFIG['app']['itunes_library'])
    l = Library(pl.dictionary)

    if options.verbose:
        print 'Tracks:'
    for song in l.songs:

        h = HTMLParser.HTMLParser()
        location = h.unescape(song.location)
        
        track = {
            'track': song.name,
            'artist': song.artist,
            'album_artist': song.album_artist,
            'album': song.album,
            'kind': song.kind,
            'location': urlparse(unquote(location), allow_fragments=False).path
        }

        options.artist = track['artist']
        options.album = track['album']
        options.track = track['track']

        if find(options):
            logger.info(track['location'])
            if options.verbose:
                print track['location']

            insert(track)
    return True


def insert(track):
    track = (track['artist'], track['album'], track['album_artist'], track['track'], track['location'], track['kind'])
    c.execute('INSERT INTO tracks (artist, album, album_artist, track, filename, kind) VALUES (?, ?, ?, ?, ?)', track)


def reset_db(options):
    logger.info('Resetting DB')
    if options.verbose:
        print 'Resetting DB'
    db.drop_collection(tracks)


def find(options):

    conditions = ()
    cmd = 'SELECT * FROM tracks'
    query = []

    if options.artist:
        qstring = ('artist', options.artist)
        query.append(qstring)
        conditions = conditions + qstring

    if options.album:
        qstring = ('album', options.album)
        query.append(qstring)
        conditions = conditions + qstring

    if options.track:
        qstring = ('track', options.track)
        query.append(qstring)
        conditions = conditions + qstring
    
    if len(query) > 0:
        cmd += ' WHERE'
        for i, option in query:
            if i != 0:
                cmd += ' AND'
            cmd += ' ?=?'

    print cmd
    result = c.execute(cmd, conditions)



    if c.rowcount > 0:
        return result

    return False


def retrieve(options):
    songs = find(options)
    song_left = song_count = songs.count()

    def shellquote(s):
        return s.replace(" ", "\\ ").replace("(", "\(").replace(")", "\)").replace("&", "\&")

    for song in songs:
        song_left -= 1
        logger.info('[{1}/{2}] Copying "{0}"'.format(song['location'], song_left, song_count))
        if options.verbose:
            print '[{1}/{2}] Copying "{0}"'.format(song['location'], song_left, song_count)
        file_name = os.path.basename(song['location'])

        if not os.path.isdir(CONFIG['app']['data_dir']):
            os.makedirs(CONFIG['app']['data_dir'])

        dir_name = os.path.join(CONFIG['app']['data_dir'], song['album'])
        final_name = os.path.join(dir_name, file_name)

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        if not os.path.exists(final_name) and not os.path.exists('{0}.mp3'.format(final_name)):
            
            try:
                if song['kind'] == 'Audio Apple Lossless':
                    cmd = [ CONFIG['app']['xld_bin'], '-f', 'mp3', '-o', '{0}.mp3'.format(final_name), song['location'] ]
                    subprocess.call(cmd)
                else:
                    shutil.copyfile(song['location'], final_name)
                if options.verbose:
                    logger.info('Copy OK')
                    print 'Copy OK'
            except Exception as e:
                logger.warning('Copy failed for "{0}"'.format(song['location']))
                if options.verbose:
                    print 'Copy failed for "{0}"'.format(song['location'])
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
        for result in find(options):
            print 'Track: {0} | Artist: {1} | Album: {2}'.format(result['track'], result['artist'], result['album'])
    elif options.scan:
        parse_library(options)
    elif options.reset:
        reset_db(options)
    elif options.retrieve:
        retrieve(options)
