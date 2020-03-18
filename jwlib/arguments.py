import json
import urllib.request
import argparse
from os import makedirs
from shutil import disk_usage
from sys import stderr
from typing import Tuple


class JwbSettings:
    """Global settings, set from script arguments"""

    # General stuff
    work_dir = '.'
    quiet = 0
    list_languages = False

    # API parsing stuff
    lang = 'E'
    quality = 1080
    subtitles = False
    min_date = None  # type: int
    include_categories = ()  # type: Tuple[str]
    exclude_categories = ()  # type: Tuple[str]

    # Disk space check stuff
    keep_free = 0  # bytes
    # Warn if limit is set too low
    warning = True

    # Download stuff
    download = False
    curl_path = 'curl'
    rate_limit = '0'
    checksums = True

    # Output stuff
    sub_dir = ''
    mode = None  # type: str
    # NTFS friendly
    safe_filenames = False
    # Prepend the codename (filesystem)
    include_keyname = False
    # Remove non-broken symlinks (filesystem)
    clean_all_symlinks = False

    def __setattr__(self, key, value):
        # This will raise an error if the attribute we are trying to set doesn't already exist
        getattr(self, key)
        super().__setattr__(key, value)


def get_jwb_languages():
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
    print('language codes:', file=stderr)
    for l in get_jwb_languages():
        print('{:>3}  {:<}'.format(l['code'], l['name']), file=stderr)
    exit()


def action_factory(function):
    """Create an Action class for passing to for ArgumentParser

    :param function: ArgumentParser will run the argument through this function before saving it to the namespace
    """

    class CustomAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            result = function(values)
            setattr(namespace, self.dest, result)

    return CustomAction


class DefaultArgumentParser(argparse.ArgumentParser):
    """Same as ArgumentParser, but it returns a Settings instance and does not touch default values of it

    Also has a quick way to add common arguments.
    """

    def __init__(self, *args, argument_default=None, **kwargs):
        super().__init__(*args, argument_default=argparse.SUPPRESS, **kwargs)

    default_arguments = {
        '--quiet': {
            'alternatives': ['-q'],
            'action': 'count',
            'default': 0,
            'help': 'Less info, can be used multiple times'},
        '--mode': {
            'alternatives': ['-m'],
            'choices': ['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
            'help': 'output mode'},
        '--lang': {
            'alternatives': ['-l'],
            'default': 'E',
            'action': action_factory(verify_language),
            'nargs': '?',
            'help': 'language code'},
        '--languages': {
            'action': action_factory(print_language),
            'help': 'display a list of valid language codes'},
        '--download': {
            'alternatives': ['-d'],
            'action': 'store_true',
            'help': 'download media files'},
        '--quality': {
            'alternatives': ['-Q'],
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
            'dest': 'checksum',
            'help': 'don\'t check md5 checksum'},
        '--free': {
            'default': 0,
            'type': int,
            'metavar': 'MiB',
            'action': action_factory(lambda x: x * 1024 * 1024),  # MiB to B
            'dest': 'keep_free',
            'help': 'disk space in MiB to keep free (deletes older MP4 files)'},
        '--no-warning': {
            'dest': 'warning',
            'action': 'store_false',
            'help': 'do not warn when space limit seems wrong'},
        'work_dir': {
            'default': '.',
            'nargs': '?',
            'metavar': 'DIR',
            'help': 'directory to save data in'}}

    def add_default_arguments(self, flags):
        for flag in flags:
            if 'alternatives' in self.default_arguments[flag]:
                arg_options = self.default_arguments[flag]
                alt_flags = arg_options.pop('alternatives')
                # Example of alt_flags usage:
                # add_argument('--quiet', '-q', action=count ...)
                self.add_argument(flag, *alt_flags, **arg_options)
            else:
                self.add_argument(flag, **self.default_arguments[flag])

    def parse_args(self, *args, namespace=None, **kwargs):
        settings = JwbSettings()
        super().parse_args(*args, namespace=settings, **kwargs)
        return settings


def disk_usage_info(s: JwbSettings):
    """Display information about disk usage and maybe a warning"""

    # We create a directory here to prevent FileNotFoundError
    # if someone specified --free without --download they are dumb
    makedirs(s.work_dir, exist_ok=True)
    free = disk_usage(s.work_dir).free

    if s.quiet < 1:
        print('free space: {:} MiB, minimum limit: {:} MiB'.format(free // 1024 ** 2, s.keep_free // 1024 ** 2),
              file=stderr)

    if s.warning and free < s.keep_free:
        msg = '\nWarning:\n' \
              'The disk usage currently exceeds the limit by {} MiB.\n' \
              'If the limit was set too high, many or ALL videos may get deleted.\n' \
              'Press Enter to proceed or Ctrl+D to abort... '
        print(msg.format((s.keep_free - free) // 1024 ** 2), file=stderr)
        try:
            input()
        except EOFError:
            exit(1)
