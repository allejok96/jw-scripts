from sys import stderr
import time
import re
import json
import urllib.request
import urllib.parse
from typing import List, Union

from .arguments import Settings


class Category:
    """Object to put category info in."""
    key = None  # type: str
    name = None  # type: str
    home = False  # whether or not this is a "starting point"

    def __init__(self):
        self.contents = []  # type: List[Union[Category, Media]]


class Media:
    """Object to put media info in."""

    url = None  # type: str
    name = None  # type: str
    md5 = None  # type: str
    date = None  # type: int
    size = None  # type: int
    file = None  # type: str
    subtitle_url = None  # type: str


def msg(s):
    print(s, file=stderr, flush=True)


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
    rankings.sort()

    # [-1] The file with the highest rank, [1] the filename, not the rank
    # If there was no files, it will raise IndexError
    return rankings[-1][1]


def parse_broadcasting(s: Settings):
    """Index JW Broadcasting categories recursively and return a list with Category objects

    :param s: Global settings object
    """
    result = []

    # Make a copy of the list, because we'll append stuff here later
    queue = list(s.include_categories)
    for key in queue:

        url = 'https://data.jw-api.org/mediator/v1/categories/{L}/{c}?detailed=1&clientType=www'
        url = url.format(L=s.lang, c=key)

        with urllib.request.urlopen(url) as j_raw:  # j as JSON
            j = json.loads(j_raw.read().decode('utf-8'))

            if j.get('status') == '404':
                raise ValueError('No such category or language')

            cat = Category()
            result.append(cat)
            cat.key = j['category']['key']
            cat.name = j['category']['name']
            cat.home = cat.key in s.include_categories

            if s.quiet < 1:
                msg('{} ({})'.format(cat.key, cat.name))

            for j_sub in j['category'].get('subcategories', []):
                sub = Category()
                sub.key = j_sub['key']
                sub.name = j_sub['name']
                cat.contents.append(sub)
                # Add subcategory key to queue for parsing later
                if sub.key not in queue:
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
                    continue

                media = Media()
                media.url = j_media_file['progressiveDownloadURL']
                media.name = j_media['title']
                media.md5 = j_media_file.get('checksum')
                media.size = j_media_file.get('filesize')
                if j_media_file.get('subtitles'):
                    media.subtitle_url = j_media_file['subtitles']['url']

                # Save time data
                if 'firstPublished' in j_media:
                    try:
                        # Remove last stuff from date, what is it anyways?
                        date_string = re.sub('\\.[0-9]+Z$', '', j_media['firstPublished'])
                        # Try to convert it to seconds
                        date = time.mktime(time.strptime(date_string, '%Y-%m-%dT%H:%M:%S'))
                        if s.min_date and date < s.min_date:
                            continue
                        media.date = date
                    except ValueError:
                        pass

                cat.contents.append(media)

    return result