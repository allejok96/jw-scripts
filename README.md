# JW scripts

### 2017-05-23: HUGE UPDATE! This is ported to Python now (still beta)

---

### JW Broadcasting and sound recordings anywhere

With these scripts you can get the latest [JW Broadcasting](http://tv.jw.org/) videos automatically downloaded to your Plex library, or painlessly stream sound recordings of [publications at JW.ORG](https://www.jw.org/en/publications/) to your phone, or via Kodi. You can turn a Raspberry Pi into a JW streaming machine by playing the [online stream](http://tv.jw.org/#en/live/StreamingOurStudio), or automatically downloading the latest videos and playing them offline (work in progress).

## Get started

*For Windows 10 instructions, click [here](https://github.com/allejok96/jw-scripts/wiki/Installation#installation-on-windows-10).*

Fisrt make sure to install `python-setuptools` or `python3-setuptools` depending on your distro.

Install the scripts

    git clone https://github.com/allejok96/jw-scripts.git
    cd jw-scripts
    sudo python3 setup.py install

Next, click on one of the scripts below for more info (the info there can be wrong as the scripts been ported to Python)

* [jwb-index](https://github.com/allejok96/jw-scripts/wiki/jwb-index) - Download videos from JW Broadcasting, or make playlists. Can be used together with **Plex** or **Kodi**.
* [jwb-stream](https://github.com/allejok96/jw-scripts/wiki/jwb-stream) - Stream from JW Broadcasting in your media player of choice, like **VLC**.
* [nwt-index](https://github.com/allejok96/jw-scripts/wiki/nwt-index) - Download Bible or publication recordings from JW.ORG, or make playlists.

## Questions

#### Isn't there an easier way to watch JW Broadcasting in Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/).

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag ([why?](https://github.com/allejok96/jw-scripts/wiki/How-it-works#batch-downloading)). 

*But please, somebody think of the servers!* :-)

#### Is this legal?

Yes. The [Terms of Service](http://www.jw.org/en/terms-of-use/) allows:

> distribution of free, non-commercial applications designed to download electronic files (for example, EPUB, PDF, MP3, AAC, MOBI, and MP4 files) from public areas of this site.

#### Why doesn't this do XYZ?

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues), and I'll see what I can do.
