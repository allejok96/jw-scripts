# jw-kodiator

This is a bash script I wrote so I could watch JW Broadcasting (tv.jw.org) on my Raspberry pi running Kodi (XBMC).

Then i discovered that someone actually made an add-on a month earlier:
https://github.com/ca0abinary/plugin.video.jwtv-unofficial

Which kind of makes this script useless.

## Usage:
    kodiator [options] [KEY] [DIRECTORY]
      --no-recursive        Do not download other files than KEY.
      --no-cleanup          Do not remove temp files.
      KEY                   The name of the file to download. Default: VideoOnDemand
      DIRECTORY             Directory to store the files. Default: /tmp/kodi

The script downloads and parses files from mediator.jw.org, creates a directory structure with the different categories and stores the video URLs in strm-files. It requires bash, egrep, curl and GNU sed to work.
