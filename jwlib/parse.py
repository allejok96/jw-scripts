from sys import stderr
import os
import time
import re
import subprocess

import json
import hashlib
import urllib.request
import urllib.parse


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
            response = json.loads(response.read().decode())

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
                response = json.loads(response.read().decode())

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
                        if not self.streaming:
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
        file = os.path.join(directory, base)

        # Only try resuming and downloading once
        resumed = False
        downloaded = False

        while True:

            if os.path.exists(file):

                # Since the same files can occur in multiple categories
                # only check each file once
                if file in self._checked_files:
                    return file

                # Set timestamp to date of publishing
                if media.date:
                    os.utime(file, (media.date, media.date))

                if os.path.getsize(file) == media.size or not media.size:
                    # File size is OK or unknown - Validate checksum
                    if self.checksums and media.md5 and _md5(file) != media.md5:
                        # Checksum is bad - Remove
                        print('checksum mismatch, deleting: {}'.format(base), file=stderr)
                        os.remove(file)
                    else:
                        # Checksum is correct or unknown
                        self._checked_files.add(file)
                        return file
                else:
                    # File size is bad - Delete
                    print('size mismatch, deleting: {}'.format(base + '.part'), file=stderr)
                    os.remove(file)

            elif not self.download:
                # The rest of this method is only applicable in download mode
                return None

            elif os.path.exists(file + '.part'):

                fsize = os.path.getsize(file + '.part')

                if fsize == media.size or not media.size:
                    # File size is OK - Validate checksum
                    if self.checksums and media.md5 and _md5(file + '.part') != media.md5:
                        # Checksum is bad - Remove
                        print('checksum mismatch, deleting: {}'.format(base + '.part'), file=stderr)
                        os.remove(file + '.part')
                    else:
                        # Checksum is correct or unknown - Move and approve
                        self._checked_files.add(file)
                        os.rename(file + '.part', file)
                elif fsize < media.size and not resumed:
                    # File is smaller - Resume download once
                    resumed = True
                    if self.quiet <= 1:
                        print('resuming: {} ({})'.format(base + '.part', media.name), file=stderr)
                    _curl(media.url, file + '.part', resume=True, rate_limit=self.rate_limit)
                else:
                    # File size is bad - Remove
                    print('size mismatch, deleting: {}'.format(base + '.part'), file=stderr)
                    os.remove(file + '.part')

            else:
                # Download whole file once
                if not downloaded:
                    downloaded = True
                    if self.quiet <= 1:
                        print('downloading: {} ({})'.format(base, media.name), file=stderr)
                    _curl(media.url, file + '.part', rate_limit=self.rate_limit)
                else:
                    # If we get here, all tests have failed.
                    # Resume and regular download too.
                    # There is nothing left to do.
                    return None


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
                response = json.loads(response.read().decode())

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


def _md5(file):
    """Return MD5 of a file."""
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
