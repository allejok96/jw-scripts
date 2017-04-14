#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import os
#import shutil

def download_media(url, dir=None):
    """Download a file to a directory"""

    if dir is None:
        dir = option.datadir

    os.makedirs(dir, exist_ok=True)

    u = urllib.parse.urlparse(url)
    file = os.path.basename(u.path)
    file = os.path.join(dir, file)

    print("Laddar hem " + file)
    urllib.request.urlretrieve(url, file)


def truncate_file(file, string='', overwrite=False):
    """Create a file and its parent directories"""

    d = os.path.dirname(file)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    if overwrite:
        pass
    elif os.path.exists(file) and os.stat(file).st_size == 0:
        # Truncate empty files
        pass
    else:
        return

    with open(file, 'w') as f:
        f.write(string)

class Storage:
    """A place to store stuff"""
    
    def __init__(self):
        self.__storage = []

    def add(self, value):
        if value not in self.__storage:
            self.__storage.append(value)

    def read(self):
        return self.__storage
    

class Output:
    """Methods to create and handle files"""

    def save_media(self, url, *args, **keywords):
        if option.download:
            download_media(url)

    def set_key(self, key, *args, **keywords):
        pass

    def save_sub(self, *args, **keywords):
        pass


class OutputM3U(Output):
    """Create a M3U playlist tree"""

    def __init__(self):
        self.output_file = None
        self.file_ending = ".m3u"
        
    def save_media(self, url, name, *args, **keywords):
        # Write media to a playlist

        if option.download == True:
            dir = os.path.join(option.datadir, option.subdir)
            download_media(url, dir=dir)

        self.write_to_file(url, name)

    def save_sub(self, key, name, *args, **keywords):
        # Write a link to another playlist to the current playlist

        name = name.upper()

        dest = os.path.join (".", self._inserted_subdir, key + self.file_ending)
        self.write_to_file(dest, name)

    def set_key(self, key, *args, **keywords):
        # Switch to a new file

        if self.output_file is None:
            # The first time this method runs:
            # The current (first) file gets saved outside the subdir,
            # all other data (later files) gets saved inside the subdir,
            # so all paths in the current file must have the subdir prepended.
            self._inserted_subdir = option.subdir
            self.output_file = os.path.join(option.datadir, key + self.file_ending)
        else:
            # The second time and forth:
            # Don't prepend the subdir no more
            # Save data directly in the subdir
            self._inserted_subdir = ''
            self.output_file = os.path.join(option.datadir, option.subdir, key + self.file_ending)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self.output_file):
            os.remove(self.output_file)

    def write_to_m3u(self, dest, name, file=None):
        # Write something to a M3U file

        if file == None: file = self.output_file
        
        truncate_file(file, string='#EXTM3U\n')
        with open(file, 'a') as f:
            f.write('#EXTINF:0,' + name + '\n' + dest + '\n')

    write_to_file = write_to_m3u


class OutputM3UCompat(OutputM3U):
    """Create multiple M3U playlists"""

    def __init__(self):
        super().__init__()
        self.file_ending = ".m3u"

    def set_key(self, key, name, *args, **keywords):
        # Switch to a new file

        filename = key + " - " + name + self.file_ending
        self.output_file = os.path.join(option.datadir, filename)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self.output_file):
            os.remove(self.output_file)

    def save_sub(self, *args, **keywords):
        # Don't link to other playlists to not crash media players
        # hence the "compat" part of M3UCompat 
        pass


class OutputHTML(OutputM3U):
    """Create a HTML file"""

    def __init__(self):
        super().__init__()
        self.file_ending = ".html"

    def write_to_html(self, dest, name, file=None):
        # Write a link to a HTML file

        if file is None:
            file = self.output_file

        truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>\n')

        with open(file, 'a') as f:
            f.write('<a href="{0}">{1}</a><br>'.format(dest, name))

    write_to_file = write_to_html


class OutputStdout(Output):
    """Simply output to stdout"""
    
    def save_media(self, url, *args, **keywords):
        if option.download:
            download_media(url, dir=option.datadir)

        print(url)


class OutputFilesystem(Output):
    """Create a directory structure"""

    def __init__(self):
        self.output_dir = None

    def set_key(self, key, name, *args, **keywords):

        self.output_dir = os.path.join(option.datadir, option.subdir, key)

        # First time: create a symlink outside the subdir
        if self.output_dir is None:
            l = os.path.join(option.datadir, name)
            os.symlink(self.output_dir, l)

    def save_sub(self, key, name, *args, **keywords):
        """Create a symlink to a directory"""

        d = os.path.join(option.datadir, key)
        l = os.path.join(self.output_dir, name)

        if not os.path.exists(d):
            os.makedirs(d)

        os.symlink(d, l)

    def save_media(self, url, name, *args, **keywords):
        """Create a symlink to some media"""

        if option.download == True:
            dir = os.path.join(option.datadir, option.subdir)
            download_media(url, dir=dir)

        f = urllib.parse.urlparse(url)
        f = os.basename(f.path)
        f = os.path.join(option.datadir, f)
        ext = os.path.splitext(f)["ext"]
        l = os.path.join(self.output_dir, name + ext)
        os.symlink(f, l)


class Options:
    """Put global options in here"""

    def __init__(self):
        self.lang = "E"
        self.subtitle = False
        self.quality = 720
        self.key = "VideoOnDemand"
        self.mode = "stdout"
        self.download = False
        self.subdir = "jwb-" + self.lang

    @property
    def lang(self):
        return self.__lang

    @lang.setter
    def lang(self, code):
        self.__lang = code
        self.subdir = "jwb-" + code

        
def parse_vod(key):
    """Download JSON and do stuff"""

    history.add(key)

    url = "https://mediator.jw.org/v1/categories/{0}/{1}?detailed=1".format(option.lang, key)
    with urllib.request.urlopen(url) as response:
        response = json.load(response)

        if "status" in response and response["status"] == "404":
            print("No such category")
            exit()

        output.set_key(response["category"]["key"], response["category"]["name"])

        if "subcategories" in response["category"]:
            for subcategory in response["category"]["subcategories"]:
                subkey = subcategory["key"]
                if subkey not in history.read():
                    output.save_sub(subkey, subcategory["name"])
                    queue.add(subkey)

        if "media" in response["category"]:
            for media in response["category"]["media"]:
                video = get_best_video(media["files"])
                output.save_media(
                    url=video["progressiveDownloadURL"],
                    name=media["title"],
                    size=video["filesize"],
                    time=video["modifiedDatetime"],
                    checksum=video["checksum"])

                
def get_best_video(files):
    videos = sorted([x for x in files if x['frameHeight'] <= option.quality],
                    reverse=True,
                    key=lambda v: v['frameWidth'])
    videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == option.subtitle)
    return videos[0]


option = Options()
option.datadir = "/home/alex/mapp"
option.subtitle = True
option.quality = 240
option.key = "VODChildren"
option.mode = "filesystem"
option.download = False
option.lang = "Z"

output = OutputStdout()
if option.mode == "stdout":
    output = OutputStdout()
elif option.mode == "m3ucompat":
    output = OutputM3UCompat()
elif option.mode == "m3u":
    output = OutputM3U()
elif option.mode == "filesystem":
    output = OutputFilesystem()
elif option.mode == "html":
    output = OutputHTML()

history = Storage()
queue = Storage()
queue.add(option.key)

for key in queue.read():
    parse_vod(key)
