from sys import stderr
import os
import urllib
import json
import urllib.request
import urllib.parse
import time
import re

pj = os.path.join


class JWBroadcasting:

    def __init__(self):
        self.__lang = 'E'
        self.__mindate = None
        self.quality = 720
        self.subtitles = False
        self.download = False
        self.streaming = False
        self.quiet = False
        self.checksums = False
        self.category = 'VideoOnDemand'
        self.rate_limit = '1M'
        self.utc_offset = 0

    @property
    def lang(self):
        return self.__lang

    @lang.setter
    def lang(self, code=None):
        """Set language code if valid, or print out a list"""

        url = 'https://mediator.jw.org/v1/languages/E/web'

        with urllib.request.urlopen(url) as response:
            response = json.load(response)

            if code is None:
                # Print table of language codes
                print('language codes:', file=stderr)
                for lang in sorted(response['languages'], key=lambda x: x['name']):
                    print('{:>3}  {:<}'.format(lang['code'], lang['name']), file=stderr)
            else:
                # Check if the code is valid
                for lang in response['languages']:
                    if lang['code'] == code:
                        self.__lang = code
                        return

                print(code + ': invalid language code')

            exit()

    @property
    def mindate(self):
        return self.__mindate

    @mindate.setter
    def mindate(self, date):
        try:
            self.__mindate = time.mktime(time.strptime(date, '%Y-%m-%d'))
        except ValueError:
            print('wrong date format')
            exit()

    def parse(self, output):
        """Download JSON and do stuff"""

        if self.streaming:
            section = 'schedules'
        else:
            section = 'categories'

        queue = [self.category]

        for cat in queue:

            url = 'https://mediator.jw.org/v1/{s}/{l}/{c}?detailed=1&utcOffset={o}'
            url = url.format(s=section, l=self.lang, c=cat, o=self.utc_offset)

            with urllib.request.urlopen(url) as response:
                response = json.load(response)

                if 'status' in response and response['status'] == '404':
                    print('no such category or language', file=stderr)
                    quit()

                # Initialize the cateogory (setting output destination)
                cat = response['category']['key']
                name = response['category']['name']
                output.set_cat(cat, name)
                if not self.quiet:
                    print('{} ({})'.format(cat, name), file=stderr)

                if self.streaming:
                    # Save starting position
                    if 'position' in response['category']:
                        output.pos = response['category']['position']['time']

                else:
                    # Add subcategories to the queue
                    if 'subcategories' in response['category']:
                        for s in response['category']['subcategories']:
                            output.save_subcat(s['key'], s['name'])
                            if s['key'] not in queue:
                                queue.append(s['key'])

                # Output media data to current destination
                if 'media' in response['category']:
                    for media in response['category']['media']:
                        video = self.get_best_video(media['files'])

                        m = Media()
                        m.url = video['progressiveDownloadURL']
                        m.name = media['title']
                        if 'checksum' in video:
                            m.md5 = video['checksum']
                        if 'filesize' in video:
                            m.size = video['filesize']

                        # Save time data (not needed when streaming)
                        if 'firstPublished' in media and not self.streaming:
                            # Remove last stuff from date, what is it anyways?
                            d = re.sub('\.[0-9]+Z$', '', media['firstPublished'])
                            # Try to convert it to seconds
                            try:
                                d = time.mktime(time.strptime(d, '%Y-%m-%dT%H:%M:%S'))
                            except ValueError:
                                pass
                            else:
                                m.date = d
                                if self.mindate and d < self.mindate:
                                    continue

                        # [Download and] check local file (not when streaming, of course)
                        if not self.streaming:
                            m.file = self.download_media(m, output.media_dir)

                        output.save_media(m)

    def get_best_video(self, files):
        videos = sorted([x for x in files if x['frameHeight'] <= self.quality],
                        reverse=True,
                        key=lambda v: v['frameWidth'])
        videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == self.subtitles)
        return videos[0]

    def download_media(self, media, directory):
        """Download media and check it"""

        os.makedirs(directory, exist_ok=True)

        base = urllib.parse.urlparse(media.url).path
        base = os.path.basename(base)
        file = pj(directory, base)

        # Only try resuming and downloading once
        resumed = False
        downloaded = False

        while True:

            if os.path.exists(file):

                # Set timestamp to date of publishing
                if media.date:
                    os.utime(file, (media.date, media.date))

                fsize = os.path.getsize(file)

                if media.size is None:
                    break

                # File size is OK, check MD5
                elif fsize == media.size:
                    if self.checksums is False or media.md5 is None:
                        break
                    elif md5(file) == media.md5:
                        break
                    else:
                        print('deleting: {}, checksum mismatch'.format(base), file=stderr)
                        os.remove(file)

                # File is smaller, try to resume download once
                elif fsize < media.size and not resumed and self.download:
                    resumed = True
                    if not self.quiet:
                        print('resuming: {} ({})'.format(base, media.name), file=stderr)
                    curl(media.url, file, resume=True, rate_limit=self.rate_limit)
                    continue

                # File size is wrong, delete it
                else:
                    print('deleting: {}, size mismatch'.format(base), file=stderr)
                    os.remove(file)

            # Download whole file once
            if not downloaded and self.download:
                downloaded = True
                if not self.quiet:
                    print('downloading: {} ({})'.format(base, media.name), file=stderr)
                curl(media.url, file, rate_limit=self.rate_limit)
                continue

            # Already tried to download and didn't pass tests
            return

        # Tests were successful
        return file


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


