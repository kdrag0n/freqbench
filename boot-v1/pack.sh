#!/usr/bin/env sh

cd "$(dirname "$0")"

../pack-img.sh && cp ../rd-new.cpio ramdisk.gz && cp ~/code/android/devices/zf6/proton/out/arch/arm64/boot/Image.gz-dtb zImage

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
