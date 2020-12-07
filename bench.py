#!/usr/bin/env python3

import os
import time
import subprocess
import gc
import statistics
import json
import threading
import re
import csv

# Need to avoid as much extra CPU usage as possible
gc.disable()



####################################################
################### START CONFIG ###################
####################################################

# Verbose debug logging
# DO NOT ENABLE for final benchmarking!
# The extra framebuffer memory copies caused by it will influence results.
DEBUG = False

# sysfs power supply node for power sampling
POWER_SUPPLY = "/sys/class/power_supply/bms"
# qgauge updates every 100 ms, but sampling also uses power, so do it conservatively
# qpnp-fg-gen4 updates every 1000 ms
POWER_SAMPLE_INTERVAL = 250  # ms



####################################################
###################  END CONFIG  ###################
####################################################



# Must also set in init
HOUSEKEEPING_CPU = 0

# cpu0 is for housekeeping, so we can't benchmark it
# Benchmark cpu1 instead, which is also in the little cluster
REPLACE_CPUS = {
    HOUSEKEEPING_CPU: 1,
}

# How long to idle at each freq and measure power before benchmarking
FREQ_IDLE_TIME = 5  # sec

# To reduce chances of an array realloc + copy during benchmark runs
PREALLOC_SECONDS = 300  # seconds of power sampling
PREALLOC_SLOTS = int(PREALLOC_SECONDS / (POWER_SAMPLE_INTERVAL / 1000))

# CoreMark PERFORMANCE_RUN params with 250,000 iterations
COREMARK_PERFORMANCE_RUN = ["0x0", "0x0", "0x66", "250000", "7", "1", "2000"]

# Blank lines are for rounded corner & camera cutout protection
BANNER = """



  __                _                     _     
 / _|_ __ ___  __ _| |__   ___ _ __   ___| |__  
| |_| '__/ _ \/ _` | '_ \ / _ \ '_ \ / __| '_ \ 
|  _| | |  __/ (_| | |_) |  __/ | | | (__| | | |
|_| |_|  \___|\__, |_.__/ \___|_| |_|\___|_| |_|
                 |_|                            

           CPU benchmark • by kdrag0n

------------------------------------------------
"""

SYS_CPU = "/sys/devices/system/cpu"

_stop_power_mon = False
_prealloc_samples = [-1] * PREALLOC_SLOTS
_power_samples = _prealloc_samples

def pr_debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_cmd(args):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode == 0:
        return proc.stdout
    else:
        raise ValueError(f"Subprocess {args} failed with exit code {proc.returncode}:\n{proc.stdout}")

def sample_power():
    with open(f"{POWER_SUPPLY}/current_now", "r") as f:
        ma = int(f.read()) / 1000
    with open(f"{POWER_SUPPLY}/voltage_now", "r") as f:
        mv = int(f.read()) / 1000

    mw = ma * mv / 1000
    return abs(mw)

def start_power_thread(sample_interval=POWER_SAMPLE_INTERVAL):
    def _power_thread():
        global _power_samples

        sample_dest = _prealloc_samples

        count = 0
        while True:
            # Sleep before first sample to avoid a low first reading
            time.sleep(sample_interval / 1000)

            # Check stop flag immediately after sleep to avoid a low last reading
            if _stop_power_mon:
                break

            power = sample_power()
            pr_debug(f"Power: {power}\t(sample {count})")

            try:
                sample_dest[count] = power
            except IndexError:
                # If out of pre-allocated slots
                sample_dest.append(power)

            count += 1

        if count < len(sample_dest):
            _power_samples = sample_dest[:count]

    thread = threading.Thread(target=_power_thread, daemon=True)
    thread.start()
    return thread

def stop_power_thread(thread):
    global _stop_power_mon

    _stop_power_mon = True
    thread.join()
    _stop_power_mon = False

    return _power_samples

def write_cpu(cpu, node, content):
    with open(f"{SYS_CPU}/cpu{cpu}/{node}", "w") as f:
        f.write(content)

def read_cpu(cpu, node):
    with open(f"{SYS_CPU}/cpu{cpu}/{node}", "r") as f:
        return f.read().strip()

def create_power_stats(time_ns, samples):
    sec = time_ns / 1e9

    power = statistics.mean(samples)
    mj = power * sec
    joules = mj / 1000

    return {
        "elapsed_sec": sec,
        "elapsed_ns": time_ns,
        "power_samples": samples,
        "power_mean": power,
        "energy_millijoules": mj,
        "energy_joules": joules,
    }

