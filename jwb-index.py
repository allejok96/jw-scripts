#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import os
import argparse
import sys
import hashlib
import subprocess
import time
import re

pj = os.path.join


def validate_lang(code=None):
    """Print out a language code list or check if the code is in the list"""

    url = 'https://mediator.jw.org/v1/languages/E/web'

    with urllib.request.urlopen(url) as response:
        response = json.load(response)

        if code is None:
            # Print table of language codes
            print('language codes:', file=sys.stderr)
            for lang in sorted(response['languages'], key=lambda x: x['name']):
                print('{:>3}  {:<}'.format(lang['code'], lang['name']), file=sys.stderr)
        else:
            # Check if the code is valid
            for lang in response['languages']:
                if lang['code'] == code:
                    return True

            print(code + ': invalid language code')


def parse_vod(cat):
    """Download JSON and do stuff"""

    url = 'https://mediator.jw.org/v1/categories/{0}/{1}?detailed=1'.format(option.lang, cat)
    with urllib.request.urlopen(url) as response:
        response = json.load(response)

        if 'status' in response and response['status'] == '404':
            print('no such category or language', file=sys.stderr)
            quit()

        # Set output destination based on current category
        cat = response['category']['key']
        name = response['category']['name']
        if not option.quiet:
            print('{} ({})'.format(cat, name), file=sys.stderr)
        output.set_cat(cat, name)

        # Add subcategories to the queue
        if 'subcategories' in response['category']:
            for s in response['category']['subcategories']:
                output.save_subcat(s['key'], s['name'])
                if s['key'] not in queue:
                    queue.append(s['key'])

        # Output media data to current destination
        if 'media' in response['category']:
            for media in response['category']['media']:
                video = get_best_video(media['files'])

                m = Media()
                m.url = video['progressiveDownloadURL']
                m.name = media['title']

                if 'firstPublished' in media:
                    if option.since:
                        published = re.sub('\.[0-9]+Z$', '', media['firstPublished'])
                        published = time.strptime(published, '%Y-%m-%dT%H:%M:%S')
                        published = time.mktime(published)
                        if published < option.since:
                            continue

                    m.date = media['firstPublished']
                if 'checksum' in video:
                    m.md5 = video['checksum']
                if 'filesize' in video:
                    m.size = video['filesize']

                m.file = download_media(m, output.media_dir)

                output.save_media(m)


def get_best_video(files):
    videos = sorted([x for x in files if x['frameHeight'] <= option.quality],
                    reverse=True,
                    key=lambda v: v['frameWidth'])
    videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == option.subtitles)
    return videos[0]


def truncate_file(file, string=''):
    """Create a file and its parent directories"""

    d = os.path.dirname(file)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    # Don't truncate non-empty files
    if os.path.exists(file) and os.stat(file).st_size != 0:
        return

    with open(file, 'w') as f:
        f.write(string)


def download_media(media, directory=None):
    """Download media and check it"""

    if directory is None:
        directory = option.work_dir

    os.makedirs(directory, exist_ok=True)

    base = urllib.parse.urlparse(media.url).path
    base = os.path.basename(base)
    file = pj(directory, base)

    # Only try resuming and downloading once
    resumed = False
    downloaded = False

    while True:

        if os.path.exists(file):

            fsize = os.path.getsize(file)

            if media.size is None:
                return file

            # File size is OK, check MD5
            elif fsize == media.size:
                if option.checksum is False or media.md5 is None:
                    return file
                elif md5(file) == media.md5:
                    return file
                else:
                    print('deleting: {}, checksum mismatch'.format(base), file=sys.stderr)
                    os.remove(file)

            # File is smaller, try to resume download once
            elif fsize < media.size and not resumed and option.download:
                resumed = True
                if not option.quiet:
                    print('resuming: {} ({})'.format(base, media.name), file=sys.stderr)
                curl(media.url, file, resume=True)
                continue

            # File size is wrong, delete it
            else:
                print('deleting: {}, size mismatch'.format(base), file=sys.stderr)
                os.remove(file)

        # Download whole file once
        if not downloaded and option.download:
            downloaded = True
            if not option.quiet:
                print('downloading: {} ({})'.format(base, media.name), file=sys.stderr)
            curl(media.url, file)
            continue

        # Already tried to download and didn't pass tests
        break


