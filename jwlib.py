from sys import stderr
import os
import time
import re

import json
import urllib.request
import urllib.parse

pj = os.path.join


class JWBroadcasting:

    def __init__(self):
        self.__lang = 'E'
        self.__mindate = None
        self.quality = 720
        self.subtitles = False
        self.download = False
        self.streaming = False
        self.quiet = 0
        self.checksums = False
        self.category = 'VideoOnDemand'
        self.rate_limit = '1M'
        self.utc_offset = 0
        # Don't download or check files
        self.dry_run = False
        # Used by download_media()
        self._checked_files = set()

    @property
    def lang(self):
        return self.__lang

    @lang.setter
    def lang(self, code=None):
        """Set language code.
        
        If valid the code is invalid, print out a list and exit.
        """
        url = 'https://mediator.jw.org/v1/languages/E/web'

        with urllib.request.urlopen(url) as response:
            response = json.load(response)

            if not code:
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

                raise ValueError(code + ': invalid language code')

            exit()

    @property
    def mindate(self):
        return self.__mindate

    @mindate.setter
    def mindate(self, date):
        """Convert human readable date to seconds since epoch."""
        try:
            self.__mindate = time.mktime(time.strptime(date, '%Y-%m-%d'))
        except ValueError:
            raise ValueError('wrong date format')

    def parse(self, output):
        """Download JSON, create Media objects and send them to the Output object."""
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
                    raise ValueError('No such category or language')

                # Initialize the cateogory (setting output destination)
                cat = response['category']['key']
                name = response['category']['name']
                output.set_cat(cat, name)
                if self.quiet == 0:
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
                        # Skip videos marked as hidden
                        if 'tags' in response['category']['media']:
                            if 'WebExclude' in response['category']['media']['tags']:
                                continue

                        video = self._get_best_video(media['files'])

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
                        if not self.streaming and not self.dry_run:
                            m.file = self.download_media(m, output.media_dir)

                        output.save_media(m)

    def _get_best_video(self, video_list: list):
        """Take a list of media files and metadata and return the best one"""

        videos = []
        for vid in video_list:
            try:
                # Convert labels like 720p to int in a most forgiving way
                vid['label'] = int(vid['label'][:-1])
            except ValueError or TypeError:
                # In case the label is wrong format, use frame height
                # (But this may be misleading)
                vid['label'] = vid['frameHeight']
            # Only save videos that match quality setting
            if vid['label'] <= self.quality:
                videos.append(vid)

        # Sort by quality and subtitle setting
        videos = sorted(videos, reverse=True, key=lambda v: v['label'])
        videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == self.subtitles)
        return videos[0]

    def download_media(self, media, directory):
        """Download media file and check it.

        Download file, check MD5 sum and size, delete file if it missmatches.
        Return the filename, or None if unsucessfull.

        Arguments:
        media - A Media instance
        directory - Dir to save the files to
        """        
        os.makedirs(directory, exist_ok=True)

        base = urllib.parse.urlparse(media.url).path
        base = os.path.basename(base)
        file = pj(directory, base)

        # Since the same files can occur in multiple categories
        # only check each file once
        if file in self._checked_files:
            return file

        # Only try resuming and downloading once
        resumed = False
        downloaded = False

        while True:

            if os.path.exists(file):

                # Set timestamp to date of publishing
                if media.date:
                    os.utime(file, (media.date, media.date))

                fsize = os.path.getsize(file)

                if not media.size:
                    break

                # File size is OK, check MD5
                elif fsize == media.size:
                    if not self.checksums or not media.md5:
                        break
                    elif _md5(file) == media.md5:
                        break
                    else:
                        print('deleting: {}, checksum mismatch'.format(base), file=stderr)
                        os.remove(file)

                # File is smaller, try to resume download once
                elif fsize < media.size and not resumed and self.download:
                    resumed = True
                    if self.quiet <= 1:
                        print('resuming: {} ({})'.format(base, media.name), file=stderr)
                    _curl(media.url, file, resume=True, rate_limit=self.rate_limit)
                    continue

                # File size is wrong, delete it
                else:
                    print('deleting: {}, size mismatch'.format(base), file=stderr)
                    os.remove(file)

            # Download whole file once
            if not downloaded and self.download:
                downloaded = True
                if self.quiet <= 1:
                    print('downloading: {} ({})'.format(base, media.name), file=stderr)
                _curl(media.url, file, rate_limit=self.rate_limit)
                continue

            # Already tried to download and didn't pass tests
            return None

        # Tests were successful
        self._checked_files.add(file)
        return file


