import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import List, Dict, Iterable
from urllib.error import HTTPError

from .common import msg, Settings, Path
from .constants import TAG_HIDDEN, API_BASE

SAFE_FILENAMES = False
FRIENDLY_FILENAMES = False
LANGUAGE_TABLE = {'E': ('English', 'en')}  # just for reference


class MissingCategoryName(Exception):
    """When trying to get a human readable name on a category is lazily created with primaryCategory (--update)"""
    pass


class InvalidCategory(Exception):
    """When a category request returns 404 or empty"""
    pass


class InvalidMedia(Exception):
    """When media request returns 404 or empty, or it should not be parsed"""
    pass


class Category:
    """Object to put category info in."""
    key: str = ''
    name: str = ''
    home: bool = False  # whether or not this is a "starting point"

    def __init__(self):
        self.subcategories: List[Category] = []
        self.items: List[Media] = []

    # misleading use of repr, but it's only for debugging...
    def __repr__(self):
        return "Category('{}', {}, {})".format(self.key, self.subcategories, self.items)

    @property
    def safe_name(self):
        """Returns name with special characters removed, or raises CategoryError if unset"""
        if not self.name:
            raise MissingCategoryName
        return format_filename(self.name)


class Media:
    """Object to put media info in."""
    date: int = 0
    duration: int = 0
    key: str = ''
    md5: str = ''
    name: str = ''
    size: int = 0
    url: str = ''
    _file: Path = None

    def __init__(self):
        self.subtitles: Dict[str, str] = {}  # {language: URL}

    # misleading use of repr, but it's only for debugging...
    def __repr__(self):
        return "Media('{}')".format(self.key)

    @property
    def filename(self):
        return url_basename(self.url)

    @property
    def friendly_filename(self):
        return format_filename((self.name or '') + os.path.splitext(self.filename)[1])

    def find_file(self, directory: Path):
        """Find and return existing media file or fall back to default filename"""

        if self._file is None:
            # TODO should we match friendly if not in that mode?
            for name in self.filename, self.friendly_filename:
                if (directory / name).exists():
                    self._file = directory / name
                    break
            else:
                # Match a different quality (highest first)
                pattern = re.sub(r'_r[0-9]{3,4}P\.', '_r*P.', self.filename)
                for file in sorted(directory.glob(pattern),
                                   key=lambda f: get_quality_from_filename(f.name),
                                   reverse=True):
                    self._file = file
                    break
                else:
                    # Fallback to default (non-existent) name
                    self._file = directory / (self.friendly_filename if FRIENDLY_FILENAMES else self.filename)

        return self._file


def url_basename(url):
    return format_filename(os.path.basename(urllib.parse.urlparse(url).path))


def format_filename(string: str):
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


def get_quality_from_filename(name):
    match = re.match(r'_r([1-9][0-9]{2,3})P\.', name)
    if match:
        return int(match[1])
    else:
        return 0


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


def get_languages():
    """Get languages from the API"""

    global LANGUAGE_TABLE

    if len(LANGUAGE_TABLE) == 1:
        with urllib.request.urlopen(API_BASE + '/languages/E/web') as response:
            for L in json.loads(response.read().decode('utf-8'))['languages']:
                LANGUAGE_TABLE[L['code']] = L['name'], L['locale']

    return LANGUAGE_TABLE


def request_category(lang, key) -> dict:
    """Make an API request for category data"""

    try:
        # Note: looking up an invalid category results in 404
        url = API_BASE + '/categories/{}/{}?detailed=1'.format(lang, key)
        with urllib.request.urlopen(url) as data:
            return json.loads(data.read().decode('utf-8'))['category']
    except HTTPError as e:
        if e.code == 404:
            raise InvalidCategory
    except KeyError:
        raise InvalidCategory


def request_media(lang, key) -> dict:
    """Make an API request for media data"""

    try:
        # Note: looking up an invalid media key results in {'media': []}
        url = API_BASE + '/media-items/{}/{}'.format(lang, key)
        with urllib.request.urlopen(url) as data:
            return json.loads(data.read().decode('utf-8'))['media'][0]
    except HTTPError as e:
        if e.code == 404:
            raise InvalidMedia
    except (KeyError, IndexError, AssertionError):
        raise InvalidMedia


def get_categories(s: Settings, key: str):
    """Return a list of sub category keys"""

    j = request_category(s.lang, key)
    return [sub['key'] for sub in j['category'].get('subcategories', [])]


