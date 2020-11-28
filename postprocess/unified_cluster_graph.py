#!/usr/bin/env python3

import json
import csv
import sys
import matplotlib.pyplot as plt

with open(sys.argv[1], "r") as f:
    json_data = json.loads(f.read())

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

col_name = sys.argv[2]
cpus_data = json_data["cpus"]

col_label = COL_LABELS[col_name] if col_name in COL_LABELS else col_name
plt.ylabel(col_label)
plt.xlabel("Frequency (MHz)")
if len(sys.argv) > 3:
    plt.title(sys.argv[3])
else:
    plt.title(col_label)

for cpu, cpu_data in cpus_data.items():
    cpu = int(cpu)

    freqs = [int(freq) / 1000 for freq in cpu_data["freqs"].keys()]
    values = [freq_data["active"][col_name] for freq_data in cpu_data["freqs"].values()]
    cpu_label = CPU_LABELS[cpu] if cpu in CPU_LABELS else f"CPU {cpu}"

    plt.plot(freqs, values, label=cpu_label)

plt.legend()
plt.show()
