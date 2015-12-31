# JW bash scripts

### These scripts creates playlists from the videos on JW Broadcasting and the bible sound recordings on jw.org.

#### jwb-index
This script creates a hierarchy of m3u playlists (or directories) containing the videos on [JW Broadcasting](http://tv.jw.org/). This should work for most of the languages, but I've only tested English and Swedish.

**First update:** Now you can download the actual video files with the `--download` flag.

** Second update:** Plex compatible! Organize videos in directories instead of in m3u playlists (see *How do I use this with Plex?*).

#### nwt-index
This script does almost the same thing as jwb-index, but instead it indexes the MP3 recordings of the New Worlds Translation from [jw.org](http://www.jw.org).

Most of the things written about jwb-index here also applies on nwt-index. Run `nwt-index --help` to get some more info.

#### jwb-stream

Soon to come...

## Questions

##### What are these scripts for?

I wrote the jwb-index script so I could watch JW Broadcasting on my Raspberry Pi running Kodi.

##### How do I use this with Kodi?

1. Run the script on your Linux rig (se `--help` for more options). Example:

`jwb-index --lang E ~/Videos/Broadcasting`

2. The script will create a link called "Video on Demand.m3u"
3. Add the "Broadcasting" directory as a source in Kodi
4. Open the playlist

##### How do I use this with Plex?

1. Run the script as usual, but you must add the `--download` and `--filesystem` flag, as Plex don't allow streaming files directly from the internet (if I'm wrong, please correct me). Example:

`jwb-index --lang E --download --filesystem ~/Videos/Broadcasting`

2. This will create a link called "Video on Demand".
3. Add that link as a library in Plex, choose the type "Home Videos".
4. Open it and enjoy!

##### Isn't there an easier way to watch JW Broadcasting on Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/) for Kodi.

##### If there already is a better add-on for Kodi, why did you make these scripts?

Because I didn't know about the add-on at the time.

But now these script has a use, as there seems to be no good way to watch JW Broadcasting on Plex.

I'm also planning to write a script for the videos on jw.org.

##### Can I have this running as a cron job?

Certanly! To spare some bandwidth (both for you and the server), please use the `--latest` flag. This will create a "Latest Videos" playlist/directory. It also tries to intelligently add the videos to their belonging categories.

If the directory gets messy and full of old, broken links, use the `--clean` flag to remove everything except the downloaded videos.

##### Why is the download of the videos so slow?

It seems to be realated to the `--limit-rate` flag. *But please, somebody think of the servers!* :)

##### How does this work?

The script downloads JSON files supplied by jw.org and mediator.jw.org. It then sorts out the titles and video links and saves them in m3u playlists or downloads them.

When downloading videos, existing files won't be overwritten. If a file gets corrupted, you must delete it manually before the script downloads a new version.

And yes, I know parsing JSON could be done a thousand times simpler in any programming/scripting language like Python, but unfortunately I only know bash.

##### Is this a violation of the ToS?

The [ToS](http://www.jw.org/en/terms-of-use/) states that "free, non-commercial applications designed to download electronic files" is allowed. So it's seems OK.

It's also worth mentioning that these scripts practically does the same thing as the JavaScripts that run when you visit the jw.org website. The only difference is that these bash scripts are more inefficient, and generates text instead of HTML.

##### I want this to do XYZ! But it don't!

If you have a feature request or have been bitten by a bug (let the friendly bugs be, they are hiding everywhere :) please [create an issue](https://github.com/allejok96/jw-kodiator/issues).
