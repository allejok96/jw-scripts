# JW bash scripts

###### Update 2016-08-03: New `html` mode + bugfix in `jwb-index` (you should upgrade to get videos in correct category)
###### Update 2016-08-02: `nwt-index` now downloads recordings of *any* publication from JW.ORG.

### JW Broadcasting and sound recordings anywhere

With these scripts you can get the latest [JW Broadcasting](http://tv.jw.org/) videos automatically downloaded to your Plex library, or painlessly stream sound recordings of [publications at JW.ORG](https://www.jw.org/en/publications/) to your phone, or via Kodi. You can turn a Raspberry Pi into a JW streaming machine, either playing the [online stream](http://tv.jw.org/#en/live/StreamingOurStudio), or automatically downloading the latest videos and playing them offline.

## Get started

Install the scripts ([requirements](https://github.com/allejok96/jw-scripts/wiki/Installation))

    git clone https://github.com/allejok96/jw-scripts.git
    cd jw-scripts
    sudo ./install.sh

Next, click on one of the scripts below for more info.

* [jwb-index](https://github.com/allejok96/jw-scripts/wiki/jwb-index) - Download videos from JW Broadcasting, or make playlists. Can be used together with **Plex** or **Kodi**.
* [jwb-stream](https://github.com/allejok96/jw-scripts/wiki/jwb-stream) - Stream from JW Broadcasting in your media player of choice, like **VLC**.
* [nwt-index](https://github.com/allejok96/jw-scripts/wiki/nwt-index) - Download Bible or publication recordings from JW.ORG, or make playlists.
* [jwb-rpi](https://github.com/allejok96/jw-scripts/wiki/jwb-rpi) - Create your own "streaming channel". Uses jwb-index + omxplayer + a lot of fancy.

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

#### Why doesn't this do XYZ?

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues), and I'll see what I can do.
