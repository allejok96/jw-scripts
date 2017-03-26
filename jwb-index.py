#!/usr/bin/env python3

class OutputHTML:
    pass

class OutputM3U:
    pass

class OutputM3UCompat:
    pass

class OutputStdout:
    def save_media(self, title, url):
        print("+ " + title + "(" + url + ")")

    def save_sub(self, key, name):
        print("> " + name + "(" + key + ")")
        parse_vod(key)

class History:
    """A place to save history of keys"""

    def __init__(self):
        self.__history=[]

    def add(self, string):
        self.__history.append(string)

    def read(self):
        return self.__history

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
                    parse_vod(subkey)

        if "media" in list["category"]:
            for media in list["category"]["media"]:
                video = get_best_video(media["files"])
                output.save_media(media["title"], video["progressiveDownloadURL"])

def get_best_video(files):
    videos = sorted([x for x in files if x['frameHeight'] <= option.quality],
                    reverse=True,
                    key=lambda v: v['frameWidth'])
    videos = sorted(videos, reverse=True, key=lambda v: v['subtitled'] == option.subtitle)
    return videos[0]

    """
    file["frameWidth"]
    file["subtitled"]
    file["filesize"]
    file["checksum"]
    file["progressiveDownloadURL"]
    file["modifiedDatetime"]
    """

import urllib.request
import json

option = Options()
option.subtitle = True
option.lang = "Z"
option.quality = 360
option.key = "VODChildren"
option.mode = "stdout"

history = History()
history.add("BJF")

if option.mode == "stdout":
    output = OutputStdout()

parse_vod(option.key)