def main():
    bench_start_time = time.time()

    print(BANNER)

    print("Frequency domains: ", end="", flush=True)
    bench_cpus = []
    for policy_dir in sorted(os.listdir(f"{SYS_CPU}/cpufreq")):
        if policy_dir.startswith("policy"):
            first_cpu = int(policy_dir[len("policy"):])
            if first_cpu in REPLACE_CPUS:
                first_cpu = REPLACE_CPUS[first_cpu]

            print(f"cpu{first_cpu}", end=" ", flush=True)
            bench_cpus.append(first_cpu)
        else:
            print(f"Unrecognized file/dir in cpufreq: {policy_dir}")
            continue
    print()

    print("Offline CPUs: ", end="", flush=True)
    with open("/proc/cpuinfo", "r") as f:
        cpuinfo = f.read()
        cpu_count = len(re.findall(r'processor\s+:\s+\d+', cpuinfo))

    for cpu in range(cpu_count):
        if cpu == HOUSEKEEPING_CPU:
            continue

        print(f"cpu{cpu}", end=" ", flush=True)
        write_cpu(cpu, "online", "0")
    print(flush=True)

    pr_debug("Minimizing frequency of housekeeping CPU")
    write_cpu(HOUSEKEEPING_CPU, "cpufreq/scaling_governor", "powersave")
    pr_debug()

    print("Baseline power usage: ", end="", flush=True)
    pr_debug("Waiting for power usage to settle", flush=True)
    time.sleep(15)
    pr_debug()

    pr_debug("Measuring base power usage with only housekeeping CPU")
    # The power used for sampling might affect results here, so sample less often
    thread = start_power_thread(sample_interval=POWER_SAMPLE_INTERVAL * 2)
    time.sleep(60)
    base_power_samples = stop_power_thread(thread)
    base_power = min(base_power_samples)
    print(f"{base_power:.0f} mW")
    print()

    pr_debug("Starting benchmark")
    pr_debug()

    cpus_data = {}
    for cpu in bench_cpus:
        print()
        print(f"===== CPU {cpu} =====")

        cpu_data = {
            "freqs": {}
        }
        cpus_data[cpu] = cpu_data

        pr_debug("Onlining CPU")
        write_cpu(cpu, "online", "1")

        pr_debug("Setting governor")
        write_cpu(cpu, "cpufreq/scaling_governor", "userspace")

        pr_debug("Getting frequencies")
        with open(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_available_frequencies", "r") as f:
            raw_freqs = f.read().replace("\n", "").split(" ")
            freqs = [int(freq) for freq in raw_freqs if freq]

        # Some kernels may change the defaults
        pr_debug("Setting frequency limits")
        write_cpu(cpu, "cpufreq/scaling_min_freq", str(min(freqs)))
        write_cpu(cpu, "cpufreq/scaling_max_freq", str(max(freqs)))

        # Bail out if the kernel is clamping our values
        pr_debug("Validating frequency limits")
        real_min_freq = int(read_cpu(cpu, "cpufreq/scaling_min_freq"))
        if real_min_freq != min(freqs):
            raise ValueError(f"Minimum frequency setting {min(freqs)} rejected by kernel; got {real_min_freq}")
        real_max_freq = int(read_cpu(cpu, "cpufreq/scaling_max_freq"))
        if real_max_freq != max(freqs):
            raise ValueError(f"Maximum frequency setting {max(freqs)} rejected by kernel; got {real_max_freq}")

        # Need to sort because different platforms have different orders
        freqs.sort()
        print("Frequencies:", " ".join(str(int(freq / 1000)) for freq in freqs))
        print()

        for freq in freqs:
            mhz = freq / 1000
            print(f"{int(mhz):4d}: ", end="", flush=True)
            write_cpu(cpu, "cpufreq/scaling_setspeed", str(freq))

            pr_debug("Waiting for frequency to settle")
            time.sleep(0.1)

            pr_debug("Validating frequency")
            real_freq = int(read_cpu(cpu, "cpufreq/scaling_cur_freq"))
            if real_freq != freq:
                raise ValueError(f"Frequency setting is {freq} but kernel is using {real_freq}")

            pr_debug("Waiting for power usage to settle")
            time.sleep(3)

            pr_debug("Measuring idle power usage")
            thread = start_power_thread()
            time.sleep(FREQ_IDLE_TIME)
            idle_power_samples = stop_power_thread(thread)
            idle_power = statistics.mean(idle_power_samples)
            idle_mj = idle_power * FREQ_IDLE_TIME
            idle_joules = idle_mj / 1000
            pr_debug(f"Idle: {idle_power:4.0f} mW    {idle_joules:4.1f} J")

            pr_debug("Running CoreMark...")
            thread = start_power_thread()
            start_time = time.time_ns()
            cm_out = run_cmd(["taskset", "-c", f"{cpu}", "coremark", *COREMARK_PERFORMANCE_RUN])
            end_time = time.time_ns()
            power_samples = stop_power_thread(thread)

            pr_debug(cm_out)
            elapsed_sec = (end_time - start_time) / 1e9

            # Extract score and iterations
            match = re.search(r'CoreMark 1\.0 : ([0-9.]+?) / ', cm_out)
            score = float(match.group(1))
            match = re.search(r'Iterations\s+:\s+(\d+)', cm_out)
            iters = float(match.group(1))

            # Adjust for base power usage
            power_samples = [sample - base_power for sample in power_samples]

            # Calculate power values
            power = statistics.mean(power_samples)
            # CoreMarks/MHz as per EEMBC specs
            cm_mhz = score / mhz
            # mW * sec = mJ
            mj = power * elapsed_sec
            joules = mj / 1000
            # ULPMark-CM score = iterations per millijoule
            ulpmark_score = iters / mj

            print(f"{score:5.0f}     {cm_mhz:3.1f} C/MHz   {power:4.0f} mW   {joules:4.1f} J   {ulpmark_score:4.1f} I/mJ   {elapsed_sec:5.1f} s")

            cpu_data["freqs"][freq] = {
                "active": {
                    **create_power_stats(end_time - start_time, power_samples),
                    "coremark_score": score,
                    "coremarks_per_mhz": cm_mhz,
                    "ulpmark_cm_score": ulpmark_score
                },
                "idle": create_power_stats(int(FREQ_IDLE_TIME * 1e9), idle_power_samples),
            }

        # In case the CPU shares a freq domain with the housekeeping CPU, e.g. cpu1
        pr_debug("Reverting governor")
        write_cpu(cpu, "cpufreq/scaling_governor", "powersave")

        pr_debug("Offlining CPU")
        write_cpu(cpu, "online", "0")
        print()

    # Make the rest run faster
    pr_debug("Maxing housekeeping CPU frequency")
    write_cpu(HOUSEKEEPING_CPU, "cpufreq/scaling_governor", "performance")

    # OK to GC beyond this point as all the benchmarking is done
    pr_debug("Enabling Python GC")
    gc.enable()

    print()
    print("Benchmark finished!")

    bench_finish_time = time.time()

    pr_debug("Writing JSON data")
    data = {
        "version": 1,
        "total_elapsed_sec": bench_finish_time - bench_start_time,
        "housekeeping": create_power_stats(int(5 * 1e9), base_power_samples),
        "cpus": cpus_data,
        "meta": {
            "housekeeping_cpu": HOUSEKEEPING_CPU,
            "power_sample_interval": POWER_SAMPLE_INTERVAL,
            "cpu_count": cpu_count,
        },
    }

    results_json = json.dumps(data)
    pr_debug(results_json)
    with open("/tmp/results.json", "w+") as f:
        f.write(results_json)

    pr_debug("Writing CSV data")
    with open("/tmp/results.csv", "w+") as f:
        fields = [
            "CPU",
            "Frequency (kHz)",
            "CoreMarks (iter/s)",
            "CoreMarks/MHz",
            "Power (mW)",
            "Energy (J)",
            "ULPMark-CM (iter/mJ)",
            "Time (s)"
        ]

        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for cpu, cpu_data in cpus_data.items():
            for freq, freq_data in cpu_data["freqs"].items():
                freq_data = freq_data["active"]

                writer.writerow({
                    "CPU": cpu,
                    "Frequency (kHz)": freq,
                    "CoreMarks (iter/s)": freq_data["coremark_score"],
                    "CoreMarks/MHz": freq_data["coremarks_per_mhz"],
                    "Power (mW)": freq_data["power_mean"],
                    "Energy (J)": freq_data["energy_joules"],
                    "ULPMark-CM (iter/mJ)": freq_data["ulpmark_cm_score"],
                    "Time (s)": freq_data["elapsed_sec"],
                })

if __name__ == "__main__":
    main()
