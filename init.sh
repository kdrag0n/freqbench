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
# For htop config
export HOME=/root

saving_logs=false
on_exit() {
    if ! $saving_logs; then
        save_logs
    fi

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

# Log to kernel log
#exec > /dev/kmsg 2>&1
# Don't log anywhere
#exec > /dev/null 2>&1

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

save_logs() {
    saving_logs=true

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

    # Saving logs multiple times is fine as long as we don't try to recurse
    saving_logs=false
}

# SSH debug over USB RNDIS
set +e
#source /usb.sh
set -e

# Disable fbcon cursor blinking to reduce interference from its 1-second timer and memory ops
echo 0 > /sys/devices/virtual/graphics/fbcon/cursor_blink

# Enable cpuidle for more realistic conditions
{ echo 0 > /sys/module/lpm_levels/parameters/sleep_disabled; } > /dev/null 2>&1 || true
{ echo 0 > /sys/module/msm_pm/parameters/sleep_disabled; } > /dev/null 2>&1 || true

cat /proc/interrupts > /tmp/pre_bench_interrupts.txt

taskset 01 python3 /bench.py 2>&1 | tee /tmp/run.log || on_error

# Gather system info
cat /proc/interrupts > /tmp/post_bench_interrupts.txt
cat /proc/cmdline > /tmp/cmdline.txt
dmesg > /tmp/kernel.log
ps -A > /tmp/processes.txt
echo "Kernel: $(cat /proc/version)" > /tmp/versions.txt
echo "Python: $(python3 --version)" >> /tmp/versions.txt
find /dev > /tmp/dev.list
find /sys | gzip > /tmp/sysfs.list.gz

mkdir /tmp/cpufreq_stats
for policy in /sys/devices/system/cpu/cpufreq/policy*
do
    pol_dir="/tmp/cpufreq_stats/$(basename "$policy" | sed 's/policy/')"
    mkdir "$pol_dir"
    cp "$policy/"{time_in_state,total_trans,trans_table} "$pol_dir"
done

save_logs

# To debug system load
#htop

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
reboot_with_cmd ''
