import html
import os
import subprocess
from random import shuffle
from typing import List, Type

from .parse import Category, Media
from .common import Settings, msg

pj = os.path.join


class PlaylistEntry:
    def __init__(self, name: str, source: str, duration=0):
        self.name = name
        self.source = source
        self.duration = duration


class BaseOutputWriter:
    """Base class for creation of output files

    Usage:
    1. Load existing file data (stripping start and end).
    2. Keep history of URLs so we don't include doublets.
    3. Add lines to a queue.
    4. Write out the queue to wherever (reversing happens here).
    """
    start_string = ''
    end_string = ''
    ext = ''

    def __init__(self, s: Settings, filename: str):
        """
        :param filename: File name (can also be a relative path)
        """
        self.quiet = s.quiet
        self.append = s.append  # append instead of overwriting
        self.reverse = s.sort == 'newest'  # prepend instead of append
        self.file = pj(s.work_dir, filename)

        self.queue = []
        self.history = set()

        # Get existing lines from file
        self.loaded_data = ''
        if self.append or self.reverse:
            self.load_existing()

    def load_existing(self):
        """Reads existing file into memory, removing start and end strings"""

        try:
            with open(self.file, 'r', encoding='utf-8') as file:
                data = file.read()
                if data.startswith(self.start_string):
                    data = data[len(self.start_string):]
                if data.endswith(self.end_string):
                    data = data[:-len(self.end_string)]
                self.loaded_data = data
                # Generate history from loaded data
                for line in data.splitlines():
                    self.history.add(self.string_parse(line))
        except OSError:
            pass

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

    def dump_queue(self):
        """Create dir and write out queue to file"""

        if not self.queue:
            return
        if self.reverse:
            self.queue.reverse()

        d = os.path.dirname(self.file)
        os.makedirs(d, exist_ok=True)

        # All IO is done in binary mode, since text mode is not seekable
        try:
            if self.reverse or not self.append or not self.loaded_data:
                raise OSError  # file must be overwritten

            file = open(self.file, 'r+b')
            if self.quiet < 1:
                msg('extending: {}'.format(self.file))

            try:
                # Truncate right before end string
                # Seeking to invalid positions raises OSError
                file.seek(-len(self.end_string.encode('utf-8')), 2)
                if file.peek().decode('utf-8') == self.end_string:
                    file.truncate()
                else:
                    raise OSError
            except OSError:
                raise RuntimeError(self.file + ': refusing to append to file which does not match output format')

        except OSError:
            # Overwrite with start string
            file = open(self.file, 'wb')
            if self.quiet < 1:
                msg('writing: {}'.format(self.file))
            file.write(self.start_string.encode('utf-8'))

        with file:
            # Write out buffer
            for string in self.queue:
                file.write((string + '\n').encode('utf-8'))
            # Append old file contents
            if self.reverse and self.append:
                file.write(self.loaded_data.encode('utf-8'))
            # End string
            file.write(self.end_string.encode('utf-8'))

    def string_format(self, entry: PlaylistEntry) -> str:
        """Turn a playlist entry into a string"""
        return entry.source

    def string_parse(self, string: str) -> str:
        """Extract URL from a string"""
        return string


class TxtWriter(BaseOutputWriter):
    pass


class M3uWriter(BaseOutputWriter):
    start_string = '#EXTM3U\n'
    ext = '.m3u'

    def string_format(self, entry):
        return '#EXTINF:{}, {}\n{}'.format(entry.duration, entry.name, entry.source)

    def string_parse(self, string):
        if not string.startswith('#'):
            return string


class HtmlWriter(BaseOutputWriter):
    start_string = '<!DOCTYPE html>\n<html><head><meta charset="utf-8"/></head><body>\n'
    end_string = '</body></html>'
    ext = '.html'

    def string_format(self, entry):
        # Note: we need to quote the URL too because it can have weird
        # characters if friendly filenames are being used
        source = html.escape(entry.source, quote=True)
        return '<a href="{}">{}</a><br>'.format(source, html.escape(entry.name))

    def string_parse(self, string):
        # The thing between the first quotes is an URL
        html.unescape(string.split('"')[1])


class StdoutWriter(BaseOutputWriter):
    def load_existing(self):
        """Don't read files"""
        pass

    def dump_queue(self):
        """Write to stdout"""

        if self.reverse:
            self.queue.reverse()
        for line in self.queue:
            print(line)


class CommandWriter(BaseOutputWriter):
    def __init__(self, s, filename):
        super().__init__(s, filename)
        self.command = s.command

    def load_existing(self):
        pass

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


def sort_media(media_list: list, sort: str):
    """Sort a list of Media objects in place"""

    if sort == 'none':
        return
    elif sort == 'name':
        media_list.sort(key=lambda x: x.name)
    elif sort in ('newest', 'oldest'):
        media_list.sort(key=lambda x: x.date)
    elif sort == 'random':
        shuffle(media_list)
    else:
        raise RuntimeError


