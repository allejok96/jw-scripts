import time
import re
import json
import os
import urllib.request
import urllib.parse
from urllib.error import HTTPError
from typing import List, Union

from .common import msg, Settings

SAFE_FILENAMES = False
FRIENDLY_FILENAMES = False


class Category:
    """Object to put category info in."""
    key = ''
    name = ''
    home = False  # whether or not this is a "starting point"

    def __init__(self):
        self.contents = []  # type: List[Union[Category, Media]]

    # misleading use of repr, but it's only for debugging...
    def __repr__(self):
        return "Category('{}', {})".format(self.key, self.contents)

    @property
    def safe_name(self):
        return format_filename(self.name)


class Media:
    """Object to put media info in."""
    date = 0
    duration = 0
    md5 = ''
    name = ''
    size = 0
    subtitle_url = ''
    url = ''

    # misleading use of repr, but it's only for debugging...
    def __repr__(self):
        return "Media('{}')".format(self.filename)

    def exists_in(self, directory):
        return os.path.exists(os.path.join(directory, self.filename))

    def _get_filename(self, url=''):
        return format_filename(os.path.basename(urllib.parse.urlparse(url).path))

    def _get_friendly_filename(self, url=''):
        return format_filename((self.name or '') + os.path.splitext(self._get_filename(url))[1])

    @property
    def filename(self):
        if FRIENDLY_FILENAMES:
            return self._get_friendly_filename(self.url)
        else:
            return self._get_filename(self.url)

    @property
    def friendly_filename(self):
        return self._get_friendly_filename(self.url)

    @property
    def subtitle_filename(self):
        if FRIENDLY_FILENAMES:
            return self._get_friendly_filename(self.subtitle_url)
        else:
            return self._get_filename(self.subtitle_url)


def format_filename(string):
    """Remove unsafe characters from file names"""

    if SAFE_FILENAMES:
        # NTFS/FAT forbidden characters
        # newline is not forbidden but causes problems in python on windows
        string = string.replace('"', "'").replace(':', '.')
        forbidden = '<>|?\\*/\0\n'
    else:
        # Unix forbidden characters
        forbidden = '/\0'

    return ''.join(x for x in string if x not in forbidden)


# Whoops, copied this from the Kodi plug-in
def get_best_video(videos: list, quality: int, subtitles: bool):
    """Take an jw JSON array of files and metadata and return the most suitable like (url, size)"""

    # Rank media files depending on how they match certain criteria
    # Video resolution will be converted to a rank between 2 and 10
    resolution_not_too_big = 200
    subtitles_matches_pref = 100

    rankings = []
    for j_video in videos:
        rank = 0
        try:
            # Grab resolution from label, eg. 360p, and remove the p
            res = int(j_video.get('label')[:-1])
        except (TypeError, ValueError):
            try:
                res = int(j_video.get('frameHeight', 0))
            except (TypeError, ValueError):
                res = 0
        rank += res // 10
        if 0 < res <= quality:
            rank += resolution_not_too_big
        # 'subtitled' only applies to hardcoded video subtitles
        if j_video.get('subtitled') is subtitles:
            rank += subtitles_matches_pref
        rankings.append((rank, j_video))
    rankings.sort(key=lambda x: x[0])

    # [-1] The file with the highest rank, [1] the filename, not the rank
    # If there was no files, it will raise IndexError
    return rankings[-1][1]


def parse_broadcasting(s: Settings):
    """Index JW Broadcasting categories recursively and return a list with Category objects

    :param s: Global settings object
    """
    # TODO this is really ugly
    global FRIENDLY_FILENAMES, SAFE_FILENAMES
    FRIENDLY_FILENAMES = s.friendly_filenames
    SAFE_FILENAMES = s.safe_filenames

    result = []

    # Make a copy of the list, because we'll append stuff here later
    queue = list(s.include_categories)
    for key in queue:

        url = 'https://data.jw-api.org/mediator/v1/categories/{L}/{c}?detailed=1&clientType=www'
        url = url.format(L=s.lang, c=key)

        try:
            with urllib.request.urlopen(url) as j_raw:  # j as JSON
                j = json.loads(j_raw.read().decode('utf-8'))
        except HTTPError as e:
            if e.code == 404:
                e.msg = '{} not found'.format(key)
                raise e

        cat = Category()
        result.append(cat)
        cat.key = j['category']['key']
        cat.name = j['category']['name']
        cat.home = cat.key in s.include_categories

        if s.quiet < 1:
            msg('indexing: {} ({})'.format(cat.key, cat.name))

        for j_sub in j['category'].get('subcategories', []):
            sub = Category()
            sub.key = j_sub['key']
            sub.name = j_sub['name']
            # Note:
            # We always add an sub-category entry
            # but sometimes it is --exclude'ed so it won't get parsed
            # This will create broken symlinks etc
            # But if script is re-run with these categories included, the links will start to work
            # We call it implementation detail instead of bug...
            cat.contents.append(sub)
            # Add subcategory key to queue for parsing later
            if sub.key not in queue and sub.key not in s.exclude_categories:
                queue.append(sub.key)

        for j_media in j['category'].get('media', []):
            # Skip videos marked as hidden
            if 'tags' in j['category']['media']:
                if 'WebExclude' in j['category']['media']['tags']:
                    continue

            try:
                if j_media.get('type') == 'audio':
                    # Simply pick first audio stream for the time being...
                    j_media_file = j_media['files'][0]
                else:
                    # Note: empty list will raise IndexError
                    j_media_file = get_best_video(j_media['files'], quality=s.quality, subtitles=s.hard_subtitles)
            except IndexError:
                if s.quiet < 1:
                    msg('no media files found for: {}'.format(j_media['title']))
                continue

            media = Media()
            media.url = j_media_file['progressiveDownloadURL']
            media.name = j_media['title']
            media.md5 = j_media_file.get('checksum')
            media.size = j_media_file.get('filesize')
            media.duration = j_media_file.get('duration')
            if j_media_file.get('subtitles'):
                media.subtitle_url = j_media_file['subtitles']['url']

            # Save time data
            if 'firstPublished' in j_media:
                try:
                    # Remove last stuff from date, what is it anyways?
                    date_string = re.sub('\\.[0-9]+Z$', '', j_media['firstPublished'])
                    # Try to convert it to seconds
                    date = time.mktime(time.strptime(date_string, '%Y-%m-%dT%H:%M:%S'))
                    if date < s.min_date:
                        continue
                    media.date = date
                except ValueError:
                    if s.quiet < 1:
                        msg('could not get timestamp on: {}'.format(j_media['title']))

            cat.contents.append(media)

    return result
