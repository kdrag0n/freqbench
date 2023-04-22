#!/usr/bin/env bash

set -eufo pipefail

cd "$(dirname "$0")"

if command -v pigz > /dev/null 2>&1; then
    GZIP="pigz"
else
    GZIP="gzip"
fi

cp -af init.sh rd/init
cp -af config.sh usb.sh bench.py dhcpd.conf rd/
mkdir -p rd/{tmp,sys,srv,run,root,proc,opt,mnt,home,dev}
mkdir -p rd/var/{tmp,opt,mail,log,local,empty}

oldwd="$PWD"
cd rd
find . | cpio -o -H newc | "$GZIP" -9c > "$oldwd/rd-new.cpio.gz"
