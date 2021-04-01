import argparse
import os
import pathlib
import sys


def msg(s):
    print(s, file=sys.stderr, flush=True)


def action_factory(function):
    """Create an argparse.Action that will run the argument through a function before storing it"""

    class CustomAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            result = function(values)
            setattr(namespace, self.dest, result)

    return CustomAction


# Ugly hack to fix ugly hack in pathlib
# Path.__new__() returns PosixPath or WindowsPath based on the OS.
# But this functionality is not inherited by subclasses of Path,
# so we piggy-back on the parent class and call type() to get the correct one.
# The second Path class is for typing in PyCharm only :)
class Path(type(pathlib.Path()), pathlib.Path):
    """pathlib.Path with extra stuff"""

    @property
    def str(self):
        """For use when string is required (Python 3.5 does not support pathlike objects)"""
        return self.__str__()

    @property
    def size(self):
        """Size in bytes"""
        return self.stat().st_size

    @property
    def mtime(self):
        """Modification time"""
        return self.stat().st_mtime

    def set_mtime(self, time: int):
        """Update modification time and access time"""
        os.utime(self.__str__(), (time, time))

    def is_mp4(self):
        """True if this is an MP4 file"""
        return self.is_file() and self.suffix.lower() == '.mp4'


class Settings:
    """Global settings and defaults"""

    quiet = 0
    list_languages = False

    # Depending on mode
    positional_arguments = []
    work_dir = Path('.')
    sub_dir = ''
    output_filename = ''
    command = []

    # API parsing stuff
    lang = 'E'
    quality = 1080
    hard_subtitles = False
    min_date = 0  # 1970-01-01
    include_categories = ['VideoOnDemand']
    exclude_categories = ['VODSJJMeetings']
    filter_categories = []
    print_category = ''
    latest = False

    # Disk space check stuff
    keep_free = 0  # bytes
    warning = True  # warn if limit is set too low

    import_dir = None  # type: Path

    # Download stuff
    download = False
    download_subtitles = False
    friendly_filenames = False
    rate_limit = 1.0  # MB/s
    checksums = False
    overwrite_bad = False

    # Output stuff
    append = False
    clean_all_symlinks = False
    update = False
    mode = ''
    safe_filenames = False
    sort = ''

    def __setattr__(self, key, value):
        # This will raise an error if the attribute we are trying to set doesn't already exist
        getattr(self, key)
        super().__setattr__(key, value)
