from os import makedirs
from shutil import disk_usage
from sys import stderr
from argparse import SUPPRESS, ArgumentParser


class DefaultArgumentParser(ArgumentParser):
    default_arguments = {
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

    def add_default_arguments(self, flags):
        for flag in flags:
            if 'alternatives' in self.default_arguments[flag]:
                arg_options = self.default_arguments[flag]
                alt_flags = arg_options.pop('alternatives')
                # Example: add_argument('--quiet', '-q', action=count ...)
                self.add_argument(flag, *alt_flags, arg_options)
            else:
                self.add_argument(flag, **self.default_arguments[flag])


def disk_usage_info(wd, keep_free: int, warn=True, quiet=0):
    """Display information about disk usage and maybe a warning

    :param wd: Working directory
    :param keep_free: Disk space in bytes to keep free
    :param warn: Show warning when keep_free seems too low
    :param quiet: Show disk usage information
    """
    # We create a directory here to prevent FileNotFoundError
    # if someone specified --free without --download they are dumb
    makedirs(wd, exist_ok=True)
    free = disk_usage(wd).free

    if quiet < 1:
        print('free space: {:} MiB, minimum limit: {:} MiB'.format(free // 1024 ** 2, keep_free // 1024 ** 2),
              file=stderr)

    if warn and free < keep_free:
        msg = '\nWarning:\n' \
              'The disk usage currently exceeds the limit by {} MiB.\n' \
              'If the limit was set too high, many or ALL videos may get deleted.\n' \
              'Press Enter to proceed or Ctrl+D to abort... '
        print(msg.format((keep_free - free) // 1024 ** 2), file=stderr)
        try:
            input()
        except EOFError:
            exit(1)
