#!/usr/bin/env python3
import argparse

import jwlib


parser = argparse.ArgumentParser(prog='jwb-index.py',
                                 usage='%(prog)s [options] [DIR]',
                                 description='Index or download media from tv.jw.org')
# TODO
parser.add_argument('--config')
parser.add_argument('--clean',
                    action='store_true')
parser.add_argument('--quiet',
                    action='count')
parser.add_argument('--mode',
                    default='stdout',
                    choices=['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html', 'downloader'],
                    help='output mode')
parser.add_argument('--lang',
                    nargs='?',
                    default='E',
                    help='language code')
parser.add_argument('--category',
                    default='VideoOnDemand',
                    dest='category',
                    help='category/section to index')
parser.add_argument('--latest',
                    action='store_const',
                    const='LatestVideos',
                    dest='category')
parser.add_argument('--quality',
                    default=720,
                    type=int,
                    choices=[240, 360, 480, 720],
                    help='maximum video quality')
parser.add_argument('--subtitles',
                    action='store_true')
parser.add_argument('--no-subtitles',
                    action='store_false',
                    dest='subtitles',
                    help='prefer un-subtitled videos')
parser.add_argument('--download',
                    action='store_true',
                    help='download media')
parser.add_argument('--limit-rate',
                    default='1M',
                    dest='rate_limit')
parser.add_argument('--since',
                    metavar='YYYY-MM-DD')
parser.add_argument('--checksum',
                    action='store_true',
                    help='check md5 checksum')
parser.add_argument('--no-checksum',
                    action='store_false',
                    help='check md5 checksum')
parser.add_argument('work_dir',
                    nargs='?',
                    default=None,
                    metavar='DIR',
                    help='directory to save data in')

jwb = jwlib.JWBroadcasting()
parser.parse_args(namespace=jwb)

# jwb.mode and jwb.work_dir gets set by argparse
wd = jwb.work_dir
sd = 'jwb-' + jwb.lang

if jwb.mode == 'stdout':
    output = jwlib.OutputStdout(wd)

elif jwb.mode == 'm3u':
    output = jwlib.OutputM3U(wd, sd)

elif jwb.mode == 'm3ucompat':
    output = jwlib.OutputM3UCompat(wd, sd)

elif jwb.mode == 'filesystem':
    output = jwlib.OutputFilesystem(wd, sd)
    output.clean_symlinks()

elif jwb.mode == 'html':
    output = jwlib.OutputHTML(wd, sd)

elif jwb.mode == 'downloader':
    output = jwlib.OutputQueue(wd)
    jwb.download = True
    # Turn of downloading and checking for now
    jwb.dry_run = True


# Note:
# output cannot be anything else, argparse takes care of that


jwb.parse(output)


if jwb.mode == 'downloader':
    # Sort media with newest videos first
    sorted_queue = sorted(output.queue, key=lambda x: x.date, reverse=True)
    # Turn on downloading and checking
    jwb.dry_run = False
    # Download all media and output to stdout
    for media_obj in sorted_queue:
        file = jwb.download_media(media_obj, jwb.work_dir)
        if file or True:
            print(file)
