#!/bin/bash

if [[ $1 = --help ]]; then
    echo Installs the files to /usr/local
    exit
fi

if [[ $UID != 0 ]]; then
    echo "Must run as root"
    exit 1
fi

prefix=/usr/local

bin="$prefix/bin"
lib="$prefix/lib/jw-scripts"
share="$prefix/share/jw-scripts"

install -d "$bin" "$lib" /etc/systemd/system
install -m 755 -t "$bin" ./jwb-index ./nwt-index ./jwb-stream ./jwb-rpi ./jwb-rpi-downloader
install -m 755 -t "$lib" ./autoimport.sh
install -m 644 -t "$lib" ./shared-functions
install -m 644 -t /etc/systemd/system/ ./systemd/*

if [[ -e /etc/jw.conf ]]; then
    echo "installing jw.conf as /etc/jw.conf.new"
    install -m 644 ./jw.conf /etc/jw.conf.new
else
    install -m 644 ./jw.conf /etc/jw.conf
fi

[[ -e /etc/jwb-rpi.conf ]] && echo "Configuration file and several flags for jw-scripts has been re-done. Please have a look at /etc/jw.conf. Also check any custom systemd units that you have set up. Then remove /etc/jwb-rpi.conf to get rid of this message."