def md5(file):
    """MD5 a file"""

    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def curl(url, file, resume=False):
    """Throttled download of a file with curl"""

    proc = ['curl', url, '--silent', '-o', file]
    if resume:
        proc.append('--continue-at')
        proc.append('-')
    if option.rate_limit != 0:
        proc.append('--limit-rate')
        proc.append(option.rate_limit)

    subprocess.run(proc, stderr=sys.stderr)


class Media:
    """Object with media info"""
    
    def __init__(self):
        self.url = None
        self.name = None
        self.md5 = None
        self.time = None
        self.size = None
        self.file = None


class OutputStdout:
    """Simply output to stdout"""

    def __init__(self):
        self.media_dir = option.work_dir

    def save_media(self, media):
        if media.file is not None:
            print(os.path.relpath(media.file, option.work_dir))
        else:
            print(media.url)

    def save_subcat(self, cat, name):
        return

    def set_cat(self, cat, name):
        return


class OutputM3U(OutputStdout):
    """Create a M3U playlist tree"""

    def __init__(self):
        super().__init__()
        self._output_file = None
        self._inserted_subdir = ''
        self.file_ending = '.m3u'
        self.media_dir = pj(option.work_dir, option.subdir)

    def save_media(self, media):
        # Write media to a playlist

        if media.file is not None:
            source = pj('.', option.subdir, os.path.basename(media.file))
        else:
            source = media.url

        self.write_to_file(source, media.name)

    def save_subcat(self, cat, name):
        # Write a link to another playlist to the current playlist

        name = name.upper()

        source = pj('.', self._inserted_subdir, cat + self.file_ending)
        self.write_to_file(source, name)

    def set_cat(self, cat, name):
        # Switch to a new file

        if self._output_file is None:
            # The first time THIS method runs:
            # The current (first) file gets saved outside the subdir,
            # all other data (later files) gets saved inside the subdir,
            # so all paths in the current file must have the subdir prepended.
            self._inserted_subdir = option.subdir
            self._output_file = pj(option.work_dir, name + self.file_ending)
        else:
            # The second time and forth:
            # Don't prepend the subdir no more
            # Save data directly in the subdir
            self._inserted_subdir = ''
            self._output_file = pj(option.work_dir, option.subdir, cat + self.file_ending)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    def write_to_m3u(self, source, name, file=None):
        # Write something to a M3U file

        if file is None:
            file = self._output_file

        truncate_file(file, string='#EXTM3U\n')
        with open(file, 'a') as f:
            f.write('#EXTINF:0,' + name + '\n' + source + '\n')

    write_to_file = write_to_m3u


class OutputM3UCompat(OutputM3U):
    """Create multiple M3U playlists"""

    def __init__(self):
        super().__init__()
        self.file_ending = '.m3u'
        self._output_file = None

    def set_cat(self, cat, name):
        # Switch to a new file

        self._output_file = pj(option.work_dir, cat + ' - ' + name + self.file_ending)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    def save_subcat(self, cat, name):
        # Don't link to other playlists to not crash media players
        # hence the "compat" part of M3UCompat 
        pass


class OutputHTML(OutputM3U):
    """Create a HTML file"""

    def __init__(self):
        super().__init__()
        self.file_ending = '.html'
        self._output_file = None

    def write_to_html(self, source, name, file=None):
        # Write a link to a HTML file

        if file is None:
            file = self._output_file

        truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>')

        with open(file, 'a') as f:
            f.write('\n<a href="{0}">{1}</a><br>'.format(source, name))

    write_to_file = write_to_html


