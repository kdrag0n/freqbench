#!/usr/bin/env sh

cd "$(dirname "$0")"

unpackbootimg -i "$1"
rename "$1-" "" "$1-"*
