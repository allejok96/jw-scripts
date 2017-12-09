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


def msg(s):
    print(s, file=stderr, flush=True)


class JWBroadcasting:
    """
    Class for parsing and downloading videos from JW Broadcasting

    Tweak the variables, and run :method:`parse` and then :method:`download_all`
    """
    __lang = 'E'
    __mindate = None
    quality = 720
    subtitles = False
    download = False
    streaming = False
    quiet = 0
    checksums = False
    index_category = 'VideoOnDemand'
    rate_limit = '1M'
    curl_path = 'curl'
    keep_free = 0
    exclude_category = ''
    # Used if streaming is True
    utc_offset = 0

    def __init__(self):
        # Will populated with Media objects by parse()
        self.result = []
        # Used by download_media()
        self._checked_files = set()

    @property
    def lang(self):
        """Language code

        If the code is None, print out a list and exit. If code is invalid, raise ValueError.
        """
        return self.__lang

    @lang.setter
    def lang(self, code):
        url = 'https://data.jw-api.org/mediator/v1/languages/E/web?clientType=tvjworg'

        with urllib.request.urlopen(url) as response:
            response = json.loads(response.read().decode())

            if not code:
                # Print table of language codes
                msg('language codes:')
                for lang in sorted(response['languages'], key=lambda x: x['name']):
                    msg('{:>3}  {:<}'.format(lang['code'], lang['name']))
                exit()
            else:
                # Check if the code is valid
                for lang in response['languages']:
                    if lang['code'] == code:
                        self.__lang = code
                        return

                raise ValueError(code + ': invalid language code')

    @property
    def mindate(self):
        """Minimum date of media

        Set to 'YYYY-MM-DD'. It will be stored as seconds since epoch.
        """
        return self.__mindate

    @mindate.setter
    def mindate(self, date):
        try:
            self.__mindate = time.mktime(time.strptime(date, '%Y-%m-%d'))
        except ValueError:
            raise ValueError('wrong date format')

    def parse(self):
        """Index JW Broadcasting categories recursively

        :return: A list containing Category and Media objects
        """
        if self.streaming:
            section = 'schedules'
        else:
            section = 'categories'

        # Load the queue with the requested (keynames of) categories
        queue = self.index_category.split(',')

        for key in queue:

            url = 'https://data.jw-api.org/mediator/v1/{s}/{L}/{c}?detailed=1&clientType=tvjworg&utcOffset={o}'
            url = url.format(s=section, L=self.lang, c=key, o=self.utc_offset)

            with urllib.request.urlopen(url) as response:
                response = json.loads(response.read().decode())

                if 'status' in response and response['status'] == '404':
                    raise ValueError('No such category or language')

                # Add new category to the result, or re-use old one
                cat = Category()
                self.result.append(cat)
                cat.key = response['category']['key']
                cat.name = response['category']['name']
                cat.home = cat.key in self.index_category.split(',')

                if self.quiet < 1:
                    msg('{} ({})'.format(cat.key, cat.name))

                if self.streaming:
                    # Save starting position
                    if 'position' in response['category']:
                        cat.position = response['category']['position']['time']

                else:
                    if 'subcategories' in response['category']:
                        for subcat in response['category']['subcategories']:
                            # Add subcategory to current category
                            s = Category()
                            s.key = subcat['key']
                            s.name = subcat['name']
                            cat.add(s)
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

                        cat.add(m)

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

    def download_media(self, media, directory, check_only=False):
        """Download media file and check it.

        Download file, check MD5 sum and size, delete file if it missmatches.

        :param media: a Media instance
        :param directory: dir to save the files to
        :param check_only: bool, True means no downloading
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
                        if self.quiet < 2:
                            msg('checksum mismatch, deleting: {}'.format(base))
                        os.remove(file)
                    else:
                        # Checksum is correct or unknown
                        self._checked_files.add(file)
                        return file
                else:
                    # File size is bad - Delete
                    if self.quiet < 2:
                        msg('size mismatch, deleting: {}'.format(base + '.part'))
                    os.remove(file)

            elif check_only:
                # The rest of this method is only applicable in download mode
                return None

            elif os.path.exists(file + '.part'):

                fsize = os.path.getsize(file + '.part')

                if fsize == media.size or not media.size:
                    # File size is OK - Validate checksum
                    if self.checksums and media.md5 and _md5(file + '.part') != media.md5:
                        # Checksum is bad - Remove
                        if self.quiet < 2:
                            msg('checksum mismatch, deleting: {}'.format(base + '.part'))
                        os.remove(file + '.part')
                    else:
                        # Checksum is correct or unknown - Move and approve
                        self._checked_files.add(file)
                        os.rename(file + '.part', file)
                elif fsize < media.size and not resumed:
                    # File is smaller - Resume download once
                    resumed = True
                    if self.quiet < 2:
                        msg('resuming: {} ({})'.format(base + '.part', media.name))
                    _curl(media.url,
                          file + '.part',
                          resume=True,
                          rate_limit=self.rate_limit,
                          curl_path=self.curl_path,
                          progress=self.quiet < 1)
                else:
                    # File size is bad - Remove
                    if self.quiet < 2:
                        msg('size mismatch, deleting: {}'.format(base + '.part'))
                    os.remove(file + '.part')

            else:
                # Download whole file once
                if not downloaded:
                    downloaded = True
                    if self.quiet < 2:
                        msg('downloading: {} ({})'.format(base, media.name))
                    _curl(media.url,
                          file + '.part',
                          rate_limit=self.rate_limit,
                          curl_path=self.curl_path,
                          progress=self.quiet < 1)
                else:
                    # If we get here, all tests have failed.
                    # Resume and regular download too.
                    # There is nothing left to do.
                    if self.quiet < 2:
                        msg('failed to download: {} ({})'.format(base, media.name))
                    return None

    def download_all(self, wd):
        """Download/check media files

        :param wd: directory where files will be saved
        """
        exclude = self.exclude_category.split(',')
        media_list = [x for cat in self.result
                      if cat.key not in exclude or cat.home
                      for x in cat.content
                      if not x.iscategory]
        media_list = sorted(media_list, key=lambda x: x.date or 0, reverse=True)

        # Trim down the list of files that need to be downloaded
        download_list = []
        for media in media_list:
            # Skip previously deleted files
            f = urllib.parse.urlparse(media.url).path
            f = os.path.basename(f)
            f = os.path.join(wd, f + '.deleted')
            if os.path.exists(f):
                continue

            # Delete broken files
            media.file = self.download_media(media, wd, check_only=True)

            # Skip correct files
            if media.file:
                continue

            download_list.append(media)

        if not self.download:
            return

        # Download all files
        for media in download_list:

            # Clean up until there is enough space
            while self.keep_free > 0:
                space = shutil.disk_usage(wd).free
                needed = media.size + self.keep_free
                if space > needed:
                    break
                if self.quiet < 1:
                    msg('free space: {:} MiB, needed: {:} MiB'.format(space//1024**2, needed//1024**2))
                delete_oldest(wd, media.date, self.quiet)

            # Download the video
            if self.quiet < 2:
                print('[{}/{}]'.format(download_list.index(media) + 1, len(download_list)), end=' ', file=stderr)
            media.file = self.download_media(media, wd)


class JWPubMedia(JWBroadcasting):
    pub = 'bi12'
    book = 0
    # Disable rate limit completely
    rate_limit = '0'
    # Disable curl
    # Since downloads of sound is so small it seems more worth
    # to stay compatible (urllib) than fancy (curl with progress bar)
    curl_path = None
    # This creates a local name for lang, and overwrites the setter/getter
    # property inherited from JWBroadcasting
    lang = 'E'

    def parse(self):
        """Index JW org sound recordings

        :return: a list containing Category and Media objects
        """
        url_template = 'https://apps.jw.org/GETPUBMEDIALINKS' \
                       '?output=json&fileformat=MP3&alllangs={a}&langwritten={L}&txtCMSLang={L}&pub={p}'

        # Watchtower/Awake reference is split up into pub and issue
        magazine_match = re.match('(wp?|g)([0-9]+)', self.pub)
        if magazine_match:
            url_template = url_template + '&issue={i}'
            self.pub = magazine_match.group(1)
            queue = [magazine_match.group(2)]
        else:
            url_template = url_template + '&booknum={i}'
            queue = [self.book]

        # Check language code
        # This must be done after the magazine stuff
        # We want the languages for THAT publication only, or else the list gets SOO long
        # The language is checked on the first pub in the queue
        url = url_template.format(L='E', p=self.pub, i=queue[0], a='1')

        with urllib.request.urlopen(url) as response:
            response = json.loads(response.read().decode())

            if not self.lang:
                # Print table of language codes
                msg('language codes:')
                for lang in sorted(response['languages'], key=lambda x: response['languages'][x]['name']):
                    msg('{:>3}  {:<}'.format(lang, response['languages'][lang]['name']))
                exit()
            else:
                # Check if the code is valid
                if self.lang not in response['languages']:
                    raise ValueError(self.lang + ': invalid language code')

        for key in queue:
            url = url_template.format(L=self.lang, p=self.pub, i=key, a=0)

            book = Category()
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

                if self.quiet < 1:
                    msg('{} ({})'.format(book.key, book.name))

                # For the Bible's index page
                # Add all books to the queue
                if key == 0 and (self.pub == 'bi12' or self.pub == 'nwt'):
                    for sub_book in response['files'][self.lang]['MP3']:

                        s = Category()
                        s.key = format(sub_book['booknum'], '02')
                        s.name = sub_book['title']
                        book.add(s)

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
                        if 'filesize' in chptr:
                            m.size = chptr['filesize']

                        book.add(m)

        return self.result


def _md5(file):
    """Return MD5 of a file."""
    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _curl(url, file, resume=False, rate_limit='0', curl_path='curl', progress=False):
    """Throttled file download by calling the curl command."""
    if curl_path:
        proc = [curl_path, url, '-o', file]

        if rate_limit != '0':
            proc.append('--limit-rate')
            proc.append(rate_limit)
        if progress:
            proc.append('--progress-bar')
        else:
            proc.append('--silent')
        if resume:
            # Download what is missing at the end of the file
            proc.append('--continue-at')
            proc.append('-')

        subprocess.call(proc, stderr=stderr)

    else:
        # If there is no rate limit, use urllib (for compatibility)
        request = urllib.request.Request(url)
        file_mode = 'wb'

        if resume:
            # Ask server to skip the first N bytes
            request.add_header('Range', 'bytes={}-'.format(os.stat(file).st_size))
            # Append data to file, instead of overwriting
            file_mode = 'ab'

        response = urllib.request.urlopen(request)

        # Write out 1MB at a time, so whole file is not lost if interrupted
        with open(file, file_mode) as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


def delete_oldest(wd, upcoming_time, quiet=0):
    """Delete the oldest .mp4 file in the work_dir

    Exit if oldest video is newer than or equal to :param:`upcoming_time`.

    :param wd: directory to look for videos
    :param upcoming_time: seconds since epoch
    :param quiet: info level, 0 = all, 1 = only deleted, 2 = nothing
    """
    videos = []
    for f in os.listdir(wd):
        f = os.path.join(wd, f)
        if f.lower().endswith('.mp4') and os.path.isfile(f):
            videos.append((f, os.stat(f).st_mtime))
    if len(videos) == 0:
        raise(RuntimeError('cannot free any disk space, no videos found'))
    videos = sorted(videos, key=lambda x: x[1])
    oldest_file, oldest_time = videos[0]

    if upcoming_time and upcoming_time <= oldest_time:
        if quiet < 1:
            msg('disk limit reached, all videos up to date')
        quit(0)

    if quiet < 2:
        msg('removing {}'.format(oldest_file))
    os.remove(oldest_file)
    # Add a "deleted" marker
    with open(oldest_file + '.deleted', 'w') as f:
        f.write('')


class Category:
    """Object to put category info in."""
    iscategory = True
    key = None
    name = None
    # Whether or not this is a "starting point"
    home = False
    # Used for streaming
    position = 0

    def __init__(self):
        self.content = []

    def add(self, obj):
        """Add an object to :var:`self.content`

        :param obj: an instance of :class:`Category` for :class:`Media`
        """
        self.content.append(obj)


class Media:
    """Object to put media info in."""
    iscategory = False
    url = None
    name = None
    md5 = None
    date = None
    size = None
    file = None
