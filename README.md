# jw-kodiator

This is a shellscript I wrote so I could watch JW Broadcasting on my Raspberry pi running Kodi.

It downloads and parses files from mediator.jw.org, which I guess are ment to be used by Roku. Then it creates a directory structure with the different categories from Video on Demand and stores the video URLs in strm-files.

This script is not beautiful, nor easy to wrap ones head around. The comments is in swedish (because that's what I speak). Maybe I'll translate it in the future.

It requires bash, egrep, curl and GNU sed to work.

The best would be to have a Kodi addon that does this on the fly, but I can't script anything but bash for the moment.

## Usage:
    kodiator [options] [KEY] [DIRECTORY]
      --no-recursive        Do not download other files than KEY.
      --no-cleanup          Do not remove temp files.
      KEY                   The name of the file to download. Default: VideoOnDemand
      DIRECTORY             Directory to store the files. Default: /tmp/kodi
