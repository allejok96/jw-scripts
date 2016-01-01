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
install -m 644 ./shared-functions /usr/local/lib/jw-scripts/shared-functions
