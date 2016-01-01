# JW bash scripts

### Get acess to JW Broadcasting and the bible sound recordings at jw.org in Kodi, Plex, or your media center of choice.

## jwb-index
This script creates playlists so you can stream from [JW Broadcasting](http://tv.jw.org/) on Kodi, or downloads the videos so you can add them to your Plex library. This should work for most of the languages, but I've only tested English and Swedish.

## nwt-index
This script does almost the same thing as jwb-index, but instead it indexes the MP3 recordings of the New Worlds Translation from [jw.org](http://www.jw.org). Most of the things written about jwb-index here also applies on nwt-index.

## jwb-stream

Soon to come...

## Usage
```sh
# Install the scripts system wide (optional)
sudo ./install.sh

# Kodi mode (streaming)
# Index all Swedish videos
jwb-index --lang Z ~/Videos/JWB

# Plex mode (offline)
# Download all videos
jwb-index --filesystem --download ~/Videos/JWB

# Make a quick update (Kodi)
jwb-index --latest ~/Videos/JWB

# Clean up and re-index everything (Plex)
jwb-index --filesystem --download --clean ~/Videos/JWB

# Make playlists with bible recordings (Kodi)
nwt-index ~/Bible
```
## Questions

#### How do I use this with Kodi?

1. Run the script on your Linux rig.
2. This will create a playlist called "Video on Demand.m3u".
3. Add the directory as a source in Kodi.
4. Open the playlist.

#### How do I use this with Plex?

1. Run the script with the `--download` and `--filesystem` flags.
2. This will create a link to a directory called "Video on Demand".
3. Add the link as a library in Plex, choose the type "Home Videos".

#### Isn't there an easier way to watch JW Broadcasting on Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/).

#### *Must* I download the videos if I have Plex?

Yes. It seems like Plex won't stream files directly from the internet, nor read playlists .If I'm wrong, please [correct](https://github.com/allejok96/jw-scripts/issues) me.

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag. *But please, somebody think of the servers!* :-)

#### How does this work?

The script downloads JSON files supplied by jw.org and mediator.jw.org. It then sorts out the titles and video links, optionally downloads them, and saves them in m3u playlists (Kodi mode) or creates a directory structure with symlinks (Plex mode). All data is saved in a subdirectory called "jwb-LANG" or "bi12-LANG".

When downloading media, existing files won't be overwritten. If a file gets corrupted, you must delete it manually before the script downloads a new version.

And yes, I know parsing JSON could be done a thousand times simpler in any programming/scripting language like Python, but unfortunately I only know bash.

#### Is this a violation of the ToS?

The [ToS](http://www.jw.org/en/terms-of-use/) states that *"free, non-commercial applications designed to download electronic files"* is allowed. So it's seems OK.

It's also worth mentioning that these scripts practically does the same thing as the JavaScripts that run when you visit the jw.org website. The only difference is that these bash scripts are more inefficient, and generates text instead of HTML. (Oh and yes, nowdays it downloads the videos too!)

#### I want this to do XYZ! But it don't!

If you have a feature request or have been bitten by a bug (let the friendly bugs be, they are hiding everywhere :-) please [create an issue](https://github.com/allejok96/jw-scripts/issues).
