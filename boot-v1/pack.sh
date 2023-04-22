#!/usr/bin/env sh

cd "$(dirname "$0")"

../packrd-gz.sh
cp ../rd-new.cpio.gz ramdisk.gz

mkbootimg \
    --kernel zImage \
    --ramdisk ramdisk.gz \
    --cmdline "$(cat cmdline)" \
    --board "$(cat board)" \
    --base "$(cat base)" \
    --pagesize "$(cat pagesize)" \
    --kernel_offset "$(cat kernel_offset)" \
    --ramdisk_offset "$(cat ramdisk_offset)" \
    --second_offset "$(cat second_offset)" \
    --tags_offset "$(cat tags_offset)" \
    --os_version "$(cat os_version)" \
    --os_patch_level "$(cat os_patch_level)" \
    -o new.img
