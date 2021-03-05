# JW scripts

*These methods of acessing jw.org are, while legal, not officially supported by the organisation. Use them if you find it worth the time, pain and risk. But first, please take the time to read [w18.04 30-31](https://wol.jw.org/en/wol/d/r1/lp-e/2018364). Then consider buing a device which has official support for JW Broadcasting app. Like a Roku, Apple TV or Amazon Fire TV. It will give you a better and safer experience.*

### JW Broadcasting and sound recordings anywhere

With these scripts you can get the latest JW Broadcasting videos automatically downloaded to your Plex library. You can turn a computer (like a Raspberry Pi) into a JW TV, either by streaming directly, or by playing downloaded videos from your collection.

## Get started

Take a look at [installation methods](https://github.com/allejok96/jw-scripts/wiki/Installation) to get up and running.

For example, to download the latest videos in Swedish, you would run:

    python jwb-index --download --latest --lang=Z

Next, check out the [Wiki pages](https://github.com/allejok96/jw-scripts/wiki) for more examples and options.

## Questions

#### Isn't there an easier way to watch JW Broadcasting in Kodi?

Yes, I'm keeping an add-on alive [here](https://github.com/allejok96/plugin.video.jwb-unofficial).

#### Why is the video download so slow?

It seems to be realated to the `--limit-rate` flag ([why?](https://github.com/allejok96/jw-scripts/wiki/How-it-works#batch-downloading)). 

*But please, somebody think of the servers!* :-)

#### What happened to the script for Bible recordings?

Since all recordings can be easily downloaded from the website, and the script couldn't do more than one publication at a time I didn't see any practical use for it.

But checkout [@vbastianpc](https://github.com/vbastianpc)'s nice fork of it that can download sign language publications.

#### Is this legal?

Yes. The [Terms of Service](http://www.jw.org/en/terms-of-use/) allows:

> distribution of free, non-commercial applications designed to download electronic files (for example, EPUB, PDF, MP3, AAC, MOBI, and MP4 files) from public areas of this site.

I've also been in contact with the Scandinavian branch office, and they have confirmed that using software like this is legal according to the ToS.

___

If you have a feature request or have been bitten by a bug, please [create an issue](https://github.com/allejok96/jw-scripts/issues), and I'll see what I can do.
