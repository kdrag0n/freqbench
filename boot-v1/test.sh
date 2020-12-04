#!/usr/bin/env sh

cd "$(dirname "$0")"

./pack.sh && fastboot boot new.img
