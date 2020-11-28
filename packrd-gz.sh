#!/usr/bin/env bash

set -ve

cd "$(dirname "$0")"
oldwd="$PWD"
cd rd
find . | cpio -o -H newc | pigz -9c > "$oldwd/rd-new.cpio"
