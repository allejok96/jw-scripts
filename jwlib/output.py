import html
import subprocess
from random import shuffle
from typing import List, Type

from .common import Path, Settings, msg
from .constants import *
from .parse import Category, Media, CategoryNameError


class FileParseError(Exception):
    pass


class PlaylistEntry:
    def __init__(self, name: str, source: str, duration=0):
        self.name = name
        self.source = source
        self.duration = duration


class AbstractOutputWriter:
    """Base class for generation of output

    Use add_to_queue() to add lines. Doublets will be skipped.
    Define what to do with the queue in dump_queue(). Reversal should happen there too.
    Some data members are only for file writing sub-classes, but defined here to avoid type errors.

    CLASS VARIABLES:
     - start_string: first string in file
     - end_string: last string in file
     - ext: file name extension (dot included)
    """
    # Make sure to end these with newline if non-empty
    start_string = ''
    end_string = ''
    ext = ''

    def __init__(self, s: Settings, file: Path):
        # Note: all OutputWriters accepts a file argument, but this class does not use it
        self.quiet = s.quiet
        self.reverse = s.sort == SORT_NEW

        self.queue = []
        self.history = set()

    def add_to_history(self, string: str):
        """Return False if the string has been added before"""

        if string in self.history:
            return False
        else:
            self.history.add(string)
            return True

    def add_to_queue(self, entry: PlaylistEntry):
        """Adds a line to the queue"""

        if self.add_to_history(entry.source):
            self.queue.append(self.string_format(entry))

    def string_format(self, entry: PlaylistEntry) -> str:
        """Turn a playlist entry into a string"""

        return entry.source

    def string_parse(self, string: str) -> str:
        """Extract URL from a string"""

        return string

    def dump_queue(self):
        """Should do something with the queue (reversing happens here)"""

        raise NotImplementedError


class TxtWriter(AbstractOutputWriter):
    """ Base class for writing text files

    Usage:
    1. Load existing file data (stripping start and end).
    2. Keep history of URLs so we don't include doublets.
    3. Add lines to a queue.
    4. Write out the queue to wherever (reversing happens here).
    """

    def __init__(self, s: Settings, file: Path):
        super().__init__(s, file)
        self.file = file

        # Get existing lines from file
        self.loaded_data = ''
        self.append = s.append
        if self.append:
            self.load_existing()

    def load_existing(self):
        """Reads existing file into memory, removing start and end strings"""

        try:
            with self.file.open(encoding='utf-8') as file:
                data = file.read()
                # Remove start string and end string
                if self.start_string:
                    if data.startswith(self.start_string):
                        data = data[len(self.start_string):]
                    else:
                        raise FileParseError
                if self.end_string:
                    if data.endswith(self.end_string):
                        # Just a note: list[:-0] == []
                        data = data[:-len(self.end_string)]
                    else:
                        raise FileParseError
                # Store file in memory
                self.loaded_data = data
                # Generate history from loaded data
                for line in data.splitlines():
                    self.history.add(self.string_parse(line))
        except OSError:
            pass

    def dump_queue(self):
        """Create dir and write out queue to file"""

        if not self.queue or not self.file:
            return
        if self.reverse:
            self.queue.reverse()

        if self.quiet < 1:
            if self.loaded_data:
                msg('updating: {}'.format(self.file))
            else:
                msg('creating: {}'.format(self.file))

        # Note:
        # Text append mode ('a') only works if there is no end_string
        # Seeking only works in binary mode, and that does not support universal newlines (CRLF)
        # So to make it simple we always write the file from scratch, even if append = True
        # Also: encoding is needed on Windows
        with self.file.open('w', encoding='utf-8') as file:
            file.write(self.start_string)
            # Prepend old content
            if not self.reverse and self.append:
                file.write(self.loaded_data)
            # Write out buffer
            file.writelines(line + '\n' for line in self.queue)
            # Append old content
            if self.reverse and self.append:
                file.write(self.loaded_data)
            # End string
            file.write(self.end_string)