def md5(file):
    """MD5 a file"""
    import hashlib

    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def curl(url, file, resume=False, rate_limit='0'):
    """Throttled download of a file with curl"""
    import subprocess

    proc = ['curl', url, '--silent', '-o', file]
    if resume:
        proc.append('--continue-at')
        proc.append('-')
    if rate_limit != 0:
        proc.append('--limit-rate')
        proc.append(rate_limit)

    subprocess.run(proc, stderr=stderr)


class Media:
    """Object with media info"""

    def __init__(self):
        self.url = None
        self.name = None
        self.md5 = None
        self.time = None
        self.size = None
        self.file = None


class Output:
    """Output class for use in JWBroadcasting

    This class does nothing"""

    def __init__(self, work_dir=None):
        if work_dir is None:
            work_dir = os.getcwd()
        self.work_dir = work_dir
        self.media_dir = work_dir

    def _nothing(self, *args, **keywords):
        pass

    set_cat, save_subcat, save_media = _nothing, _nothing, _nothing


class OutputStdout(Output):
    """Output URLs to stdout"""

    def save_media(self, media):
        if media.file is not None:
            print(os.path.relpath(media.file, self.media_dir))
        else:
            print(media.url)


class OutputM3U(Output):
    """Create a M3U playlist tree"""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self._output_file = None
        self._inserted_subdir = ''
        self.file_ending = '.m3u'
        self.media_dir = pj(self.work_dir, self._subdir)

    def save_media(self, media):
        # Write media to a playlist

        if media.file is not None:
            source = pj('.', self._subdir, os.path.basename(media.file))
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
            self._inserted_subdir = self._subdir
            self._output_file = pj(self.work_dir, name + self.file_ending)
        else:
            # The second time and forth:
            # Don't prepend the subdir no more
            # Save data directly in the subdir
            self._inserted_subdir = ''
            self._output_file = pj(self.work_dir, self._subdir, cat + self.file_ending)

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

    def set_cat(self, cat, name):
        # Switch to a new file

        self._output_file = pj(self.work_dir, cat + ' - ' + name + self.file_ending)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    # Don't link to other playlists to not crash media players
    # hence the "compat" part of M3UCompat
    def save_subcat(self, cat, name):
        return


class OutputHTML(OutputM3U):
    """Create a HTML file"""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir, subdir)
        self.file_ending = '.html'

    def write_to_html(self, source, name, file=None):
        # Write a link to a HTML file

        if file is None:
            file = self._output_file

        truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>')

        with open(file, 'a') as f:
            f.write('\n<a href="{0}">{1}</a><br>'.format(source, name))

    write_to_file = write_to_html


class OutputFilesystem(Output):
    """Create a directory structure with symlinks to videos"""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self.media_dir = pj(work_dir, subdir)
        self._output_dir = None

    def set_cat(self, cat, name):
        # Create a directory for saving stuff

        first = self._output_dir is None

        self._output_dir = pj(self.work_dir, self._subdir, cat)

        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        # First time: create link outside subdir
        if first:
            link = pj(self.work_dir, name)
            if not os.path.lexists(link):
                dir_fd = os.open(self._output_dir, os.O_RDONLY)
                # Note: the source will be relative
                source = pj(self._subdir, cat)
                os.symlink(source, link, dir_fd=dir_fd)

    def save_subcat(self, cat, name):
        # Create a symlink to a directory

        dir_ = pj(self.work_dir, self._subdir, cat)
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

    def clean_symlinks(self, clean_all=False):
        """Clean out broken symlinks from work_dir/subdir/*/"""

        d = pj(self.work_dir, self._subdir)

        if not os.path.exists(d):
            return

        for sd in os.listdir(d):
            sd = pj(d, sd)
            if os.path.isdir(sd):
                for l in os.listdir(sd):
                    l = pj(sd, l)
                    if clean_all or os.path.lexists(l):
                        os.remove(l)


class OutputStreaming(Output):
    """Save URLs in a list"""

    def __init__(self):
        super().__init__()
        self.queue = []
        self.pos = 0

    def save_media(self, media):
        self.queue.append(media.url)

    def set_cat(self, cat, name):
        # Reset queue
        self.queue = []