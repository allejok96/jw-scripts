#!/bin/bash

if [[ $1 = --help ]]; then
    echo Installs the files to /usr/local
    exit
fi

if [[ $UID != 0 ]]; then
    echo "Must run as root"
    exit 1
fi

install -d /usr/local/bin /usr/local/lib/jw-scripts
install -m 755 ./jwb-index /usr/local/bin/jwb-index
install -m 755 ./nwt-index /usr/local/bin/nwt-index
install -m 755 ./jwb-stream /usr/local/bin/jwb-stream
install -m 755 ./jwb-rpi /usr/local/bin/jwb-rpi
install -m 755 ./jwb-rpi-downloader /usr/local/bin/jwb-rpi-downloader
install -m 644 ./shared-functions /usr/local/lib/jw-scripts/shared-functions

install -m 644 -t /etc/systemd/system/ ./systemd/*

if [[ -e /etc/jwb-rpi.conf ]]; then
    echo "installing jwb-rpi.conf as /etc/jwb-rpi.conf.new"
    install -m 644 ./jwb-rpi.conf /etc/jwb-rpi.conf.new
else
    install -m 644 ./jwb-rpi.conf /etc/jwb-rpi.conf
fi
