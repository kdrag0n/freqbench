#!/usr/bin/env sh

set -eufo pipefail

cd "$(dirname "$0")"

cp ~/code/android/devices/zf6/proton/out/arch/arm64/boot/Image.gz-dtb zImage
./pack.sh
adb reboot bootloader || true
fastboot boot new.img