def create_output(s: Settings, data: List[Category]):
    """Call correct output function"""

    if s.mode == 'filesystem':
        clean_symlinks(s)
        output_filesystem(s, data)
        return
    elif s.mode == 'run':
        writer = CommandWriter
    elif s.mode.startswith('html'):
        writer = HtmlWriter
    elif s.mode.startswith('m3u'):
        writer = M3uWriter
    elif s.mode.startswith('stdout'):
        writer = StdoutWriter
    elif s.mode.startswith('txt'):
        writer = TxtWriter
    else:
        # Note: ArgumentParser will make sure we never end up here
        raise RuntimeError('invalid mode')

    if s.mode.endswith('multi'):
        output_multi(s, data, writer, tree=False)
    elif s.mode.endswith('tree'):
        output_multi(s, data, writer, tree=True)
    else:
        output_single(s, data, writer)


def output_single(s: Settings, data: List[Category], writercls: Type[BaseOutputWriter]):
    """Create a concatenated output file"""

    all_media = [item for category in data for item in category.contents if isinstance(item, Media)]
    sort_media(all_media, s.sort)

    # Filename falls back to the name of the first category
    filename = s.output_filename or (data[0].safe_name + writercls.ext)
    writer = writercls(s, filename)

    for media in all_media:
        if media.exists_in(pj(s.work_dir, s.sub_dir)):
            source = pj('.', s.sub_dir, media.filename)
        else:
            source = media.url
        writer.add_to_queue(PlaylistEntry(media.name, source, media.duration))

    writer.dump_queue()


def output_multi(s: Settings, data: List[Category], writercls: Type[BaseOutputWriter], tree=True):
    """Create a tree of output files

    :keyword writercls: a PlaylistWriter class
    :keyword tree: create an hierarchy vs everything at top level
    """
    wd = s.work_dir
    sd = s.sub_dir

    for category in data:
        if tree and category.home:
            # For the root of a tree:
            # Output file is outside subdir, with nice name
            # Links point inside the subdir
            source_prepend_dir = sd
            writer = writercls(s, category.safe_name + writercls.ext)
        elif tree:
            # For sub-categories in a tree:
            # Output file is inside subdir, with ugly name
            # No need to prepend links with the subdir (since we are inside it)
            source_prepend_dir = ''
            writer = writercls(s, pj(sd, category.key) + writercls.ext)
        else:
            # "Flat" mode, not a tree:
            # Output file is outside subdir, has both ugly and nice name
            # Links point inside subdir
            source_prepend_dir = sd
            writer = writercls(s, category.key + ' - ' + category.safe_name + writercls.ext)

        media_entries = []
        for item in category.contents:
            if isinstance(item, Category):
                # Only link to categories if we are creating a tree structure
                if tree:
                    source = pj('.', source_prepend_dir, item.key + writer.ext)
                    # Categories go on top of the queue
                    writer.add_to_queue(PlaylistEntry(item.name.upper(), source))
            else:
                if item.exists_in(pj(wd, sd)):
                    source = pj('.', source_prepend_dir, item.filename)
                else:
                    source = item.url
                # Hold on to media links so we can sort them later
                media_entries.append(PlaylistEntry(item.name, source, item.duration))

        sort_media(media_entries, s.sort)
        for entry in media_entries:
            writer.add_to_queue(entry)

        writer.dump_queue()


def output_filesystem(s: Settings, data: List[Category]):
    """Creates a directory structure with symlinks to videos"""

    wd = s.work_dir
    sd = s.sub_dir

    if s.quiet < 1:
        msg('creating directory structure')

    for category in data:

        # Create the directory
        output_dir = pj(wd, sd, category.key)
        os.makedirs(output_dir, exist_ok=True)

        # Index/starting/home categories: create link outside subdir
        if category.home:
            link = pj(wd, category.safe_name)
            if s.safe_filenames:
                source = pj(wd, sd, category.key)
            else:
                source = pj(sd, category.key)
            try:
                os.symlink(source, link)
            except FileExistsError:
                pass
            except OSError:
                print('Could not create symlink. If you are on Windows 10, try enabling developer mode.')
                raise

        for item in category.contents:

            if isinstance(item, Category):
                d = pj(wd, sd, item.key)
                os.makedirs(d, exist_ok=True)
                if s.safe_filenames:
                    source = d
                else:
                    source = pj('..', item.key)
                link = pj(output_dir, item.safe_name)

            else:
                if not item.exists_in(pj(wd, sd)):
                    continue

                if s.safe_filenames:
                    source = pj(wd, sd, item.filename)
                else:
                    source = pj('..', item.filename)
                link = pj(output_dir, item.friendly_filename)

            try:
                os.symlink(source, link)
            except FileExistsError:
                pass
            except OSError:
                print('Could not create symlink. If you are on Windows 10, try enabling developer mode.')


def clean_symlinks(s: Settings):
    """Clean out broken (or all) symlinks from work dir"""

    path = pj(s.work_dir, s.sub_dir)

    if not os.path.isdir(path):
        return

    for subdir in os.listdir(path):
        subdir = pj(path, subdir)
        if not os.path.isdir(subdir):
            continue

        for file in os.listdir(subdir):
            file = pj(subdir, file)
            if not os.path.islink(file):
                continue

            source = pj(subdir, os.readlink(file))

            if s.clean_all_symlinks or not os.path.exists(source):
                if s.quiet < 1:
                    msg('removing link: ' + os.path.basename(file))
                os.remove(file)
