#!/usr/bin/env python3

import sys
import matplotlib.pyplot as plt
import re
import collections

CPU_LABELS = {
    1: "Little",
    4: "Big",
    6: "Big",
    7: "Prime"
}

flags = set()
socs = {}
freq_load = "active"
col_name = None
for i, arg in enumerate(sys.argv[1:]):
    if ":" in arg:
        name, path = arg.split(":")
        with open(path, "r") as f:
            socs[name] = [[int(v) for v in re.split(r"[\.=]", opp)] for opp in f.read().strip().split(" ")]
    elif "+" in arg:
        flag = arg[1:]
        flags.add(flag)

plt.ylabel("Voltage (mV)")
plt.xlabel("Frequency (MHz)")
plt.title("CPU Voltages")

for soc_i, (soc, soc_data) in enumerate(socs.items()):
    cpu_freqs = collections.defaultdict(list)
    cpu_volts = collections.defaultdict(list)

    for cpu, freq, volt in soc_data:
        freq /= 1000
        volt /= 1000

        cpu_freqs[cpu].append(freq)
        cpu_volts[cpu].append(volt)

    for cpu, freqs in cpu_freqs.items():
        volts = cpu_volts[cpu]

        cpu_label = CPU_LABELS[cpu] if cpu in CPU_LABELS else f"CPU {cpu}"
        val_label = f"{soc} {cpu_label}"
        color = f"C{soc_i}"

        if "soccolor" in flags:
            plt.plot(freqs, volts, color, label=val_label)
        else:
            plt.plot(freqs, volts, label=val_label)

plt.legend()
plt.show()
