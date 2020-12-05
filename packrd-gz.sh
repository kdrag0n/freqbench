#!/usr/bin/env bash

set -ve

cd "$(dirname "$0")"

cp -af init.sh rd/init
cp -af usb.sh bench.py dhcpd.conf rd/

oldwd="$PWD"
cd rd
find . | cpio -o -H newc | pigz -9c > "$oldwd/rd-new.cpio"
