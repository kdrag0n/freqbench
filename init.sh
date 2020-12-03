#!/usr/bin/env bash

# Deps: python3 util-linux bash
# Execs: /usr/bin/coremark
# Governors: powersave userspace
# Kernel config: CONFIG_DEVTMPFS
# Kernel cmdline: printk.devkmsg=on isolcpus=1-7 (depends on CPU count)

set -eufo pipefail


####################################################
################### START CONFIG ###################
####################################################

# Should usually stay the same
BLOCK_DEV=/dev/sda

# Must be in /persist or /tmp
OUT_DIR=/persist/freqbench

####################################################
###################  END CONFIG  ###################
####################################################


# Populate PATH and other basic settings
source /etc/profile

on_exit() {
    echo
    echo
    echo "ERROR!"
    echo
    echo "Press volume down to reboot..."
    echo
    echo

    read -n1
    reboot_with_cmd bootloader
}

# Set trap before mounting in case devtmpfs fails
trap on_exit EXIT

# Mount essential pseudo-filesystems
mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /tmp

find_part_by_name() {
    partnum="$(sgdisk -p "$BLOCK_DEV" | grep " $1$" | head -n1 | awk '{print $1}')"
    echo "$BLOCK_DEV$partnum"
}

# Add delay for error visibility
on_error() {
    e=$?
    sleep 5
    return $e
}

# SSH debug over USB RNDIS
#source /usb.sh

# Disable fbcon cursor blinking to reduce interference from its 1-second timer and memory ops
echo 0 > /sys/devices/virtual/graphics/fbcon/cursor_blink

# Enable cpuidle for more realistic conditions
{ echo 0 > /sys/module/lpm_levels/parameters/sleep_disabled; } > /dev/null 2>&1 || true
{ echo 0 > /sys/module/msm_pm/parameters/sleep_disabled; } > /dev/null 2>&1 || true

#exec > /dev/null 2>&1

cat /proc/interrupts > /tmp/pre_bench_interrupts.txt

taskset 01 python3 /bench.py 2>&1 | tee /tmp/run.log || on_error

cat /proc/interrupts > /tmp/post_bench_interrupts.txt

mkdir /persist
persist_part="$(find_part_by_name persist)"

# We write everything to tmpfs and copy it to persist afterwards because writing to UFS will use power
echo
mount -t ext4 -o noatime,nosuid,nodev,barrier=1 "$persist_part" /persist

echo "Writing logs and results to $OUT_DIR"
rm -fr "$OUT_DIR"
cp -r /tmp "$OUT_DIR"
umount /persist
sync

echo
echo "Press volume down to reboot..."
# Rounded corner protection
echo
echo
sleep 5
#read -n1
#sleep inf

# Busybox reboot doesn't work for some reason
reboot_with_cmd ''
