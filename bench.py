#!/usr/bin/env python3

import os
import sys
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

# sysfs power supply nodes for power sampling
POWER_SUPPLY = None
POWER_SUPPLY_NODES = [
    # Qualcomm Battery Management System + fuel gauge: preferred when available for more info
    "/sys/class/power_supply/bms",
    # Most common
    "/sys/class/power_supply/battery",
]
# Some fuel gauges need current scaling
CURRENT_FACTOR = 1

# Default power sampling intervals
POWER_SAMPLE_INTERVAL = 1000  # ms
POWER_SAMPLE_FG_DEFAULT_INTERVALS = {
    # qgauge updates every 100 ms, but sampling also uses power, so do it conservatively
    "qpnp,qg": 250,
    # qpnp-fg-gen3/4 update every 1000 ms
    "qpnp,fg": 1000,
}

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

# "Constants" evaluated at runtime
for psy_node in POWER_SUPPLY_NODES:
    if os.path.exists(psy_node):
        POWER_SUPPLY = psy_node
        break

psy_name = os.readlink(POWER_SUPPLY)
for fg_string, interval in POWER_SAMPLE_FG_DEFAULT_INTERVALS.items():
    if fg_string in psy_name:
        POWER_SAMPLE_INTERVAL = interval
        break

if len(sys.argv) > 1:
    override_interval = int(sys.argv[1])
    if override_interval > 0:
        POWER_SAMPLE_INTERVAL = override_interval

# Calculate prealloc slots now that the interval is known
PREALLOC_SLOTS = int(PREALLOC_SECONDS / (POWER_SAMPLE_INTERVAL / 1000))

_stop_power_mon = False
_prealloc_samples = [-1] * PREALLOC_SLOTS
_power_samples = _prealloc_samples

def pr_debug(*args, **kwargs):
    if __debug__:
        kwargs["flush"] = True
        print(*args, **kwargs)

def run_cmd(args):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode == 0:
        return proc.stdout
    else:
        raise ValueError(f"Subprocess {args} failed with exit code {proc.returncode}:\n{proc.stdout}")

def sample_power():
    with open(f"{POWER_SUPPLY}/current_now", "r") as f:
        ma = int(f.read()) * CURRENT_FACTOR / 1000
    with open(f"{POWER_SUPPLY}/voltage_now", "r") as f:
        mv = int(f.read()) / 1000

    mw = ma * mv / 1000
    return ma, mv, abs(mw)

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
                pr_debug("Stopping power monitor due to global stop flag")
                break

            current, voltage, power = sample_power()
            pr_debug(f"Power: {power} mW\t(sample {count} from {current} mA * {voltage} mV)")

            try:
                sample_dest[count] = power
            except IndexError:
                pr_debug("Pre-allocated sample slots exhausted, falling back to dynamic allocation")
                # If out of pre-allocated slots
                sample_dest.append(power)

            count += 1

        if count < len(sample_dest):
            pr_debug(f"Truncating to first {count} samples from pre-allocated array")
            _power_samples = sample_dest[:count]

    pr_debug("Starting power monitor thread")
    thread = threading.Thread(target=_power_thread, daemon=True)
    thread.start()
    return thread

def stop_power_thread(thread):
    global _stop_power_mon

    pr_debug("Setting flag to stop power monitor")
    _stop_power_mon = True
    pr_debug("Waiting for power monitor to stop")
    thread.join()
    _stop_power_mon = False

    return _power_samples

def write_cpu(cpu, node, content):
    pr_debug(f"Writing CPU value: cpu{cpu}/{node} => {content}")
    with open(f"{SYS_CPU}/cpu{cpu}/{node}", "w") as f:
        f.write(content)

def read_cpu(cpu, node):
    with open(f"{SYS_CPU}/cpu{cpu}/{node}", "r") as f:
        content = f.read().strip()
        pr_debug(f"Reading CPU value: cpu{cpu}/{node} = {content}")
        return content

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

def init_cpus():
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

    return bench_cpus, cpu_count

def check_charging(node, charging_value, charging_warned):
    if os.path.exists(node):
        with open(node, "r") as f:
            psy_status = f.read().strip()
            pr_debug(f"Power supply status at {node}: {psy_status}")
            if psy_status == charging_value and not charging_warned:
                print()
                print("=============== WARNING ===============")
                print("Detected power supply in charging state!")
                print("Power measurements will be invalid and benchmark results may be affected.")
                print("Unplug the device and restart the benchmark for valid results.")
                print("=============== WARNING ===============")
                print()
                return True

    return charging_warned

def init_power():
    global CURRENT_FACTOR

    pr_debug(f"Using power supply: {POWER_SUPPLY}")

    charging_warned = False
    charging_warned = check_charging(f"{POWER_SUPPLY}/status", "Charging", charging_warned)
    charging_warned = check_charging(f"/sys/class/power_supply/battery/status", "Charging", charging_warned)
    charging_warned = check_charging(f"/sys/class/power_supply/usb/present", "1", charging_warned)
    charging_warned = check_charging(f"/sys/class/power_supply/dc/present", "1", charging_warned)

    # Some PMICs may give unstable readings at this point
    pr_debug("Waiting for power usage to settle for initial current measurement")
    time.sleep(5)
    # Maxim PMICs used on Exynos devices report current in mA, not µA
    with open(f"{POWER_SUPPLY}/current_now", "r") as f:
        # Assumption: will never be below 1 mA
        ref_current = int(f.read())
        if abs(ref_current) <= 1000:
            CURRENT_FACTOR = 1000
    pr_debug(f"Scaling current by {CURRENT_FACTOR}x (derived from initial sample: {ref_current})")

    print(f"Sampling power every {POWER_SAMPLE_INTERVAL} ms")
    pr_debug(f"Pre-allocated {PREALLOC_SLOTS} sample slots for {PREALLOC_SECONDS} seconds")
    pr_debug(f"Power sample interval adjusted for power supply: {psy_name}")
    print("Baseline power usage: ", end="", flush=True)
    pr_debug("Waiting for power usage to settle")
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

    return base_power, base_power_samples

def main():
    bench_start_time = time.time()

    print(BANNER)
    pr_debug("Running in debug mode")

    pr_debug("Initializing CPU states")
    bench_cpus, cpu_count = init_cpus()

    pr_debug("Initializing power measurements")
    base_power, base_power_samples = init_power()

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

        with open(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_boost_frequencies", "r") as f:
            raw_boost_freqs = f.read().replace("\n", "").split(" ")
            freqs.extend([int(freq) for freq in raw_boost_freqs if freq])

        # Some kernels may change the defaults
        pr_debug("Setting frequency limits")
        write_cpu(cpu, "cpufreq/scaling_min_freq", str(min(freqs)))
        write_cpu(cpu, "cpufreq/scaling_max_freq", str(max(freqs)))
        # Sometimes, reading back the limits immediately may give an incorrect result
        pr_debug("Waiting for frequency limits to take effect")
        time.sleep(1)

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

    pr_debug("Writing JSON results")
    results_json = json.dumps(data)
    pr_debug(results_json)
    with open("/tmp/results.json", "w+") as f:
        f.write(results_json)

    pr_debug("Writing CSV results")
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
