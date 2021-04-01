import argparse
import json
import time
import urllib.request

from jwlib.common import Path, Settings, action_factory, msg
from jwlib.download import copy_files, download_all, disk_usage_info
from jwlib.output import create_output
from jwlib.parse import parse_broadcasting, get_categories


def get_jwb_languages():
    """Returns [ {'code': str, 'name': str}, ... ]"""

    url = 'https://data.jw-api.org/mediator/v1/languages/E/web?clientType=www'
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode('utf-8'))['languages']


def verify_language(code):
    if code != 'E':
        for l in get_jwb_languages():
            if l['code'] == code:
                break
        else:
            raise ValueError(code + ': invalid language code')
    return code


def print_language(x):
    msg('language codes:')
    for l in get_jwb_languages():
        msg('{:>3}  {:<}'.format(l['code'], l['name']))
    exit()


def main():
    usage = '''
      %(prog)s [options] [DIR]
      %(prog)s [options] --mode=html|m3u|txt [FILE]
      %(prog)s [options] --mode=run COMMAND [ARGS]'''

    p = argparse.ArgumentParser(prog='jwb-index',
                                usage=usage,
                                description='Index or download media from jw.org',
                                argument_default=argparse.SUPPRESS)  # Do not overwrite attributes with None

    p.add_argument('--append', action='store_true',
                   help='append to file instead of overwriting')
    p.add_argument('--category', '-c', dest='include_categories', metavar='CODE',
                   action=action_factory(lambda x: x.split(',')),
                   help='comma separated list of categories to index')
    p.add_argument('--checksum', action='store_true', dest='checksums',
                   help="validate MD5 checksums")
    p.add_argument('--clean-symlinks', action='store_true', dest='clean_all_symlinks',
                   help='remove all old symlinks (mode=filesystem)')
    p.add_argument('--download', '-d', action='store_true',
                   help='download media files')
    p.add_argument('--download-subtitles', action='store_true',
                   help='download VTT subtitle files')
    p.add_argument('--exclude', metavar='CODE', dest='exclude_categories',
                   action=action_factory(lambda x: x.split(',')),
                   help='comma separated list of categories to skip (sub-categories will also be skipped)')
    p.add_argument('--fix-broken', action='store_true', dest='overwrite_bad',
                   help='check existing files and re-download them if they are broken')
    p.add_argument('--free', type=int, metavar='MiB', dest='keep_free',
                   action=action_factory(lambda x: x * 1024 * 1024),  # MiB to B
                   help='disk space in MiB to keep free (warning: deletes old MP4 files, use separate folder!)')
    p.add_argument('--friendly', '-H', action='store_true', dest='friendly_filenames',
                   help='save downloads with human readable names')
    p.add_argument('--hard-subtitles', action='store_true',
                   help='prefer videos with hard-coded subtitles')
    p.add_argument('--import', dest='import_dir', metavar='DIR',
                   help='import of media files from this directory (offline)')
    p.add_argument('--lang', '-l', action=action_factory(verify_language),
                   help='language code')
    p.add_argument('--languages', '-L', nargs=0, action=action_factory(print_language),
                   help='display a list of valid language codes')
    p.add_argument('--latest', action='store_true',
                   help='index the "Latest Videos" category only')
    p.add_argument('--limit-rate', '-R', metavar='RATE', type=float, dest='rate_limit',
                   help='maximum download rate, in megabytes/s (default = 1 MB/s, 0 = no limit)')
    p.add_argument('--list-categories', '-C', nargs='?', const='VideoOnDemand', metavar='CODE', dest='print_category',
                   help='print a list of (sub) category names')
    p.add_argument('--mode', '-m',
                   choices=['filesystem', 'html', 'html_tree', 'm3u', 'm3u_multi', 'm3u_tree', 'run', 'stdout', 'txt'],
                   help='output mode (see wiki)')
    p.add_argument('--no-warning', dest='warning', action='store_false',
                   help='do not warn when space limit seems wrong')
    p.add_argument('--ntfs', '-X', action='store_true', dest='safe_filenames',
                   help='use NTFS/FAT compatible file names, and absolute paths for symlinks')
    p.add_argument('--quality', '-Q', type=int,
                   choices=[240, 360, 480, 720],
                   help='maximum video quality')
    p.add_argument('--quiet', '-q', action='count',
                   help='Less info, can be used multiple times')
    p.add_argument('--since', metavar='YYYY-MM-DD', dest='min_date',
                   action=action_factory(lambda x: time.mktime(time.strptime(x, '%Y-%m-%d'))),
                   help='only index media newer than this date')
    p.add_argument('--sort',
                   choices=['newest', 'oldest', 'name', 'random'],
                   help='sort output')
    p.add_argument('--update', action='store_true',
                   help='update existing categories with the latest videos (implies --append --latest --sort=newest)')
    p.add_argument('positional_arguments', nargs='*', metavar='DIR|FILE|COMMAND',
                   help='where to send output (depends on mode)')

    s = p.parse_args(namespace=Settings())

    # Quick print of categories list
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
            s.sort = 'newest'
    if s.latest:
        for key in s.include_categories:
            if key != 'VideoOnDemand':
                # Add key and its sub categories to the filter
                s.filter_categories.append(key)
                if s.quiet < 1:
                    msg('preparing filter: ' + key)
                s.filter_categories += get_categories(s, key)
        s.include_categories = ['LatestVideos']

    # Handle positional arguments depending on mode
    # COMMAND [ARGS]
    if s.mode == 'run':
        if not s.positional_arguments:
            msg('--mode=run requires a command')
            exit(1)
        s.command = s.positional_arguments

    elif len(s.positional_arguments) == 1:
        path = Path(s.positional_arguments[0])
        # FILE
        if s.mode in ('txt', 'm3u', 'html') and not path.is_dir():
            s.output_filename = path.name
            s.work_dir = path.parent
        # DIR
        else:
            s.work_dir = path

    elif len(s.positional_arguments) > 1:
        msg('unexpected argument: {}'.format(s.positional_arguments[1]))
        exit(1)

    # Check / set paths
    if not s.work_dir.is_dir():
        msg('not a directory: ' + s.work_dir.str)
        exit(1)

    if s.mode not in ('', 'stdout'):
        s.sub_dir = 'jwb-' + s.lang

    # Warning if disk space is already below limit
    if (s.download or s.import_dir) and s.keep_free > 0:
        disk_usage_info(s)

    # Offline import (stops here)
    if s.import_dir:
        copy_files(s)
        exit()

    # Some heads-up
    if s.quiet < 1:
        if s.download and s.rate_limit:
            msg('note: download rate limit is active')
        if not s.safe_filenames and (s.mode not in ('', 'stdout') or s.friendly_filenames):
            msg('note: NTFS/FAT compatibility is off')

    # Do the indexing
    data = parse_broadcasting(s)

    if s.download or s.download_subtitles:
        download_all(s, data)

    if s.mode:
        create_output(s, data)


if __name__ == '__main__':
    main()
