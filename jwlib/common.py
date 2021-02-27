import argparse
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


class Settings:
    """Global settings and defaults"""

    quiet = 0
    list_languages = False

    # Depending on mode
    positional_arguments = []
    work_dir = '.'
    sub_dir = ''
    output_filename = ''
    command = []

    # API parsing stuff
    lang = 'E'
    quality = 1080
    hard_subtitles = False
    min_date = 0  # 1970-01-01
    include_categories = ('VideoOnDemand',)
    exclude_categories = ('VODSJJMeetings',)

    # Disk space check stuff
    keep_free = 0  # bytes
    warning = True  # warn if limit is set too low

    import_dir = ''

    # Download stuff
    download = False
    download_subtitles = False
    friendly_filenames = False
    curl_path = 'curl'
    rate_limit = '1M'
    checksums = False
    overwrite_bad = False

    # Output stuff
    append = False
    clean_all_symlinks = False
    mode = ''
    safe_filenames = False
    sort = 'none'

    def __setattr__(self, key, value):
        # This will raise an error if the attribute we are trying to set doesn't already exist
        getattr(self, key)
        super().__setattr__(key, value)