class JWPubMedia(JWBroadcasting):

    def __init__(self):
        super().__init__()
        self.pub = 'bi12'
        self.book = 0

    # TODO
    # Make the language validation pull from JW org
    # @lang.setter
    # def lang(self, code=None):

    def parse(self, output):
        """Download JSON, create Media objects and send them to the Output object."""
        queue = [self.book]

        for bookid in queue:
            url = 'https://apps.jw.org/GETPUBMEDIALINKS' \
                  '?output=json&fileformat=MP3&alllangs=0&langwritten={l}&txtCMSLang={l}&pub={p}&{n}={i}'

            # Watchtower/Awake reference is split up into pub and issue
            match = re.match('(wp?|g)([0-9]+)', self.pub)
            if match:
                url = url.format(l=self.lang, p=match.group(1), n='issue', i=match.group(2))
                codename = self.pub
            else:
                url = url.format(l=self.lang, p=self.pub, n='booknum', i=bookid)
                codename = format(bookid, '02')

            with urllib.request.urlopen(url) as response:
                response = json.load(response)

                # Initialize the publication or book (setting output destination)
                name = response['pubName']
                output.set_cat(codename, name)

                if self.quiet == 0:
                    print('{} ({})'.format(codename, name), file=stderr)

                # For the Bible's index page
                # Add all books to the queue
                if bookid == 0 and (self.pub == 'bi12' or self.pub == 'nwt'):
                    for book in response['files'][self.lang]['MP3']:
                        output.save_subcat(format(book['booknum'], '02'), book['title'])
                        if book['booknum'] not in queue:
                            queue.append(book['booknum'])
                else:
                    # Output media data to current destination
                    for chptr in response['files'][self.lang]['MP3']:
                        # Skip the ZIP
                        if chptr['mimetype'] != 'audio/mpeg':
                            continue

                        m = Media()
                        m.url = chptr['file']['url']
                        m.name = chptr['title']
                        if 'filesize' in chptr['file']:
                            m.size = chptr['file']['filesize']
                        m.file = self.download_media(m, output.media_dir)
                        output.save_media(m)


def _truncate_file(file, string=''):
    """Create a file and the parent directories.

    Arguments:
    file - File to create/overwrite

    Keyword arguments:
    string - A string to write to the file
    """
    d = os.path.dirname(file)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    # Don't truncate non-empty files
    if os.path.exists(file) and os.stat(file).st_size != 0:
        return

    with open(file, 'w') as f:
        f.write(string)


def _md5(file):
    """Return MD5 of a file."""
    import hashlib

    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _curl(url, file, resume=False, rate_limit='0'):
    """Throttled file download by calling the curl command.

    Arguments:
    url - URL to be downloaded
    file - File to write to

    Keyword arguments:
    resume - Resume download of file (default False)
    rate_limit - Rate to pass to curl --limit-rate
    """
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
    """Object to put media info in."""

    def __init__(self):
        self.url = None
        self.name = None
        self.md5 = None
        self.time = None
        self.size = None
        self.file = None


class Output:
    """Base output class.

    This class does nothing.
    """
    
    def __init__(self, work_dir=None):
        """Set working dir and dir for media download.
        
        Keyword arguments:
            work_dir -- Working directory
        """
        if not work_dir:
            work_dir = os.getcwd()
        self.work_dir = work_dir
        self.media_dir = work_dir

    def _nothing(self, *args, **keywords):
        pass

    set_cat, save_subcat, save_media = _nothing, _nothing, _nothing


