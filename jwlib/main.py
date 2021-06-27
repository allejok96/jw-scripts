import argparse
import time
from typing import Dict

import jwlib.parse
from jwlib.common import AbsolutePath, Path, Settings, action_factory, msg
from jwlib.constants import *
from jwlib.download import copy_files, download_all, download_all_subtitles, disk_usage_info
from jwlib.output import create_output
from jwlib.parse import Media, get_languages, get_categories, index_broadcasting, index_alternative_media


def verify_language(code):
    if code != 'E':
        if code not in get_languages():
            msg(code + ': invalid language code')
            exit(1)
    return code


def verify_languages(codes: str):
    code_list = codes.split(',')
    for code in code_list:
        verify_language(code)
    return code_list


def print_language(x):
    msg('language codes:')
    for code, values in get_languages().items():
        msg('{:>3}  {:<}'.format(code, values[0]))
    exit()


def main():
    usage = '''
  %(prog)s [options] [DIR]
  %(prog)s [options] --mode=filesystem --download [DIR]
  %(prog)s [options] --mode=html|m3u|txt [FILE]
  %(prog)s [options] --mode=run COMMAND [ARGS]'''

    epilog = '''
indexing modes:
  filesystem            create a directory structure (plex)
  html                  create a single HTML file
  m3u                   create a single playlist
  m3u_multi             create a playlist for each subcategory
  html_tree, m3u_tree   create hierarchy of HTML files or playlists
  run                   run a command
  stdout                print to the terminal
  txt                   create a text file'''

    p = argparse.ArgumentParser(prog='jwb-index',
                                usage=usage,
                                description='Index or download media from jw.org',
                                epilog=epilog,
                                formatter_class=argparse.RawDescriptionHelpFormatter,  # do not line-wrap epilog
                                argument_default=argparse.SUPPRESS)  # Do not overwrite attributes with None

    p.add_argument('--append', action='store_true',
                   help='append to index files instead of overwriting them')
    p.add_argument('--category', '-c', dest='include_categories', metavar='CODE',
                   action=action_factory(lambda x: x.split(',')),
                   help='comma separated list of categories to include')
    p.add_argument('--categories', '-C', nargs='?', const=CATEGORY_DEFAULT, metavar='CODE', dest='print_category',
                   help='display a list of valid category or subcategory names')
    p.add_argument('--checksum', action='store_true', dest='checksums',
                   help='validate MD5 checksums')
    p.add_argument('--clean-symlinks', action='store_true', dest='clean_all_symlinks',
                   help='remove all old symlinks (mode=filesystem)')
    p.add_argument('--download', '-d', action='store_true',
                   help='download media files')
    p.add_argument('--download-subtitles', '-s', nargs='?', const=True, metavar='LANG',
                   action=action_factory(verify_languages),
                   help='download subtitle files (optional comma separated list of languages)')
    p.add_argument('--exclude', metavar='CODE', dest='exclude_categories',
                   action=action_factory(lambda x: x.split(',')),
                   help='comma separated list of categories to skip (subcategories will also be skipped)')
    p.add_argument('--fix-broken', action='store_true', dest='overwrite_bad',
                   help='check existing files and re-download them if they are broken')
    p.add_argument('--free', type=int, metavar='MiB', dest='keep_free',
                   action=action_factory(lambda x: x * 1024 * 1024),  # MiB to B
                   help='disk space in MiB to keep free (warning: deletes old MP4 files, use separate folder!)')
    p.add_argument('--friendly', '-H', action='store_true', dest='friendly_filenames',
                   help='save downloads with human readable names (alternative to --mode=filesystem)')
    p.add_argument('--hard-subtitles', action='store_true',
                   help='prefer videos with hard-coded subtitles')
    p.add_argument('--import', dest='import_dir', metavar='DIR',
                   action=action_factory(lambda x: Path(x)),
                   help='import media files from this directory (offline update)')
    p.add_argument('--index-dir', metavar='DIR',
                   action=action_factory(lambda x: AbsolutePath(x)),
                   help='directory to store index files in')
    p.add_argument('--lang', '-l', action=action_factory(verify_language),
                   help='language code')
    p.add_argument('--languages', '-L', nargs=0, action=action_factory(print_language),
                   help='display a list of valid language codes')
    p.add_argument('--latest', action='store_true',
                   help='index the "Latest Videos" category only')
    p.add_argument('--limit-rate', '-R', metavar='RATE', type=float, dest='rate_limit',
                   help='maximum download rate, in megabytes/s (default = 1 MB/s, 0 = no limit)')
    p.add_argument('--media-dir', metavar='DIR',
                   action=action_factory(lambda x: AbsolutePath(x)),
                   help='directory to store media files in')
    p.add_argument('--mode', '-m',
                   choices=MODES,
                   help='what to do with the indexed data (see below)')
    p.add_argument('--no-warning', dest='warning', action='store_false',
                   help='do not warn when space limit seems wrong')
    p.add_argument('--quality', '-Q', type=int,
                   choices=[240, 360, 480, 720],
                   help='maximum video quality')
    p.add_argument('--quiet', '-q', action='count',
                   help='less info, can be used multiple times')
    p.add_argument('--since', metavar='YYYY-MM-DD', dest='min_date',
                   action=action_factory(lambda x: time.mktime(time.strptime(x, '%Y-%m-%d'))),
                   help='only include media newer than this date')
    p.add_argument('--sort',
                   choices=SORTS,
                   help='sort output')
    p.add_argument('--update', action='store_true',
                   help='update existing index with the latest videos (implies --append --latest --sort=newest)')
    p.add_argument('positional_arguments', nargs='*', metavar='DIR|FILE|COMMAND',
                   help='where to send output (depends on mode)')

    #
    # Argument parsing / validation
    #

    s = p.parse_args(namespace=Settings())

    # Quick print of categories list (stops here)
    if s.print_category:
        print(*get_categories(s, s.print_category), sep='\n')
        exit()

    # Required arguments
    if not (s.mode or s.download or s.download_subtitles or s.import_dir):
        msg('please use --mode or --download')
        exit(1)

    # Implicit arguments
    if s.update:
        s.append = True
        s.latest = True
        if not s.sort:
            s.sort = SORT_NEW
    if s.latest:
        for key in s.include_categories:
            if key != CATEGORY_DEFAULT:
                # Add key and its sub categories to the filter
                s.filter_categories.append(key)
                if s.quiet < 1:
                    msg('preparing filter: ' + key)
                s.filter_categories += get_categories(s, key)
        s.include_categories = [CATEGORY_LATEST]

    # Handle positional arguments depending on mode
    # COMMAND [ARGS]
    if s.mode == M_RUN:
        if not s.positional_arguments:
            msg('--mode=run requires a command')
            exit(1)
        s.command = s.positional_arguments

    elif len(s.positional_arguments) == 1:
        path = Path(s.positional_arguments[0])
        # FILE
        if s.mode in MODES_WITH_SINGLE_FILE and not path.is_dir():
            s.output_filename = path.name
            s.work_dir = path.parent
        # DIR
        else:
            s.work_dir = path

    elif len(s.positional_arguments) > 1:
        msg('unexpected argument: {}'.format(s.positional_arguments[1]))
        exit(1)

    # Ugly way to configure parser
    jwlib.parse.FRIENDLY_FILENAMES = s.friendly_filenames

    #
    # Path checks / creation
    #

    if not s.work_dir.is_dir():
        msg('not a directory: ' + str(s.work_dir))
        exit(1)

    if s.media_dir is None:
        if s.mode in MODES_WITH_MEDIA_SUBDIR:
            s.media_dir = s.work_dir / 'jwb-data' / 'media'
            # Backwards compatibility
            old_media_dir = s.work_dir / ('jwb-' + s.lang)
            if not s.media_dir.exists() and any(old_media_dir.glob('*.mp4')):
                msg('deprecation warning: media stored in {} (should be in {})'.format(old_media_dir, s.media_dir))
                s.media_dir = old_media_dir
        else:
            s.media_dir = s.work_dir
        if s.download or s.download_subtitles or s.import_dir:
            s.media_dir.mkdir(parents=True, exist_ok=True)
    elif not s.media_dir.is_dir():
        msg('directory does not exist: ' + str(s.media_dir))
        exit(1)

    if s.index_dir is None:
        if s.mode in MODES_WITH_INDEX_SUBDIR:
            s.index_dir = s.work_dir / 'jwb-data' / 'index' / s.lang
            # Backwards compatibility
            old_index_dir = s.work_dir / ('jwb-' + s.lang)
            if not s.index_dir.exists() and old_index_dir.exists():
                msg('deprecation warning: index stored in {} (should be in {})'.format(old_index_dir, s.index_dir))
                s.index_dir = old_index_dir
            s.index_dir.mkdir(parents=True, exist_ok=True)
        else:
            s.index_dir = s.work_dir
    elif not s.index_dir.is_dir():
        msg('directory does not exist: ' + str(s.index_dir))
        exit(1)

    #
    # Filesystem checks
    #

    # Warning if disk space is already below limit
    if (s.download or s.import_dir) and s.keep_free > 0:
        disk_usage_info(s)

    # Offline import (stops here)
    if s.import_dir:
        copy_files(s)
        exit()

    # NTFS compatibility (try to create a forbidden file)
    try:
        for directory in s.work_dir, s.index_dir, s.media_dir:
            try:
                (directory / '?').touch(exist_ok=False)
                (directory / '?').unlink()
            except FileExistsError:
                pass
    except OSError:
        jwlib.parse.SAFE_FILENAMES = True

    # Some heads-up
    if s.quiet < 1:
        if s.download and s.rate_limit:
            msg('note: download rate limit is active')
        if jwlib.parse.SAFE_FILENAMES:
            msg('note: using NTFS/FAT compatible file names')

    #
    # Start of main... thing
    #

    index = index_broadcasting(s)

    # Get all unique Media objects
    all_media: Dict[str, Media] = {media.key: media for cat in index for media in cat.items}

    # Sort newest first, this is important for --free to work as expected
    download_queue = sorted(all_media.values(), key=lambda x: x.date or 0, reverse=True)

    # Index other languages and merge subtitles from that into current
    if s.download_subtitles:
        for other in index_alternative_media(s, all_media.values()):
            try:
                all_media[other.key].subtitles.update(other.subtitles)
            except KeyError:
                pass

        download_all_subtitles(s, download_queue)

    if s.download:
        download_all(s, download_queue)

    if s.mode:
        create_output(s, index)


if __name__ == '__main__':
    main()
