#!/usr/bin/env python3

import json
import csv
import sys
import matplotlib.pyplot as plt

CPU_LABELS = {
    1: "Little",
    4: "Big",
    6: "Big",
    7: "Prime"
}

COL_LABELS = {
    "power_mean": "Power (mW)",
    "coremark_score": "Performance (iter/s)",
    "energy_joules": "Energy (J)",
    "energy_millijoules": "Energy (mJ)",
    "elapsed_sec": "Time (s)",
    "coremarks_per_mhz": "CoreMarks/MHz",
    "ulpmark_cm_score": "ULPMark-CM (iter/mJ)",
}

flags = set()
socs = {}
freq_load = "active"
col_name = None
for i, arg in enumerate(sys.argv[1:]):
    if ":" in arg:
        name, path = arg.split(":")
        with open(path, "r") as f:
            socs[name] = json.loads(f.read())
    elif "+" in arg:
        flag = arg[1:]
        flags.add(flag)
    elif "/" in arg:
        freq_load, col_name = arg.split("/")
    else:
        col_name = arg

col_label = COL_LABELS[col_name] if col_name in COL_LABELS else col_name
plt.ylabel(col_label)
plt.xlabel("Frequency (MHz)")
plt.title(col_label)

for soc_i, (soc, soc_data) in enumerate(socs.items()):
    cpus_data = soc_data["cpus"]
    for cpu, cpu_data in cpus_data.items():
        cpu = int(cpu)

        freqs = [int(freq) / 1000 for freq in cpu_data["freqs"].keys()]
        raw_values = [freq_data[freq_load][col_name] for freq_data in cpu_data["freqs"].values()]
        values = []
        for freq, freq_data in cpu_data["freqs"].items():
            if "minscl" in flags:
                curv = freq_data[freq_load][col_name]
                minv = min(raw_values)
                values.append(curv - minv)
            else:
                values.append(freq_data[freq_load][col_name])

        cpu_label = CPU_LABELS[cpu] if cpu in CPU_LABELS else f"CPU {cpu}"
        val_label = f"{soc} {cpu_label}"
        color = f"C{soc_i}"

        if "soccolor" in flags:
            plt.plot(freqs, values, color, label=val_label)
        else:
            plt.plot(freqs, values, label=val_label)

plt.legend()
plt.show()
