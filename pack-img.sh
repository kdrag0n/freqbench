#!/usr/bin/env bash

oldwd="$PWD"
cd "$(dirname "$0")"

./packrd-gz.sh

python mkbootimg.py \
    --header_version 2 \
    --os_version 11.0.0 \
    --os_patch_level 2020-11 \
    --ramdisk rd-new.cpio.gz \
    --kernel alpine-Image.lz4 \
    --dtb alpine-dt.dtb \
    --cmdline 'console=ttyMSM0,115200n8 androidboot.console=ttyMSM0 printk.devkmsg=on msm_rtb.filter=0x237 ehci-hcd.park=3 service_locator.enable=1 androidboot.memcg=1 cgroup.memory=nokmem lpm_levels.sleep_disabled=1 usbcore.autosuspend=7 androidboot.usbcontroller=a600000.dwc3 swiotlb=2048 androidboot.boot_devices=soc/1d84000.ufshc loop.max_part=7 snd_soc_cs35l41_i2c.async_probe=1 i2c_qcom_geni.async_probe=1 st21nfc.async_probe=1 spmi_pmic_arb.async_probe=1 ufs_qcom.async_probe=1 buildvariant=user' \
    --kernel_offset 0x8000 \
    --ramdisk_offset 0x1000000 \
    --dtb_offset 0x1f00000 \
    --tags_offset 0x100 \
    --pagesize 4096 \
    --output "$oldwd/${1:-bench.img}"
