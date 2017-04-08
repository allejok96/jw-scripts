#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import os

class Storage:
    """A place to store stuff"""
    
    def __init__(self):
        self.__storage = []

    def add(self, value):
        if no value in self.__storage:
            self.__storage.append(value)

    def read(self):
        return self.__storage
    

class Output:
    """Methods to create and handle files"""
    
    def truncate_file(self, file, string=''):
        if not os.path.exists(file):
            dirname = os.path.dirname(file)
            if not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            with f as open(file, 'w'):
                file.write(string)

    def set_file(self, key):
        return None

    def get_file(self):
        return None

    
class OutputHTML(Output):
    """Create a HTML file"""
    pass


class OutputM3U(Output):
    """Create a M3U playlist tree"""

    def set_file(self, key):
        self.__file = os.path.join(option.datadir, key, '.m3u')

    def get_file(self):
        return self.__file
        
    def write_to_m3u(self, dest, name, file=None):
        if file == None:
            file = self.__file
        
        self.truncate_file(file, string='#EXTM3U\n')
        with f as open(file, 'a'):
            f.write('#EXTINF:0,' + name + '\n' + dest)


class OutputM3UCompat(OutputM3U):
    """Create multiple M3U playlists"""

    def save_media(self, url, name, **keywords):
        self.write_to_m3u(name=name, dest=url)

    def save_sub(self, key, name, **keywords):
        self.write_to_m3u(dest=key + ".m3u", name=name)


class OutputStdout(Output):
    """Simply output to stdout"""
    
    def save_media(self, url, name, **keywords):
        print("+ " + name + "(" + url + ")")

    def save_sub(self, key, name, **keywords):
        print("> " + name + "(" + key + ")")

        
class Options:
    """Put global options in here"""

    def __init__(self):
        self.lang = "E"
        self.subtitle = False
        self.quality = 720
        self.key = "VideoOnDemand"

        
def parse_vod(key):
    """Download JSON and do stuff"""

    history.add(key)

    url = "https://mediator.jw.org/v1/categories/{0}/{1}?detailed=1".format(option.lang, key)
    with urllib.request.urlopen(url) as response:
        list = json.load(response)

        if "status" in list and list["status"] == "404":
            print("No such category")
            exit()

        key = list["category"]["key"]

        if "subcategories" in list["category"]:
            for subcategory in list["category"]["subcategories"]:
                subkey = subcategory["key"]
                if not subkey in history.read():
                    output.save_sub(subkey, subcategory["name"])
                    queue.add(subkey)

        if "media" in list["category"]:
            for media in list["category"]["media"]:
                video = get_best_video(media["files"])
                output.save_media(
                    url = video["progressiveDownloadURL"],
                    name = media["title"],
                    size = video["filesize"],
                    time = video["modifiedDatetime"],
                    checksum = video["checksum"])

                
def get_best_video(files):
    videos = sorted([x for x in files if x['frameHeight'] <= option.quality],
                    reverse=True,
                    key=lambda v: v['frameWidth'])
    videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == option.subtitle)
    return videos[0]


option = Options()
option.datadir = "/home/alex"
option.subtitle = True
option.lang = "Z"
option.quality = 360
option.key = "VODChildren"
option.mode = "stdout"

if option.mode == "stdout":
    output = OutputStdout()
elif option.mode == "m3ucompat":
    output = OutputM3UCompat()

history = Storage()
queue = Storage()
queue.add(option.key)

for key in queue.read():
    output.set_file(key)
    parse_vod(key)