class OutputFilesystem(OutputStdout):
    """Create a directory structure"""

    def __init__(self):
        super().__init__()
        self._output_dir = None
        self.media_dir = pj(option.work_dir, option.subdir)

    def set_cat(self, cat, name):
        # Create a directory for saving stuff

        first = self._output_dir is None

        self._output_dir = pj(option.work_dir, option.subdir, cat)

        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        # First time: create link outside subdir
        if first:
            link = pj(option.work_dir, name)
            if not os.path.lexists(link):
                dir_fd = os.open(self._output_dir, os.O_RDONLY)
                # Note: the source will be relative
                source = pj(option.subdir, cat)
                os.symlink(source, link, dir_fd=dir_fd)

    def save_subcat(self, cat, name):
        # Create a symlink to a directory

        dir_ = pj(option.work_dir, option.subdir, cat)
        if not os.path.exists(dir_):
            os.makedirs(dir_)

        source = pj('..', cat)
        link = pj(self._output_dir, name)

        if not os.path.lexists(link):
            dir_fd = os.open(self._output_dir, os.O_RDONLY)
            os.symlink(source, link, dir_fd=dir_fd)

    def save_media(self, media):
        # Create a symlink to some media

        if media.file is None:
            return

        source = pj('..', os.path.basename(media.file))
        ext = os.path.splitext(media.file)[1]
        link = pj(self._output_dir, media.name + ext)

        if not os.path.lexists(link):
            dir_fd = os.open(self._output_dir, os.O_RDONLY)
            os.symlink(source, link, dir_fd=dir_fd)


parser = argparse.ArgumentParser(prog='jwb-index.py', usage='%(prog)s [options] [DIR]',
                                 description='Index or download media from tv.jw.org')
# TODO
parser.add_argument('--config')

# TODO
parser.add_argument('--clean', action='store_true')

parser.add_argument('--quiet', action='store_true')

parser.add_argument('--mode', default='stdout', choices=['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
                    help='output mode')

parser.add_argument('--lang', nargs='?', default='E',
                    help='language code')

parser.add_argument('--category', default='VideoOnDemand', dest='category',
                    help='category/section to index')

parser.add_argument('--latest', action='store_const', const='LatestVideos', dest='category')

parser.add_argument('--quality', default=720, type=int, choices=[240, 360, 480, 720],
                    help='maximum video quality')

parser.add_argument('--subtitles', action='store_true')

parser.add_argument('--no-subtitles', action='store_false', dest='subtitles',
                    help='prefer un-subtitled videos')

parser.add_argument('--download', action='store_true',
                    help='download media')

parser.add_argument('--limit-rate', default='1M', dest='rate_limit')

parser.add_argument('--since', metavar='YYYY-MM-DD')

parser.add_argument('--checksum', action='store_true',
                    help='check md5 checksum')

parser.add_argument('--no-checksum', action='store_false',
                    help='check md5 checksum')

# TODO
parser.add_argument('--timestamp', action='store_true')

parser.add_argument('--no-timestamp', action='store_false', dest='timestamp')

parser.add_argument('work_dir', nargs='?', default=os.getcwd(), metavar='DIR',
                    help='directory to save data in')

option = parser.parse_args()


# Check language code validity
validate_lang(option.lang) or exit()
option.subdir = pj('jwb-' + option.lang)

# Check date option validity
if option.since:
    try:
        option.since = time.mktime(time.strptime(option.since, '%Y-%m-%d'))
    except ValueError:
        print('wrong date format')
        exit()

# Set the output mode
modes = {'stdout': OutputStdout,
         'm3u': OutputM3U,
         'm3ucompat': OutputM3UCompat,
         'filesystem': OutputFilesystem,
         'html': OutputHTML}
output = modes[option.mode]()


# Begin with the first category
# (more categories will be added as we move on)
queue = [option.category]

for c in queue:
    parse_vod(c)
