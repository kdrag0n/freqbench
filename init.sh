#!/usr/bin/env bash

set -euo pipefail

# Populate PATH and other basic env
source /etc/profile
# For htop config
export HOME=/root

source /config.sh

# Must be in /persist or /tmp
# /persist will be mounted from the cache partition if it exists
OUT_DIR=/persist/freqbench

reboot_end() {
    echo
    echo "Rebooting in 5 seconds..."
    # Rounded corner protection
    echo
    echo
    sleep 5

    # Wait for volume down keypress
    #read -n1
    # Wait for manual forced reboot
    #sleep inf

    # Busybox reboot doesn't work for some reason
    reboot_with_cmd "$1"
}

saving_logs=false
on_exit() {
    if ! $saving_logs; then
        save_logs
    fi

    echo
    echo
    echo "ERROR!"

    reboot_end bootloader
}

# Set trap before mounting in case devtmpfs fails
trap on_exit EXIT

# Mount essential pseudo-filesystems
mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /tmp

# Log to kernel log if no console is present
if [[ ! -t 1 ]]; then
    exec > /dev/kmsg 2>&1
fi

# Don't log anywhere
#exec > /dev/null 2>&1

find_part_by_name() {
    plist="$(sgdisk -p "$BLOCK_DEV")"
    # Check for existence first
    echo "$plist" | grep -qi " $1$" || return $?

    partnum="$(echo "$plist" | grep -i " $1$" | head -n1 | awk '{print $1}')"
    if [[ -e "${BLOCK_DEV}p1" ]]; then
        echo "${BLOCK_DEV}p${partnum}"
    else
        echo "${BLOCK_DEV}${partnum}"
    fi
}

redact_serial() {
    sed -E 's/androidboot.serialno=[A-Za-z0-9]+/androidboot.serialno=REDACTED/'
}

# Add delay for error visibility
on_error() {
    e=$?
    sleep 5
    return $e
}

save_logs() {
    saving_logs=true

    mkdir /persist
    persist_part="$(find_part_by_name cache || find_part_by_name persist)"

    # We write everything to tmpfs and copy it to persist afterwards because writing to UFS will use power
    echo
    mount -t ext4 -o noatime,nosuid,nodev,barrier=1 "$persist_part" /persist

    echo "Writing logs and results to $OUT_DIR"
    rm -fr "$OUT_DIR"
    cp -r /tmp "$OUT_DIR"
    umount /persist
    sync

    # Saving logs multiple times is fine as long as we don't try to recurse
    saving_logs=false
}

# SSH debug over USB RNDIS
set +e
if $USB_DEBUG; then
    source /usb.sh
fi
set -e

# Disable fbcon cursor blinking to reduce interference from its 1-second timer and memory ops
{ echo 0 > /sys/devices/virtual/graphics/fbcon/cursor_blink; } > /dev/null 2>&1 || true

# Enable cpuidle for more realistic conditions
{ echo 0 > /sys/module/lpm_levels/parameters/sleep_disabled; } > /dev/null 2>&1 || true
{ echo 0 > /sys/module/msm_pm/parameters/sleep_disabled; } > /dev/null 2>&1 || true

cat /proc/interrupts > /tmp/pre_bench_interrupts.txt

time taskset 01 python3 /bench.py $DEBUG $POWER_SAMPLE_INTERVAL 2>&1 | tee /tmp/run.log || on_error

# Gather system info
set +e
cat /proc/interrupts > /tmp/post_bench_interrupts.txt
cat /proc/cmdline | redact_serial > /tmp/cmdline.txt
cat /proc/cpuinfo > /tmp/cpuinfo.txt
dmesg | redact_serial > /tmp/kernel.log
uptime > /tmp/uptime.txt
ps -A > /tmp/processes.txt
echo "Kernel: $(cat /proc/version)" > /tmp/versions.txt
echo "Python: $(python3 --version)" >> /tmp/versions.txt
echo "Model: $(cat /sys/firmware/devicetree/base/model | tr '\0' ';')" > /tmp/device.txt
echo "Compatible: $(cat /sys/firmware/devicetree/base/compatible | tr '\0' ';')" >> /tmp/device.txt
find /dev > /tmp/dev.list
find /sys | gzip > /tmp/sysfs.list.gz

mkdir /tmp/cpufreq_stats
for policy in /sys/devices/system/cpu/cpufreq/policy*
do
    pol_dir="/tmp/cpufreq_stats/$(basename "$policy" | sed 's/policy//')"
    mkdir "$pol_dir"
    # Frequency domains with too many OPPs will fail here
    cp "$policy/stats/"{time_in_state,total_trans,trans_table} "$pol_dir" 2> /dev/null || true
done
set -e

save_logs

# To debug system load
#htop

reboot_end ''
