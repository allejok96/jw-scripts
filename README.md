# jw-kodiator

This is a bash script for indexing JW Broadcasting (tv.jw.org).

The script downloads and parses JSON files and then creates a hierarchy of m3u playlists. This should work for most of the languages that JW Broadcasting has, but I have only tested English and Swedish.

The JSON files are located at mediator.jw.org and I wrote this script so I could watch JW Broadcasting on Kodi - hence the name Kodiator.
**There's a BETTER [unofficial JW Broadcasting add-on] (https://github.com/ca0abinary/plugin.video.jwtv-unofficial) for Kodi.**
I was unaware of that add-on when I made this script.

And yes, I know parsing JSON could be done a thousand times simpler in any programming/scripting language like Python, but unfortunately I only know bash.

## Usage:
    kodiator [options] [DIRECTORY]
      --lang LANGUAGE       Language to download. Selecting no language will show a list of available language codes
      --no-recursive        Just download this file/category
      --category CATEGORY   Name of the file/category to index
      DIRECTORY             Directory to save the playlists in
