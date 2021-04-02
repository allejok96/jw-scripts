import argparse
import os
import pathlib
import sys

from typing import List


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

    # Typing like crazy because PyCharm won't believe me otherwise

    quiet = 0  # type: int
    list_languages = False  # type: bool

    # Depending on mode
    positional_arguments = []  # type: List[str]
    work_dir = Path('.')  # type: Path
    sub_dir = ''  # type: str
    output_filename = ''  # type: str
    command = []  # type: List[str]

    # API parsing stuff
    lang = 'E'  # type: str
    quality = 1080  # type: int
    hard_subtitles = False  # type:bool
    min_date = 0  # type: int # 1970-01-01
    include_categories = ['VideoOnDemand']  # type: List[str]
    exclude_categories = ['VODSJJMeetings']  # type: List[str]
    filter_categories = []  # type: List[str]
    print_category = ''  # type: str
    latest = False  # type: bool

    # Disk space check stuff
    keep_free = 0  # type: int # bytes
    warning = True  # type: bool # warn if limit is set too low

    import_dir = None  # type: Path

    # Download stuff
    download = False  # type: bool
    download_subtitles = False  # type: bool
    friendly_filenames = False  # type: bool
    rate_limit = 1.0  # type: float # MB/s
    checksums = False  # type: bool
    overwrite_bad = False  # type: bool

    # Output stuff
    append = False  # type: bool
    clean_all_symlinks = False  # type: bool
    update = False  # type: bool
    mode = ''  # type: str
    safe_filenames = False  # type: bool
    sort = ''  # type: str

    def __setattr__(self, key, value):
        # This will raise an error if the attribute we are trying to set doesn't already exist
        getattr(self, key)
        super().__setattr__(key, value)
