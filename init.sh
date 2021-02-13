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

    reboot_with_cmd bootloader
}

saving_logs=false
on_exit() {
    if ! $saving_logs; then
        save_logs
    fi

    echo
    echo
    echo "ERROR!"

    reboot_end
}

# Set trap before mounting in case devtmpfs fails
trap on_exit EXIT

# Mount essential pseudo-filesystems
mount -t tmpfs tmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /tmp

# Populate /dev without devtmpfs
mdev -s

# Log to kernel log if no console is present
if [[ ! -t 1 ]]; then
    exec > /dev/kmsg 2>&1
fi

# Don't log anywhere
#exec > /dev/null 2>&1

find_part_by_name() {
    pinfo="$(blkid -l --match-token "PARTLABEL=$1"; blkid -l --match-token "PARTLABEL=${1^^}")"

    # Check for existence first
    if [[ -z "$pinfo" ]]; then
        return 1
    fi

    echo "$pinfo" | cut -d' ' -f1 | tr -d ':'
}

redact_arg() {
    sed -E "s/$1=[^ ]+/$1=REDACTED/"
}

redact_args() {
    redact_arg androidboot.serialno | \
        redact_arg androidboot.wifimacaddr | \
        redact_arg androidboot.btmacaddr | \
        redact_arg androidboot.uid | \
        redact_arg androidboot.ap_serial | \
        redact_arg androidboot.cpuid | \
        redact_arg LCD | \
        redact_arg androidboot.id.jtag | \
        redact_arg androidboot.em.did
}

# Add delay for error visibility
on_error() {
    e=$?
    sleep 5
    return $e
}

save_logs() {
    saving_logs=true

    # Gather system info
    # This is best-effort and does not strictly need to be present, so suppress errors here.
    set +e
    cat /proc/interrupts > /tmp/post_bench_interrupts.txt
    cat /proc/cmdline | redact_args > /tmp/cmdline.txt
    cat /proc/cpuinfo > /tmp/cpuinfo.txt
    dmesg | redact_args > /tmp/kernel.log
    uptime > /tmp/uptime.txt
    ps -A > /tmp/processes.txt
    echo "Kernel: $(cat /proc/version)" > /tmp/versions.txt
    echo "Python: $(python3 --version)" >> /tmp/versions.txt
    echo "Model: $(cat /sys/firmware/devicetree/base/model | tr '\0' ';')" > /tmp/device.txt
    echo "Compatible: $(cat /sys/firmware/devicetree/base/compatible | tr '\0' ';')" >> /tmp/device.txt

    mkdir /tmp/cpufreq_stats
    for policy in /sys/devices/system/cpu/cpufreq/policy*
    do
        pol_dir="/tmp/cpufreq_stats/$(basename "$policy" | sed 's/policy//')"
        mkdir "$pol_dir"
        # Frequency domains with too many OPPs will fail here
        cp "$policy/stats/"{time_in_state,total_trans,trans_table} "$pol_dir" 2> /dev/null || true
    done
    set -e

    mkdir /persist
    persist_part="$(find_part_by_name cache || find_part_by_name persist)"

    # We write everything to tmpfs and copy it to persist afterwards because writing to UFS will use power
    echo
    mount -o noatime "$persist_part" /persist

    echo "Writing logs and results to $OUT_DIR"
    rm -fr "$OUT_DIR"
    cp -r /tmp "$OUT_DIR"
    umount /persist
    sync

    # Saving logs multiple times is fine as long as we don't try to recurse
    saving_logs=false
}

try_write() {
    { echo "$2" > "$1"; } > /dev/null 2>&1 || true
}

# SSH debug over USB RNDIS
set +e
if $USB_DEBUG; then
    source /usb.sh
fi
set -e

# Disable fbcon cursor blinking to reduce interference from its 1-second timer and memory ops
try_write /sys/devices/virtual/graphics/fbcon/cursor_blink 0

# Disable hung task detection
try_write /proc/sys/kernel/hung_task_timeout_secs 0

# Snapdragon: Enable cpuidle for more realistic conditions
try_write /sys/module/lpm_levels/parameters/sleep_disabled 0
try_write /sys/module/msm_pm/parameters/sleep_disabled 0

# Exynos: Disable Exynos auto-hotplug to allow manual CPU control
try_write /sys/power/cpuhotplug/enabled 0

# Snapdragon: Initialize aDSP for power supply on newer SoCs
# On Snapdragon 888 (Qualcomm kernel 5.4) devices and newer, the DSP is
# responsible for power and charging, so we need to initialize it before we can
# read power usage from the fuel gauge.
if uname -r | grep -q '^5\.' && grep -q Qualcomm /proc/cpuinfo; then
    # qrtr nameserver is required for DSP services to work properly
    qrtr-ns &

    echo "Booting DSP..."
    echo -n 1 > /sys/kernel/boot_adsp/boot
    sleep 3
    if [[ "$(cat /sys/class/subsys/subsys_adsp/device/subsys*/state)" != "ONLINE" ]]; then
        echo "Failed to boot aDSP!"
        exit 1
    fi
fi

cat /proc/interrupts > /tmp/pre_bench_interrupts.txt

py_args=()
if ! $DEBUG; then
    py_args+=(-OO)
fi
py_args+=(/bench.py "$POWER_SAMPLE_INTERVAL")
time taskset 01 python3 "${py_args[@]}" 2>&1 | tee /tmp/run.log || on_error

save_logs

# To debug system load
#htop

reboot_end