class M3uWriter(TxtWriter):
    start_string = '#EXTM3U\n'
    ext = '.m3u'

    def string_format(self, entry):
        return '#EXTINF:{}, {}\n{}'.format(entry.duration, entry.name, entry.source)

    def string_parse(self, string):
        if not string.startswith('#'):
            return string


class HtmlWriter(TxtWriter):
    start_string = '<!DOCTYPE html>\n<html><head><meta charset="utf-8"/></head><body>\n'
    end_string = '</body></html>\n'
    ext = '.html'

    def string_format(self, entry):
        # Note: we need to quote the URL too because it can have weird
        # characters if friendly filenames are being used
        source = html.escape(entry.source, quote=True)
        return '<a href="{}">{}</a><br>'.format(source, html.escape(entry.name))

    def string_parse(self, string):
        try:
            # The thing between the first quotes is an URL
            if string.startswith('<a href="'):
                return html.unescape(string.split('"')[1])
        except IndexError:
            raise FileParseError


class StdoutWriter(AbstractOutputWriter):
    def dump_queue(self):
        """Write to stdout"""

        if self.reverse:
            self.queue.reverse()
        for line in self.queue:
            print(line)


class CommandWriter(AbstractOutputWriter):
    def __init__(self, s, file):
        super().__init__(s, file)
        self.command = s.command

    def dump_queue(self):
        """Run a program with queue entries as arguments"""

        if not self.queue:
            msg('no media')
            return
        if self.reverse:
            self.queue.reverse()

        # Avoid too long argument string (~32kB max on win)
        while self.queue:
            subprocess.check_call(self.command + self.queue[:300])
            self.queue = self.queue[300:]


def sort_media(media_list: List[Media], sort: str):
    """Sort a list of Media objects in place"""

    if sort == SORT_NONE:
        return
    elif sort == SORT_NAME:
        media_list.sort(key=lambda x: x.name)
    elif sort in (SORT_NEW, SORT_OLD):
        media_list.sort(key=lambda x: x.date)
    elif sort == SORT_RANDOM:
        shuffle(media_list)
    else:
        raise RuntimeError


def create_output(s: Settings, data: List[Category]):
    """Call correct output function"""

    if s.mode == M_FILESYSTEM:
        clean_symlinks(s)
        output_filesystem(s, data)
        return
    elif s.mode == M_RUN:
        writer = CommandWriter
    elif s.mode in (M_HTML, M_HTML_TREE):
        writer = HtmlWriter
    elif s.mode in (M_M3U, M_M3U_TREE, M_M3U_MULTI):
        writer = M3uWriter
    elif s.mode == M_STDOUT:
        writer = StdoutWriter
    elif s.mode == M_TXT:
        writer = TxtWriter
    else:
        raise RuntimeError

    if s.mode == M_M3U_MULTI:
        output_multi(s, data, writer, tree=False)
    elif s.mode in (M_HTML_TREE, M_M3U_TREE):
        output_multi(s, data, writer, tree=True)
    else:
        output_single(s, data, writer)


def output_single(s: Settings, data: List[Category], writercls: Type[AbstractOutputWriter]):
    """Create a concatenated output file"""

    all_media = [item for category in data for item in category.contents if isinstance(item, Media)]
    sort_media(all_media, s.sort)

    try:
        # Filename falls back to the name of the first category
        outputfile = s.work_dir / (s.output_filename or data[0].safe_name + writercls.ext)
        writer = writercls(s, outputfile)
    except CategoryNameError:
        msg('please specify filename for output')
        exit(1)
        raise

    for media in all_media:
        mediafile = media.find_file(s.media_dir)
        if mediafile.exists():
            source = mediafile.relative_to(outputfile.parent)
        else:
            source = media.url
        writer.add_to_queue(PlaylistEntry(media.name, str(source), media.duration))

    writer.dump_queue()


