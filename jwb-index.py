#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import os
import argparse
import sys
import hashlib

pj = os.path.join


def md5(file):
    """MD5 a file"""

    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def download_media(url, directory=None, size=None, checksum=None, resume=False):
    """Download a file to a directory"""

    if directory is None:
        directory = option.work_dir

    os.makedirs(directory, exist_ok=True)

    base = urllib.parse.urlparse(url).path
    base = os.path.basename(base)
    file = pj(directory, base)

    for loop in range(0, 2):

        request = None

        if os.path.exists(file):

            # If file is smaller, try to resume download once.
            fsize = os.path.getsize(file)
            if size is not None and fsize < size:
                print('Resuming ' + url, file=sys.stderr)
                request = urllib.request.Request(url, headers={'Range': 'bytes={0}-' + fsize + '-'})
            elif fsize == size:
                if checksum and checksum is not None:
                    if not checksum == md5(file):
                        os.remove(file)
                        print(file + ': deleting, checksum mismatch', file=sys.stderr)
            else:
                os.remove(file)
                print(file + ': deleting, size mismatch', file=sys.stderr)


        if request is None:
            print('Downloading ' + file, file=sys.stderr)
            request = url


        urllib.request.urlretrieve(request, file)

    if os.path.exists(file):
        if size is not None and not os.path.getsize(file) == size:
            err = 'size mismatch'
        elif checksum is not None and not md5(file) == checksum:
            err = 'checksum mismatch'
        else:
            return True

        print(file + ': deleting corrupted file, ' + err, file=sys.stderr)
        os.remove(file)
        return False

    return file


def truncate_file(file, string='', overwrite=False):
    """Create a file and its parent directories"""

    d = os.path.dirname(file)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    if overwrite:
        pass
    elif os.path.exists(file) and os.stat(file).st_size == 0:
        # Truncate empty files
        pass
    else:
        return

    with open(file, 'w') as f:
        f.write(string)


def check_file(file, size, checksum):
    """Validate a file and delete invalid ones"""




class Media:
    """Object with media info"""
    
    def __init__(self):
        self.url = None
        self.name = None
        self.checksum = None
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
            # The first time this method runs:
            # The current (first) file gets saved outside the subdir,
            # all other data (later files) gets saved inside the subdir,
            # so all paths in the current file must have the subdir prepended.
            self._inserted_subdir = option.subdir
            self._output_file = pj(option.work_dir, cat + self.file_ending)
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

        truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>\n')

        with open(file, 'a') as f:
            f.write('<a href="{0}">{1}</a><br>'.format(source, name))

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


def parse_vod(cat):
    """Download JSON and do stuff"""

    history.add(cat)

    url = 'https://mediator.jw.org/v1/categories/{0}/{1}?detailed=1'.format(option.lang, cat)
    with urllib.request.urlopen(url) as response:
        response = json.load(response)

        if 'status' in response and response['status'] == '404':
            print('No such category', file=sys.stderr)
            quit()

        # Set output destination based on current category
        cat = response['category']['key']
        name = response['category']['name']
        print('{0} - {1}'.format(cat, name), file=sys.stderr)
        output.set_cat(cat, name)

        # Add subcategories to the queue
        if 'subcategories' in response['category']:
            for s in response['category']['subcategories']:
                if s['key'] not in history:
                    output.save_subcat(s['key'], s['name'])
                    queue.add(s['key'])

        # Output media data to current destination
        if 'media' in response['category']:
            for media in response['category']['media']:
                video = get_best_video(media['files'])

                m = Media()
                m.url = video['progressiveDownloadURL']
                m.name = media['title']

                if 'firstPublished' in media:
                    m.date = media['firstPublished']
                if 'checksum' in video:
                    m.checksum = video['checksum']
                if 'size' in video:
                    m.size = video['size']

                if option.download:
                    file = download_media(m.url, output.media_dir, resume=True)
                    if os.path.exists(file):
                        m.file = file

                output.save_media(m)
                

def get_best_video(files):
    videos = sorted([x for x in files if x['frameHeight'] <= option.quality],
                    reverse=True,
                    key=lambda v: v['frameWidth'])
    videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == option.subtitles)
    return videos[0]


# flags, action, nargs, const, default, type, choices, required, help, metavar, dest
parser = argparse.ArgumentParser(prog='jwb-index.py',
                                 description='Index or download media from tv.jw.org',
                                 usage='%(prog)s [options] [DIR]')

parser.add_argument('--quality',
                    default=720,
                    type=int,
                    choices=[240, 360, 480, 720],
                    help='maximum video quality')

parser.add_argument('--mode',
                    default='stdout',
                    choices=['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
                    help='output mode')

parser.add_argument('--subtitles',
                    action='store_true',
                    help='prefer subtitled videos')

parser.add_argument('--category',
                    default='VideoOnDemand',
                    help='category/section to index',
                    dest='category')

parser.add_argument('--lang',
                    default='E',
                    help='language code')

parser.add_argument('--download',
                    action='store_true',
                    help='download media')

parser.add_argument('work_dir',
                    action='store',
                    nargs='?',
                    default=os.getcwd(),
                    help='directory to save data in',
                    metavar='DIR')



# HACKISH
argv = ['--lang', 'Z',
        '--mode', 'stdout',
        '--download',
        '--category', 'ChildrenFeatured',
        '/home/alex/mapp',
        '--quality', '240',
        '--download']



option = parser.parse_args(argv)
option.subdir = pj(option.work_dir, 'jwb-' + option.lang)

print(option)

modes = {'stdout': OutputStdout,
         'm3u': OutputM3U,
         'm3ucompat': OutputM3UCompat,
         'filesystem': OutputFilesystem,
         'html': OutputHTML}

output = modes[option.mode]()

# Begin with the first category
# (more categories will be added as we move on)
queue = {option.category}
history = set()

for c in queue:
    parse_vod(c)
