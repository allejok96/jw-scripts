import os
from random import shuffle
from typing import List, Type

from .parse import Category, Media
from .arguments import Settings, msg

pj = os.path.join


class PlaylistWriter:
    ext = ''
    start_string = ''
    end_string = ''

    def __init__(self, file: str, append=False):
        self.append = append
        self.io = None
        self.unique_lines = set()

        if not file.endswith(self.ext):
            file = file + self.ext
        self.file = file

    def __del__(self):
        if self.io and not self.io.closed:
            self.io.write(self.end_string)
            self.io.close()

    def write(self, string):
        """Create dir/file, write header and append string"""

        if not self.io or self.io.closed:
            d = os.path.dirname(self.file)
            os.makedirs(d, exist_ok=True)

            if self.append and os.path.exists(self.file) and os.stat(self.file).st_size != 0:
                self.io = open(self.file, 'a', encoding='utf-8')
            else:
                self.io = open(self.file, 'w', encoding='utf-8')
                self.io.write(self.start_string)

        self.io.write(string)

    def unique(self, string):
        """Run once to check unique status"""

        # Get existing lines from file
        if not self.unique_lines:
            try:
                with open(self.file, 'r') as file:
                    for line in file:
                        self.unique_lines.add(line.rstrip('\n'))
            except OSError:
                pass

        if string in self.unique_lines:
            return False
        else:
            self.unique_lines.add(string)
            return True

    def add(self, name, source, length=0):
        raise NotImplementedError


class TxtWriter(PlaylistWriter):
    def add(self, name, source, length=0):
        if self.unique(source):
            self.write(source + '\n')


class M3uWriter(PlaylistWriter):
    start_string = '#EXTM3U\n'
    ext = '.m3u'

    def add(self, name, source, length=0):
        if self.unique(source):
            self.write('#EXTINF:{}, {}\n{}\n'.format(length, name, source))


class HtmlWriter(PlaylistWriter):
    start_string = '<!DOCTYPE html>\n<html><head><meta charset="utf-8" /></head><body>'
    end_string = '\n</body></html>'
    ext = '.html'

    def add(self, name, source, length=0):
        self.write('\n<a href="{0}">{1}</a><br>'.format(source, name))


class StdoutWriter(PlaylistWriter):
    """Hack that only writes to stdout"""

    def __init__(self, file, append=False):
        super().__init__(file, append)
        self.file = ''

    def add(self, name, source, length=0):
        if self.unique(source):
            print(source)


def create_output(s: Settings, data: List[Category]):
    """Settings for output modes"""

    if s.mode == 'filesystem':
        clean_symlinks(s)
        output_filesystem(s, data)
    elif s.mode == 'html':
        output_multi(s, data, HtmlWriter)
    elif s.mode == 'm3u_flat':
        output_multi(s, data, M3uWriter, flat=True)
    elif s.mode == 'm3u_single':
        output_single(s, data, M3uWriter)
    elif s.mode == 'm3u_tree':
        output_multi(s, data, M3uWriter)
    elif s.mode == 'stdout':
        output_single(s, data, StdoutWriter)
    elif s.mode == 'txt':
        output_single(s, data, TxtWriter)
    else:
        raise RuntimeError('invalid mode')


def output_single(s: Settings, data: List[Category], writercls: Type[PlaylistWriter]):
    """Create a concatenated output file"""

    all_media = [item for category in data for item in category.contents if isinstance(item, Media)]

    if s.sort == 'date':
        all_media.sort(key=lambda x: x.date)
    elif s.sort == 'name':
        all_media.sort(key=lambda x: x.name)
    elif s.sort == 'random':
        shuffle(all_media)

    writer = writercls(pj(s.work_dir, s.output_filename), append=s.append)

    if all_media and writer.file and s.quiet < 1:
        msg('writing: {}'.format(writer.file))

    for media in all_media:
        if media.exists_in(pj(s.work_dir, s.sub_dir)):
            source = pj('.', s.sub_dir, media.filename)
        else:
            source = media.url
        writer.add(media.name, source, media.duration)


def output_multi(s: Settings, data: List[Category], writercls: Type[PlaylistWriter], flat=False):
    """Create a tree of output files

    :keyword writercls: a PlaylistWriter class
    :keyword flat: all categories are saved at top level
    """
    wd = s.work_dir
    sd = s.sub_dir

    for category in data:
        if flat:
            # Flat mode, all files in working dir
            source_prepend_dir = sd
            writer = writercls(pj(wd, category.key + ' - ' + category.safe_name))
        elif category.home:
            # For home/index/starting categories
            # The current file gets saved outside the subdir
            # Links point inside the subdir
            source_prepend_dir = sd
            writer = writercls(pj(wd, category.safe_name))
        else:
            # For all other categories
            # Things get saved inside the subdir
            # No need to prepend links with the subdir itself
            source_prepend_dir = ''
            writer = writercls(pj(wd, sd, category.key))

        if category.contents and s.quiet < 1:
            msg('writing: {}'.format(writer.file))

        for item in category.contents:
            if isinstance(item, Category):
                if flat:
                    # "flat" playlists does not link to other playlists
                    continue
                name = item.name.upper()
                source = pj('.', source_prepend_dir, item.key + writer.ext)
                duration = 0
            else:
                name = item.name
                if item.exists_in(pj(wd, sd)):
                    source = pj('.', source_prepend_dir, item.filename)
                else:
                    source = item.url
                duration = item.duration

            writer.add(name, source, duration)


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
