#!/usr/bin/env python3
import os
import shutil

from jwlib.common import Settings, msg
from jwlib.download import disk_cleanup


class File:
    def __init__(self, name: str, directory: str):
        self.name = name
        self.path = os.path.join(directory, name)
        try:
            stat = os.stat(self.path)
            self.size = stat.st_size
            self.date = stat.st_mtime
        except FileNotFoundError:
            self.size = None
            self.date = None

def copy_files(s: Settings):
    dest_dir = os.path.join(s.work_dir, s.sub_dir)

    # Create a list of all mp4 files to be copied
    source_files = []
    for name in os.listdir(s.import_dir):
        if not name.lower().endswith('.mp4'):
            continue
        source_file = File(s.import_dir, name)
        dest_file = File(dest_dir, name)
        # Just a simple size check, no checksum etc
        if source_file.size != dest_file.size:
            source_files.append(source_file)

    # Newest file first
    source_files.sort(key=lambda x: x.date, reverse=True)

    os.makedirs(dest_dir, exist_ok=True)

    total = len(source_files)
    for source_file in source_files:
        if s.keep_free > 0:
            disk_cleanup(s, directory=dest_dir, reference_media=source_file)

        if s.quiet < 1:
            i = source_files.index(source_file)
            msg('copying [{}/{}]: {}'.format(i + 1, total, source_file.name))

        shutil.copy2(source_file.path, os.path.join(dest_dir, source_file.name))
