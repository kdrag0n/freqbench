#!/usr/bin/env bash

oldwd="$PWD"
cd "$(dirname "$0")"

./packrd-gz.sh

pushd anykernel
cp ../rd-new.cpio.gz .
rm -f "$oldwd/freqbench-installer.zip"
zip -r0 "$oldwd/freqbench-installer.zip" .
popd
