from sys import stderr
import os
from typing import List

from .parse import Category, Media
from .arguments import JwbSettings

pj = os.path.join


def create_output(s: JwbSettings, data: List[Category], stdout_uniq=False):
    """Settings for output modes

    :param s: Global settings
    :param data: list with Media and Category objects
    :param stdout_uniq: passed to output_stdout
    """

    if s.mode == 'stdout':
        output_stdout(s, data, uniq=stdout_uniq)
    elif s.mode == 'm3u':
        output_m3u(s, data)
    elif s.mode == 'filesystem':
        clean_symlinks(s)
        output_filesystem(s, data)
    elif s.mode == 'm3ucompat':
        output_m3u(s, data, flat=True)
    elif s.mode == 'html':
        output_m3u(s, data, writer=_write_to_html, file_ending='.html')
    else:
        raise RuntimeError('invalid mode')


def output_stdout(s: JwbSettings, data: List[Category], uniq=False):
    """Output URLs or filenames to stdout.

    :param uniq: If True all output is unique, but unordered
    """
    out = []
    for category in data:
        for item in category.contents:
            if isinstance(item, Media):
                if item.file:
                    out.append(os.path.relpath(item.file, s.work_dir))
                else:
                    out.append(item.url)
    if uniq:
        out = set(out)

    print(*out, sep='\n')


def output_m3u(s: JwbSettings, data: List[Category], writer=None, flat=False, file_ending='.m3u'):
    """Create a M3U playlist tree.

    :param writer: Function to write to files
    :param flat: If all playlist will be saved outside of subdir
    :param file_ending: Well, duh
    """
    wd = s.work_dir
    sd = s.sub_dir

    def fmt(x):
        return format_filename(x, safe=s.safe_filenames)

    if not writer:
        writer = _write_to_m3u

    for category in data:
        if flat:
            # Flat mode, all files in working dir
            output_file = pj(wd, category.key + ' - ' + fmt(category.name) + file_ending)
            source_prepend_dir = sd
        elif category.home:
            # For home/index/starting categories
            # The current file gets saved outside the subdir
            # Links point inside the subdir
            source_prepend_dir = sd
            output_file = pj(wd, fmt(category.name) + file_ending)
        else:
            # For all other categories
            # Things get saved inside the subdir
            # No need to prepend links with the subdir itself
            source_prepend_dir = ''
            output_file = pj(wd, sd, category.key + file_ending)

        # Since we want to start on a clean file, remove the old one
        try:
            os.remove(output_file)
        except FileNotFoundError:
            pass

        for item in category.contents:
            if isinstance(item, Category):
                if flat:
                    continue
                name = item.name.upper()
                source = pj('.', source_prepend_dir, item.key + file_ending)
            else:
                name = item.name
                if item.file:
                    source = pj('.', source_prepend_dir, os.path.basename(item.file))
                else:
                    source = item.url
            writer(source, name, output_file)


def output_filesystem(s: JwbSettings, data: List[Category]):
    """Creates a directory structure with symlinks to videos"""
    wd = s.work_dir
    sd = s.sub_dir

    def fmt(x):
        return format_filename(x, safe=s.safe_filenames)

    for category in data:

        # Create the directory
        output_dir = pj(wd, sd, category.key)
        os.makedirs(output_dir, exist_ok=True)

        # Index/starting/home categories: create link outside subdir
        if category.home:
            link = pj(wd, fmt(category.name))
            # Note: the source will be relative
            source = pj(sd, category.key)
            try:
                os.symlink(source, link)
            except FileExistsError:
                pass

        for item in category.contents:

            if isinstance(item, Category):
                d = pj(wd, sd, item.key)
                os.makedirs(d, exist_ok=True)
                source = pj('..', item.key)

                if s.include_keyname:
                    link = pj(output_dir, item.key + ' - ' + fmt(item.name))
                else:
                    link = pj(output_dir, fmt(item.name))

            else:
                if not item.file:
                    continue

                source = pj('..', os.path.basename(item.file))
                ext = os.path.splitext(item.file)[1]
                link = pj(output_dir, fmt(item.name + ext))

            try:
                os.symlink(source, link)
            except FileExistsError:
                pass


def format_filename(string, safe=False):
    """Remove unsafe characters from file names"""

    if safe:
        # NTFS/FAT forbidden characters
        string = string.replace('"', "'").replace(':', '.')
        forbidden = '<>:"|?*/\0'
    else:
        # Unix forbidden characters
        forbidden = '/\0'

    return ''.join(x for x in string if x not in forbidden)


def clean_symlinks(s: JwbSettings):
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
                if s.quiet < 2:
                    print('removing link: ' + os.path.basename(file), file=stderr)
                os.remove(file)


def _truncate_file(file, string=''):
    """Create a file and the parent directories."""
    d = os.path.dirname(file)
    os.makedirs(d, exist_ok=True)

    # Don't truncate non-empty files
    try:
        if os.stat(file).st_size != 0:
            return
    except FileNotFoundError:
        pass

    with open(file, 'w', encoding='utf-8') as f:
        f.write(string)


def _write_to_m3u(source, name, file):
    """Write entry to a M3U playlist file."""
    _truncate_file(file, string='#EXTM3U\n')
    with open(file, 'a', encoding='utf-8') as f:
        f.write('#EXTINF:0,' + name + '\n' + source + '\n')


def _write_to_html(source, name, file):
    """Write a HTML file with a hyperlink to a media file."""
    _truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>')
    with open(file, 'a', encoding='utf-8') as f:
        f.write('\n<a href="{0}">{1}</a><br>'.format(source, name))
