from os import makedirs
from shutil import disk_usage
from sys import stderr
from argparse import SUPPRESS


valid_args = {
    '--quiet': {
        'alternatives': ['-q'],
        'action': 'count',
        'default': 0,
        'help': 'Less info, can be used multiple times'},
    '--mode': {
        'choices': ['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
        'help': 'output mode',
        'dest': 'mode'},
    '--lang': {
        'default': 'E',
        'nargs': '?',
        'help': 'language code'},
    '--download': {
        'action': 'store_true',
        'help': 'download media files'},
    '--quality': {
        'default': 720,
        'type': int,
        'choices': [240, 360, 480, 720],
        'help': 'maximum video quality'},
    '--subtitles': {
        'action': 'store_true',
        'help': 'prefer subtitled videos'},
    '--no-subtitles': {
        'action': 'store_false',
        'dest': 'subtitles',
        'help': 'prefer un-subtitled videos'},
    '--checksum': {
        'action': 'store_true',
        'dest': 'checksums',
        'help': 'check md5 checksum'},
    '--no-checksum': {
        'action': 'store_false',
        'dest': 'checksums',
        'help': 'don\'t check md5 checksum'},
    '--free': {
        'default': 0,
        'type': int,
        'metavar': 'MiB',
        'dest': 'keep_free',
        'help': 'disk space in MiB to keep free (deletes older MP4 files)'},
    '--no-warning': {
        'dest': 'warn',
        'action': 'store_false',
        'help': 'do not warn when space limit seems wrong'},
    'work_dir': {
        # When nargs=? and the argument is left out, it stores None
        # We put SUPPRESS here so that it doesn't overwrite the previous value in that case
        'default': SUPPRESS,
        'nargs': '?',
        'metavar': 'DIR',
        'help': 'directory to save data in'}}


def add_arguments(parser, selected_args=None):
    """Add preset arguments to an argument parser

    :param parser: an instance of argparse.ArgumentParser
    :param selected_args: a list of keys from valid_args
    """
    if not selected_args:
        selected_args = valid_args.keys()

    for flag in sorted(selected_args):
        flags = [flag]
        # Add alternative flags as positional arguments to add_argument()
        # Example: add_argument('--quiet', '-q', action=count ...)
        if 'alternatives' in valid_args[flag]:
            flags = flags + valid_args[flag].pop('alternatives')
        parser.add_argument(*flags, **valid_args[flag])


def disk_usage_info(wd, keep_free: int, warn=True, quiet=0):
    """Display information about disk usage and maybe a warning

    :param wd: Working directory
    :param keep_free: Disk space in bytes to keep free
    :param warn: Show warning when keep_free seems too low
    :param quiet: Show disk usage information
    """
    # We create a directory here to prevent FileNotFoundError
    # if someone specified --free without --download they are dumb
    makedirs(wd,exist_ok=True)
    free = disk_usage(wd).free

    if quiet < 1:
        print('free space: {:} MiB, minimum limit: {:} MiB'.format(free//1024**2, keep_free//1024**2), file=stderr)

    if warn and free < keep_free:
        msg = '\nWarning:\n' \
              'The disk usage currently exceeds the limit by {} MiB.\n' \
              'If the limit was set too high, many or ALL videos may get deleted.\n' \
              'Press Enter to proceed or Ctrl+D to abort... '
        print(msg.format((keep_free-free) // 1024**2), file=stderr)
        try:
            input()
        except EOFError:
            exit(1)
