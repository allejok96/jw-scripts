#!/usr/bin/env python3
import argparse
import jwindex


parser = argparse.ArgumentParser(prog='jwb-index.py', usage='%(prog)s [options] [DIR]',
                                 description='Index or download media from tv.jw.org')
# TODO
parser.add_argument('--config')

parser.add_argument('--clean', action='store_true')

parser.add_argument('--quiet', action='store_true')

parser.add_argument('--mode', default='stdout', choices=['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
                    help='output mode')

parser.add_argument('--lang', nargs='?', default='E',
                    help='language code')

parser.add_argument('--category', default='VideoOnDemand', dest='category',
                    help='category/section to index')

parser.add_argument('--latest', action='store_const', const='LatestVideos', dest='category')

parser.add_argument('--quality', default=720, type=int, choices=[240, 360, 480, 720],
                    help='maximum video quality')

parser.add_argument('--subtitles', action='store_true')

parser.add_argument('--no-subtitles', action='store_false', dest='subtitles',
                    help='prefer un-subtitled videos')

parser.add_argument('--download', action='store_true',
                    help='download media')

parser.add_argument('--limit-rate', default='1M', dest='rate_limit')

parser.add_argument('--since', metavar='YYYY-MM-DD')

parser.add_argument('--checksum', action='store_true',
                    help='check md5 checksum')

parser.add_argument('--no-checksum', action='store_false',
                    help='check md5 checksum')

parser.add_argument('work_dir', nargs='?', default=None, metavar='DIR',
                    help='directory to save data in')

jwb = jwindex.JWBroadcasting()
parser.parse_args(namespace=jwb)

m = jwb.mode # set by argparse
wd = jwb.work_dir # set by argparse
sd = 'jwb-' + jwb.lang

if m == 'stdout':
    output = jwindex.OutputStdout(wd)

elif m == 'm3u':
    output = jwindex.OutputM3U(wd, sd)

elif m == 'm3ucompat':
    output = jwindex.OutputM3UCompat(wd, sd)

elif m == 'filesystem':
    output = jwindex.OutputFilesystem(wd, sd)
    output.clean_symlinks()

elif m == 'html':
    output = jwindex.OutputHTML(wd, sd)

# Note:
# output cannot be anything else, argparse takes care of that

jwb.parse(output)