def output_multi(s: Settings, data: List[Category], writercls: Type[AbstractOutputWriter], tree=True):
    """Create a tree of output files

    :keyword writercls: a PlaylistWriter class
    :keyword tree: create an hierarchy vs everything at top level
    """
    for category in data:
        if tree and category.home:
            # Root of tree: file is outside subdir, with nice name
            # Note: CategoryNameError cannot occur on home categories
            outputfile = s.work_dir / (category.safe_name + writercls.ext)
        elif tree:
            # Sub-categories in tree: file is inside subdir, with ugly name
            outputfile = s.index_dir / (category.key + writercls.ext)
        else:
            # "Flat" mode: file is outside subdir, has both ugly and nice name
            try:
                outputfile = s.work_dir / (category.key + ' - ' + category.safe_name + writercls.ext)
            except CategoryNameError:
                # Try to guess the file name if we only have the key
                pattern = category.key + ' - *' + writercls.ext
                matches = list(s.work_dir.glob(pattern))  # need list to get len
                if len(matches) == 1:
                    outputfile = matches[0]
                else:
                    if s.quiet < 2:
                        msg('failed to find: ' + pattern)
                    continue

        # Open the output file
        try:
            writer = writercls(s, outputfile)
        except FileParseError:
            # File cannot be appended to
            if s.quiet < 2:
                msg('badly formatted file: ' + outputfile)
            continue

        # All categories go on top of the queue
        for item in category.contents:
            if isinstance(item, Category):
                # Only link to categories if we are creating a tree structure
                if tree:
                    source = (s.index_dir / (item.key + writer.ext)).relative_to(outputfile.parent)
                    writer.add_to_queue(PlaylistEntry(item.name.upper(), str(source)))

        media_items = [m for m in category.contents if isinstance(m, Media)]
        sort_media(media_items, s.sort)

        for media in media_items:
            mediafile = media.find_file(s.media_dir)
            if mediafile.exists():
                source = mediafile.relative_to(outputfile.parent)
            else:
                source = media.url
            writer.add_to_queue(PlaylistEntry(media.name, str(source), media.duration))

        writer.dump_queue()


def output_filesystem(s: Settings, data: List[Category]):
    """Creates a directory structure with symlinks to videos"""

    for category in data:

        # Create the directory
        cat_dir = s.index_dir / category.key
        if s.quiet < 1:
            msg('preparing: {}'.format(cat_dir))
        cat_dir.mkdir(exist_ok=True)

        # Index/starting/home categories: create link outside subdir
        if category.home:
            # Note: CategoryNameError cannot occur on home categories
            home_link = s.work_dir / category.safe_name
            if s.quiet < 1:
                msg('linking: {} -> {}'.format(home_link, cat_dir))
            home_link.symlink_to(cat_dir)

        for item in category.contents:

            if isinstance(item, Category):
                link_dest = s.index_dir / item.key
                link_dest.mkdir(exist_ok=True)
                # Note: CategoryNameError cannot occur on categories inside other categories contents
                link_file = cat_dir / item.safe_name

            else:
                link_dest = item.find_file(s.media_dir)
                if not link_dest.exists():
                    continue
                link_file = cat_dir / item.friendly_filename

                subtitle = item.find_subtitle(s.media_dir)
                if subtitle.exists():
                    (cat_dir / item.friendly_subtitle).symlink_to(subtitle)

            link_file.symlink_to(link_dest)


def clean_symlinks(s: Settings):
    """Clean out broken (or all) symlinks from work dir"""

    for link in s.index_dir.glob('*/*'):
        if link.is_symlink():
            # If link is neither dir nor file it's probably broken
            if s.clean_all_symlinks or (not link.is_dir() and not link.is_file()):
                if s.quiet < 1:
                    msg('removing link: ' + link.name)
                link.unlink()
