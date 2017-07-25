from sys import stderr
import os
import time
import re
import subprocess
import shutil

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
        self.index_category = 'VideoOnDemand'
        self.rate_limit = '1M'
        self.utc_offset = 0
        self.keep_free = 0
        self.exclude_category = ''

        # Will get set by parse()
        # list containing Media objects
        self.result = []

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

    def parse(self):
        """Download JSON, and return a list of populated a Category objects."""
        if self.streaming:
            section = 'schedules'
        else:
            section = 'categories'

        # Load the queue with the requested (keynames of) categories
        queue = self.index_category.split(',')

        for key in queue:

            url = 'https://mediator.jw.org/v1/{s}/{l}/{c}?detailed=1&utcOffset={o}'
            url = url.format(s=section, l=self.lang, c=key, o=self.utc_offset)

            with urllib.request.urlopen(url) as response:
                response = json.loads(response.read().decode())

                if 'status' in response and response['status'] == '404':
                    raise ValueError('No such category or language')

                # Add new category to the result, or re-use old one
                cat = Media(iscategory=True)
                self.result.append(cat)
                cat.key = response['category']['key']
                cat.name = response['category']['name']
                cat.home = cat.key in self.index_category.split(',')

                if self.quiet == 0:
                    print('{} ({})'.format(cat.key, cat.name), file=stderr)

                if self.streaming:
                    # Save starting position
                    if 'position' in response['category']:
                        cat.position = response['category']['position']['time']

                else:
                    if 'subcategories' in response['category']:
                        for subcat in response['category']['subcategories']:
                            # Add subcategory to current category
                            s = Media(iscategory=True)
                            s.key = subcat['key']
                            s.name = subcat['name']
                            cat.content.append(s)
                            # Add subcategory to queue for parsing later
                            if s.key not in queue:
                                queue.append(s.key)

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

                        cat.content.append(m)

        return self.result

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

        :param media: A Media instance
        :param directory: Dir to save the files to
        :return: filename, or None if unsuccessful
        """
        if not os.path.exists(directory) and not self.download:
            return None

        os.makedirs(directory, exist_ok=True)

        base = urllib.parse.urlparse(media.url).path
        base = os.path.basename(base)
        file = os.path.join(directory, base)

        # Only try resuming and downloading once
        resumed = False
        downloaded = False

        while True:

            if os.path.exists(file):

                # Set timestamp to date of publishing
                # NOTE: Do this before checking _checked_files since
                # this is not done for newly renamed .part files!
                if media.date:
                    os.utime(file, (media.date, media.date))

                # Since the same files can occur in multiple categories
                # only check each file once
                if file in self._checked_files:
                    return file

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

    def download_all(self, wd):
        """Download/check media files

        :param wd: directory where files will be saved
        """
        exclude = self.exclude_category.split(',')
        media_list = [x for cat in self.result if cat.key not in exclude for x in cat.content if not x.iscategory]
        media_list = sorted(media_list, key=lambda x: x.date or 0, reverse=True)

        for media in media_list:
            # Skip previously deleted files
            f = urllib.parse.urlparse(media.url).path
            f = os.path.basename(f)
            f = os.path.join(wd, f + '.deleted')
            if os.path.exists(f):
                continue

            # Clean up until there is enough space
            while self.keep_free > 0:
                space = shutil.disk_usage(wd).free
                needed = media.size + self.keep_free
                if space > needed:
                    break
                print('free space: {:} MB, needed: {:} MB'.format(space // 1000 ** 2, needed // 1000 ** 2), file=stderr)
                _delete_oldest(wd, media.date)

            # Download the video
            media.file = self.download_media(media, wd)


class JWPubMedia(JWBroadcasting):

    def __init__(self):
        super().__init__()
        self.pub = 'bi12'
        self.book = 0

    # TODO
    # Make the language validation pull from JW org
    # @lang.setter
    # def lang(self, code=None):

    def parse(self):
        """Download JSON, create Media objects and send them to the Output object."""
        url_template = 'https://apps.jw.org/GETPUBMEDIALINKS' \
                       '?output=json&fileformat=MP3&alllangs=0&langwritten={l}&txtCMSLang={l}&pub={p}'

        # Watchtower/Awake reference is split up into pub and issue
        magazine_match = re.match('(wp?|g)([0-9]+)', self.pub)
        if magazine_match:
            url_template = url_template + '&issue={i}'
            self.pub = magazine_match.group(1)
            queue = [magazine_match.group(2)]
        else:
            url_template = url_template + '&booknum={i}'
            queue = [self.book]

        for key in queue:
            url = url_template.format(l=self.lang, p=self.pub, i=key)

            book = Media(iscategory=True)
            self.result.append(book)

            if self.pub == 'bi12' or self.pub == 'nwt':
                book.key = format(int(key), '02')
                # This is the starting point if the value in the queue
                # is the same as the one the user specified
                book.home = key == self.book
            else:
                book.key = self.pub
                book.home = True

            with urllib.request.urlopen(url) as response:
                response = json.loads(response.read().decode())
                book.name = response['pubName']

                if self.quiet == 0:
                    print('{} ({})'.format(book.key, book.name), file=stderr)

                # For the Bible's index page
                # Add all books to the queue
                if key == 0 and (self.pub == 'bi12' or self.pub == 'nwt'):
                    for sub_book in response['files'][self.lang]['MP3']:

                        s = Media(iscategory=True)
                        s.key = format(sub_book['booknum'], '02')
                        s.name = sub_book['title']
                        book.content.append(s)

                        if s.key not in queue:
                            queue.append(s.key)
                else:
                    for chptr in response['files'][self.lang]['MP3']:
                        # Skip the ZIP
                        if chptr['mimetype'] != 'audio/mpeg':
                            continue

                        m = Media()
                        m.url = chptr['file']['url']
                        m.name = chptr['title']
                        if 'filesize' in chptr['file']:
                            m.size = chptr['file']['filesize']

                        book.content.append(m)

        return self.result


def _md5(file):
    """Return MD5 of a file."""
    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _curl(url, file, resume=False, rate_limit='0'):
    """Throttled file download by calling the curl command.

    :param url: URL to be downloaded
    :param file: File to write to
    :param resume: Resume download of file
    :param rate_limit: Rate to pass to curl --limit-rate
    """
    proc = ['curl', url, '--silent', '-o', file]
    if resume:
        proc.append('--continue-at')
        proc.append('-')
    if rate_limit != 0:
        proc.append('--limit-rate')
        proc.append(rate_limit)

    subprocess.call(proc, stderr=stderr)


def _delete_oldest(wd, upcoming_time):
    """Delete the oldest .mp4 file in the work_dir

    Exit if oldest video is newer than or equal to upcoming_time.

    :param wd: Directory to look for videos
    :param upcoming_time: Seconds since epoch
    """
    videos = []
    for f in os.listdir(wd):
        f = os.path.join(wd, f)
        if f.endswith('.mp4') and os.path.isfile(f):
            videos.append((f, os.stat(f).st_mtime))
    if len(videos) == 0:
        raise(RuntimeError('cannot free any disk space, no videos found'))
    videos = sorted(videos, key=lambda x: x[1])
    oldest_file, oldest_time = videos[0]

    if upcoming_time and upcoming_time <= oldest_time:
        print('disk limit reached, all videos up to date', file=stderr)
        quit(0)

    print('removing {}'.format(oldest_file), file=stderr)
    os.remove(oldest_file)
    # Add a "deleted" marker
    with open(oldest_file + '.deleted', 'w') as f:
        f.write('')


class Media:
    """Object to put media or category info in."""
    def __init__(self, iscategory=False):
        self.iscategory = iscategory
        if iscategory:
            self.key = None
            self.name = None
            self.content = []
            # Whether or not this is a "starting point"
            self.home = False
            # Seconds (only used for streaming)
            self.position = 0
        else:
            self.url = None
            self.name = None
            self.md5 = None
            self.date = None
            self.size = None
            self.file = None
