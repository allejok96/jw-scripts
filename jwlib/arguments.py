import shutil
from sys import stderr


valid_args = {
    '--quiet': {'action': 'count'},
    '--mode': {
        'choices': ['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
        'help': 'output mode',
        'dest': 'mode'},
    '--lang': {
        'nargs': '?',
        'help': 'language code'},
    '--download': {
        'action': 'store_true',
        'help': 'download media files'},
    '--limit-rate': {
        'dest': 'rate_limit',
        'help': 'maximum download rate, passed to curl'},
    '--quality': {
        'type': int,
        'choices': [240, 360, 480, 720],
        'help': 'maximum video quality'},
    '--subtitles': {
        'action': 'store_true',
        'help': 'prefer subtitled videos'},
    '--no-subtitles': {
        'action': 'store_false',
        'dest': 'subtitles'},
    '--checksum': {
        'action': 'store_true',
        'dest': 'checksums',
        'help': 'check md5 checksum'},
    '--no-checksum': {
        'action': 'store_false'},
    '--free': {
        'type': int,
        'metavar': 'MB',
        'dest': 'keep_free',
        'help': 'disk space in MB to keep free (deletes older MP4 files)'},
    '--no-warning': {
        'dest': 'warn',
        'action': 'store_false',
        'help': 'do not warn when space limit seems wrong'},
    'work_dir': {
        # "default" must be set here, or work_dir will be set to None.
        # Setting work_dir before calling parse_args() has no effect,
        # other than making PyCharm satisfied.
        'default': '.',
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

    for arg in sorted(selected_args):
        parser.add_argument(arg, **valid_args[arg])


def disk_usage_info(wd, keep_free: int, warn=True, quiet=0):
    """Display information about disk usage and maybe a warning

    :param wd: Working directory
    :param keep_free: Disk space in bytes to keep free
    :param warn: Show warning when keep_free seems too low
    :param quiet: Show disk usage information
    """
    free = shutil.disk_usage(wd).free
    if quiet == 0:
        print('free space: {:} MB, minimum limit: {:} MB'.format(free//1000**2, keep_free//1000**2), file=stderr)

    if warn and free < keep_free:
        msg = '\nWarning:\n' \
              'The disk usage currently exceeds the limit by {} MB.\n' \
              'If the limit was set too high, many or ALL videos may get deleted.\n' \
              'Press Enter to proceed or Ctrl+D to abort... '
        print(msg.format((keep_free-free) // 1000**2), file=stderr)
        try:
            input()
        except EOFError:
            exit(1)