def index_broadcasting(s: Settings, lang: str = None, ignore_missing=False) -> List[Category]:
    """Index JW Broadcasting categories recursively and return a list with Category objects"""

    if lang is None:
        lang = s.lang

    # Make a copy because we'll append stuff here later
    queue = s.include_categories.copy()
    result = []

    for key in queue:
        try:
            cat_data = request_category(lang, key)
        except InvalidCategory:
            if ignore_missing:
                continue
            raise

        cat = Category()
        cat.key = cat_data['key']
        cat.name = cat_data['name']
        cat.home = cat.key in s.include_categories
        if not s.update:
            result.append(cat)

        if s.quiet < 1:
            msg('indexing: {} ({})'.format(cat.key, cat.name))

        for sub_data in cat_data.get('subcategories', []):
            # Do not dive into excluded categories
            if TAG_HIDDEN in sub_data.get('tags', []):
                continue

            sub = Category()
            sub.key = sub_data['key']
            sub.name = sub_data['name']
            # Note:
            # We always add an sub-category entry
            # but sometimes it is --exclude'ed so it won't get parsed
            # This will create broken symlinks etc
            # But if script is re-run with these categories included, the links will start to work
            # We call it implementation detail instead of bug...
            cat.subcategories.append(sub)
            # Add subcategory key to queue for parsing later
            if sub.key not in queue and sub.key not in s.exclude_categories:
                queue.append(sub.key)

        for media_data in cat_data.get('media', []):
            # Create a Media object
            try:
                media = parse_media_data(s, media_data, lang)
            except InvalidMedia:
                continue

            # Add Media object to a Category
            if s.update:
                try:
                    # Find a previously added category
                    pcat = next(c for c in result if c.key == media_data['primaryCategory'])
                except StopIteration:
                    # Create a new homeless category
                    pcat = Category()
                    pcat.key = media_data['primaryCategory']
                    pcat.home = False
                    result.append(pcat)
                # Add media to its primary category
                pcat.items.append(media)
            else:
                # Add media to current category
                cat.items.append(media)

    return result


def parse_media_data(s: Settings, media_data: dict, lang: str, verbose=False):
    """Create a Media object from JSON data

    :param s: Global settings object (needed for filtering, quality etc)
    :param media_data: Dictionary containing media metadata
    :param lang: Language code (needed for subtitles)
    :param verbose: Print media name
    """

    # Skip videos marked as hidden
    if TAG_HIDDEN in media_data.get('tags', []):
        raise InvalidMedia
    # Apply category filter
    if s.filter_categories and media_data['primaryCategory'] not in s.filter_categories:
        raise InvalidMedia

    media = Media()
    media.key = media_data['languageAgnosticNaturalKey']
    media.name = media_data['title']
    if verbose and s.quiet < 1:
        msg('indexing: {} ({})'.format(media.key, media.name))

    # Save time data
    try:
        # Try to convert it to seconds
        date = time.mktime(time.strptime(media_data['firstPublished'][:19], '%Y-%m-%dT%H:%M:%S'))
        if date < s.min_date:
            raise InvalidMedia
        media.date = date
    except (ValueError, KeyError):
        if s.quiet < 1:
            msg('could not get timestamp on: {}'.format(media.name))

    # Select preferred file
    try:
        if media_data.get('type') == 'audio':
            # Simply pick first audio stream for the time being...
            j_media_file = media_data['files'][0]
        else:
            # Note: empty list will raise IndexError
            j_media_file = get_best_video(media_data['files'], quality=s.quality, subtitles=s.hard_subtitles)
    except IndexError:
        if s.quiet < 1:
            msg('no media files found for: {}'.format(media.name))
        raise InvalidMedia

    media.url = j_media_file['progressiveDownloadURL']
    media.md5 = j_media_file.get('checksum')
    media.size = j_media_file.get('filesize')
    media.duration = j_media_file.get('duration')
    if j_media_file.get('subtitles'):
        media.subtitles[lang] = j_media_file['subtitles']['url']

    return media


def index_alternative_media(s: Settings, media_items: Iterable[Media]) -> Iterable[Media]:
    """Make a new Broadcasting index and add subtitles from the result to a previous result"""

    for other_lang in s.download_subtitles:
        if other_lang is True or other_lang == s.lang:
            continue

        # When getting subtitles from Latest Videos, lookup each video individually
        # since the list may differ between languages
        if s.latest:
            for media in media_items:
                try:
                    data = request_media(other_lang, media.key)
                    yield parse_media_data(s, data, other_lang, verbose=True)
                except InvalidMedia:
                    pass

        # Otherwise lookup a whole category recursively
        else:
            for cat in index_broadcasting(s, other_lang, ignore_missing=True):
                for media in cat.items:
                    yield media
