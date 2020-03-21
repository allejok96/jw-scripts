from sys import stderr
import time
import re
import json
import urllib.request
import urllib.parse
from typing import List, Union

from .arguments import JwbSettings


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


def parse_broadcasting(s: JwbSettings):
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


def parse_jwpub(pub='bi12', start_book=0, lang='E', quiet=0):
    """Index JW org sound recordings and return a list with Category objects

    :param pub: Publication code
    :param start_book: Book of the bible
    :param lang: Language code
    :param quiet: level of quietness
    """
    result = []

    url_template = 'https://apps.jw.org/GETPUBMEDIALINKS' \
                   '?output=json&fileformat=MP3&alllangs={a}&langwritten={L}&txtCMSLang={L}&pub={p}'

    # Watchtower/Awake reference is split up into pub and issue
    magazine_match = re.match('(wp?|g)([0-9]+)', pub)
    if magazine_match:
        url_template = url_template + '&issue={i}'
        pub = magazine_match.group(1)
        queue = [magazine_match.group(2)]
    else:
        url_template = url_template + '&booknum={i}'
        queue = [start_book]

    # Check language code
    # This must be done after the magazine stuff
    # We want the languages for THAT publication only, or else the list gets SOO long
    # The language is checked on the first pub in the queue
    url = url_template.format(L='E', p=pub, i=queue[0], a='1')

    with urllib.request.urlopen(url) as response:
        response = json.loads(response.read().decode('utf-8'))

        if not lang:
            # Print table of language codes
            msg('language codes:')
            for l in sorted(response['languages'], key=lambda x: response['languages'][x]['name']):
                msg('{:>3}  {:<}'.format(l, response['languages'][l]['name']))
            exit()
        else:
            # Check if the code is valid
            if lang not in response['languages']:
                raise ValueError(lang + ': invalid language code')

    for key in queue:
        url = url_template.format(L=lang, p=pub, i=key, a=0)

        book = Category()
        result.append(book)

        if pub == 'bi12' or pub == 'nwt':
            book.key = format(int(key), '02')
            # This is the starting point if the value in the queue
            # is the same as the one the user specified
            book.home = key == start_book
        else:
            book.key = pub
            book.home = True

        with urllib.request.urlopen(url) as response:
            response = json.loads(response.read().decode('utf-8'))
            book.name = response['pubName']

            if quiet < 1:
                msg('{} ({})'.format(book.key, book.name))

            # For the Bible's index page
            # Add all books to the queue
            if key == 0 and (pub == 'bi12' or pub == 'nwt'):
                for sub_book in response['files'][lang]['MP3']:

                    s = Category()
                    s.key = format(sub_book['booknum'], '02')
                    s.name = sub_book['title']
                    book.contents.append(s)

                    if s.key not in queue:
                        queue.append(s.key)
            else:
                for chptr in response['files'][lang]['MP3']:
                    # Skip the ZIP
                    if chptr['mimetype'] != 'audio/mpeg':
                        continue

                    m = Media()
                    m.url = chptr['file']['url']
                    m.name = chptr['title']
                    if 'filesize' in chptr:
                        m.size = chptr['filesize']

                    book.contents.append(m)

    return result
