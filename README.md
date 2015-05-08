# jw-kodiator

This is a bash script I wrote so I could watch JW Broadcasting (tv.jw.org) on my Raspberry pi running Kodi (XBMC). It requires bash, egrep, curl and GNU sed.

**There is an [unofficial JW Broadcasting add-on] (https://github.com/ca0abinary/plugin.video.jwtv-unofficial) for Kodi that does this better.**
I was unaware of that add-on when I made this script.

The script downloads and parses files from mediator.jw.org, which I guess are ment to be used by Roku. Then it creates a directory structure with all the different categories from Video on Demand and saves the video URLs in strm-files (which then can be played by Kodi). This should work for most of the languages that JW Broadcasting has, but I have only tested English and Swedish.

My scripting skills aren't the best, so this script takes a lot of CPU. Yes, I said A LOT. On my old Pentium 4 it takes 10 minutes to finish (saving 1400 links).

## Usage:
    kodiator [options] [KEY] [DIRECTORY]
      --lang LANGUAGE       Language of the videos. Selecting no language will show a list of available language codes
      --no-recursive        Just download this file
      --no-cleanup          Keep temporary files
      KEY                   Name of the file to download and process
      DIRECTORY             Directory to save the .strm files in


