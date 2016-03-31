# JW bash scripts

### JW Broadcasting and bible sound recordings anywhere

With these scripts you can get the latest [JW Broadcasting](http://tv.jw.org/) videos automatically downloaded to your Plex library, or painlessly stream bible recordings from [jw.org](http://www.jw.org) to phone or in Kodi.

A script for JW Broadcasting [live streaming](http://tv.jw.org/#en/live) is also in the works...

## Usage
This is just examples. See `--help` for more info.
```sh
# Install the scripts system wide (optional)
sudo ./install.sh

# For phone or any media player (playlists)
# Make playlists of all bible books
nwt-index --mode=m3ucompat

# For Kodi (playlist hierarchy)
# Index all Swedish videos
jwb-index --mode=m3u --lang=Z ~/Videos/JWB

# For Plex (download to directories)
# Download all videos in medium quality
jwb-index --mode=filesystem --download --quality=480 ~/Videos/JWB

# Make a quick update (Kodi)
jwb-index --mode=m3u --latest ~/Videos/JWB

```
## Questions

#### How do I use this with Kodi?

1. Run the script on your Linux rig.
2. This will create a playlist called "Video on Demand.m3u".
3. Add the directory as a source in Kodi.
4. Open the playlist.

#### How do I use this with Plex?

1. Run the script with the `--download` and `--mode=filesystem` flags.
2. This will create a link to a directory called "Video on Demand".
3. Add the link as a library in Plex, choose the type "Home Videos".

#### How do I use this on my phone or other device?

1. Run the script with the `--mode=m3ucompat` flag.
2. This will create a bunch of playlists.
3. Copy all playlists to you device.
4. Open a playlist with media player of choice.

#### Isn't there an easier way to watch JW Broadcasting on Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/).

#### *Must* I download the videos if I have Plex?

Yes. It seems like Plex won't stream files directly from the internet, nor read playlists .If I'm wrong, please [correct](https://github.com/allejok96/jw-scripts/issues) me.

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag. *But please, somebody think of the servers!* :-)

#### How does this work?

The script downloads JSON files supplied by jw.org and mediator.jw.org. It then sorts out the titles and video links, optionally downloads them, and saves them in m3u playlists or creates a directory structure with symlinks.

When downloading media, existing files won't be overwritten. If a file gets corrupted, you must delete it manually before the script downloads a new version.

And yes, I know parsing JSON could be done a thousand times simpler in any programming/scripting language like Python, but unfortunately I only know bash.

#### Is this a violation of the ToS?

The [ToS](http://www.jw.org/en/terms-of-use/) states that *"free, non-commercial applications designed to download electronic files"* is allowed. So it's seems OK.

It's also worth mentioning that these scripts practically does the same thing as the JavaScripts that run when you visit the jw.org website. The only difference is that these bash scripts are more inefficient, and generates text instead of HTML. (Oh and yes, nowdays it downloads the videos too!)

#### I want this to do XYZ! But it don't!

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues).