class OutputStdout(Output):
    """Output text only."""

    def save_media(self, media):
        """Output URL/filename from Media instance to stdout."""
        if media.file:
            print(os.path.relpath(media.file, self.media_dir))
        else:
            print(media.url)


class OutputM3U(Output):
    """Create a M3U playlist tree."""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self._output_file = None
        self._inserted_subdir = ''
        self.file_ending = '.m3u'
        self.media_dir = pj(self.work_dir, self._subdir)

    def save_media(self, media):
        """Write media entry to playlist."""
        if media.file:
            source = pj('.', self._subdir, os.path.basename(media.file))
        else:
            source = media.url

        self.write_to_file(source, media.name)

    def save_subcat(self, cat, name):
        """Write link to another category, i.e. playlist, to the current one."""
        name = name.upper()
        source = pj('.', self._inserted_subdir, cat + self.file_ending)
        self.write_to_file(source, name)

    def set_cat(self, cat, name):
        """Set destination playlist file."""
        if not self._output_file:
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
        """Write entry to a M3U playlist file."""
        if not file:
            file = self._output_file
        _truncate_file(file, string='#EXTM3U\n')
        with open(file, 'a') as f:
            f.write('#EXTINF:0,' + name + '\n' + source + '\n')

    write_to_file = write_to_m3u


class OutputM3UCompat(OutputM3U):
    """Create multiple M3U playlists."""

    def set_cat(self, cat, name):
        """Set/remove destination playlist file."""
        self._output_file = pj(self.work_dir, cat + ' - ' + name + self.file_ending)
        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    def save_subcat(self, cat, name):
        """Do nothing.

        Unlike the parent class, this class doesn't save links to other categories,
        e.g. other playlists, inside the current playlist.
        """
        pass


class OutputHTML(OutputM3U):
    """Create a HTML file."""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir, subdir)
        self.file_ending = '.html'

    def write_to_html(self, source, name, file=None):
        """Write a HTML file with a hyperlink to a media file."""
        if not file:
            file = self._output_file

        _truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>')

        with open(file, 'a') as f:
            f.write('\n<a href="{0}">{1}</a><br>'.format(source, name))

    write_to_file = write_to_html


class OutputFilesystem(Output):
    """Creates a directory structure with symlinks to videos"""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self.media_dir = pj(work_dir, subdir)
        self._output_dir = None

    def set_cat(self, cat, name):
        """Create a directory (category) where symlinks will be saved"""
        output_dir_before = self._output_dir
        
        self._output_dir = pj(self.work_dir, self._subdir, cat)
        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        # First time: create link outside subdir
        if output_dir_before is None:
            link = pj(self.work_dir, name)
            if not os.path.lexists(link):
                dir_fd = os.open(self._output_dir, os.O_RDONLY)
                # Note: the source will be relative
                source = pj(self._subdir, cat)
                os.symlink(source, link, dir_fd=dir_fd)

    def save_subcat(self, cat, name):
        """Create a symlink to a directory (category)"""
        dir_ = pj(self.work_dir, self._subdir, cat)
        if not os.path.exists(dir_):
            os.makedirs(dir_)

        source = pj('..', cat)
        link = pj(self._output_dir, name)

        if not os.path.lexists(link):
            dir_fd = os.open(self._output_dir, os.O_RDONLY)
            os.symlink(source, link, dir_fd=dir_fd)

    def save_media(self, media):
        """Create a symlink to a media file"""
        if not media.file:
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
                for L in os.listdir(sd):
                    L = pj(sd, L)
                    if clean_all or os.path.lexists(L):
                        os.remove(L)

                        
class OutputQueue(Output):
    """Queues media objects"""

    def __init__(self, work_dir):
        super().__init__(work_dir)
        self.queue = []

    def save_media(self, media):
        """Add a media object to the queue"""
        self.queue.append(media)


class OutputStreaming(Output):
    """Queue URLs from a single category"""
    
    def __init__(self):
        super().__init__()
        self.queue = []
        self.pos = 0

    def save_media(self, media):
        """Add an URL to the queue"""
        self.queue.append(media.url)

    def set_cat(self, cat, name):
        """Reset queue"""
        self.queue = []
