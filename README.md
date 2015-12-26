# JW bash scripts

### These scripts creates playlists from the videos on JW Broadcasting and the bible sound recordings on jw.org.

#### jwb-index
This script creates a hierarchy of m3u playlists containing the videos and categories on [JW Broadcasting](http://tv.jw.org/). This should work for most of the languages, but I have only tested English and Swedish.

#### nwt-index
This script does almost the same thing as jwb-index, but instead it indexes the MP3 recordings of the New Worlds Translation from [jw.org](http://www.jw.org).

#### jwb-stream

Soon to come...

## Questions

##### What are these scripts for?

I wrote the jwb-index script so I could watch JW Broadcasting on my Raspberry Pi running Kodi.

##### Isn't there an easier way to watch JW Broadcasting on Kodi?

YES. There is. Please take a look at this [unofficial JW Broadcasting add-on](http://ca0abinary.github.io/plugin.video.jwtv-unofficial/) for Kodi.

##### If there already is a better add-on for Kodi, why did you make these scripts?

Because I didn't know about the add-on at the time.

And there was a JW.ORG add-on for Kodi but is broken and gone, so the bible-index script is the only way I'm able to play the bible recordings on my Pi.

I'm also planning to write a script for the videos on jw.org.

##### How do I use this?

1. Run the script on your Linux rig (optionally choose a language with the --lang flag)
2. The script will create a directory with playlists
3. Open the first playlist in the directory with a media player e.g. Kodi

##### How does this work?

The script downloads JSON files supplied by jw.org and mediator.jw.org. It then sorts out the titles and video links and saves them in m3u playlists.

And yes, I know parsing JSON could be done a thousand times simpler in any programming/scripting language like Python, but unfortunately I only know bash.

##### Is this a violation of the ToS?

The [ToS](http://www.jw.org/en/terms-of-use/) states that "free, non-commercial applications designed to download electronic files" is allowed. So it's seems OK.

It's also worth mentioning that these scripts practically does the same thing as the JavaScripts that run when you visit the jw.org website. The only difference is that these bash scripts are more inefficient, and generates text instead of HTML.

### Parameters:
    Usage: jwb-index [options] [DIRECTORY]
      --lang CODE   Select language code. Selecting none will
     	            show a list of available codes.
      --res QUALITY Choose between 240, 360, 480 and 720
      DIRECTORY     Directory to save the playlists in

    Usage: nwt-index [options] [DIRECTORY]
      --lang CODE   Select language code. Selecting none will
                    show a list of available codes.
      --silver      Use the 2013 edition of the NWT.
      DIRECTORY     Directory to save the playlists in.


