# JW bash scripts

### JW Broadcasting and bible sound recordings anywhere

With these scripts you can get the latest [JW Broadcasting](http://tv.jw.org/) videos automatically downloaded to your Plex library, or painlessly stream bible recordings from [jw.org](http://www.jw.org) to your phone or via Kodi. You can turn a Raspberry Pi into a JW [streaming](http://tv.jw.org/#en/live/StreamingOurStudio) machine, either playing the online stream, or an offline version.

[Here's](https://github.com/allejok96/jw-scripts/wiki/Installation) how you install them. Click the links below for more help on each script.

#### [jwb-index](https://github.com/allejok96/jw-scripts/wiki/jwb-index)

Index the videos at tv.jw.org and save the links in playlists, or download the videos. Can be used to access JW Broadcasting in Kodi or add the videos to your Plex library.

#### [jwb-stream](https://github.com/allejok96/jw-scripts/wiki/jwb-stream)

Play one of the "streaming channels" at tv.jw.org in a media player.

#### [jwb-rpi](https://github.com/allejok96/jw-scripts/wiki/jwb-rpi)

Create an "offline" streaming channel, playing videos 24-7. Download new videos from tv.jw.org regulary and delete old videos when disk is full.

#### [nwt-index](https://github.com/allejok96/jw-scripts/wiki/nwt-index)

Create playlists of the sound recordings of the New World Translation of the Holy Scriptures. You can put the playlists in your smartphone, Kodi library, or open them by any media player. Can also download all recordings.

## Questions

#### Isn't there an easier way to watch JW Broadcasting on Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/).

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag (see `--help`). 

*But please, somebody think of the servers!* :-)

#### Is this a violation of the ToS?

The [ToS](http://www.jw.org/en/terms-of-use/) states that *"free, non-commercial applications designed to download electronic files"* is allowed. So it's seems OK.

It's also worth mentioning that these scripts practically does the same thing as the JavaScripts that run when you visit the jw.org website. The only difference is that these bash scripts are more inefficient, and generates text files instead of HTML. (Oh, and they can download the media files too!)

#### I want this to do XYZ! But it don't!

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues), and I'll see what I can do.
