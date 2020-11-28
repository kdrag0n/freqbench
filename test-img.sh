#!/usr/bin/env bash

cd "$(dirname "$0")"

./pack-img.sh

adb reboot bootloader
fastboot boot bench.img
