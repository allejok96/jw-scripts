# JW bash scripts

### JW Broadcasting and bible sound recordings anywhere

With these scripts you can get the latest [JW Broadcasting](http://tv.jw.org/) videos automatically downloaded to your Plex library, or painlessly stream sound recordings of the [New World Translation](https://www.jw.org/en/publications/bible/nwt/books/) to your phone, or via Kodi. You can turn a Raspberry Pi into a JW streaming machine, either playing the [online stream](http://tv.jw.org/#en/live/StreamingOurStudio), or automatically downloading the latest videos and playing them offline.

[Here](https://github.com/allejok96/jw-scripts/wiki/Installation) is how to install, and the requirements.

Click the links below for more help on each script.

#### [jwb-index](https://github.com/allejok96/jw-scripts/wiki/jwb-index)

Index the videos at tv.jw.org and save the links in playlists, or download the videos. Can be used to access JW Broadcasting in Kodi or add the videos to your Plex library.

#### [jwb-stream](https://github.com/allejok96/jw-scripts/wiki/jwb-stream)

Play one of the "streaming channels" at tv.jw.org in a media player.

#### [jwb-rpi](https://github.com/allejok96/jw-scripts/wiki/jwb-rpi)

Create an "offline" streaming channel, playing videos 24-7. Download new videos from tv.jw.org regulary and delete old videos when disk is full.

[Raspberry Pi how-to](https://github.com/allejok96/jw-scripts/wiki/jwb-rpi#installation-and-preparation)

#### [nwt-index](https://github.com/allejok96/jw-scripts/wiki/nwt-index)

Create playlists of the sound recordings of the New World Translation of the Holy Scriptures. You can put the playlists in your smartphone, Kodi library, or open them by any media player. Can also download all recordings.

## Questions

#### Isn't there an easier way to watch JW Broadcasting in Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/).

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag ([why?](https://github.com/allejok96/jw-scripts/wiki/How-it-works#batch-downloading)). 

*But please, somebody think of the servers!* :-)

#### Is this legal?

Yes. The [Terms of Service](http://www.jw.org/en/terms-of-use/) allows:

> distribution of free, non-commercial applications designed to download electronic files (for example, EPUB, PDF, MP3, AAC, MOBI, and MP4 files) from public areas of this site.

More info [here](https://github.com/allejok96/jw-scripts/wiki/How-it-works#is-it-legal).

#### I want this to do XYZ! But it don't!

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues), and I'll see what I can do.
