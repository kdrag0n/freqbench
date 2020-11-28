#!/usr/bin/env python3

import json
import csv
import sys

with open(sys.argv[1], "r") as f:
    json_data = json.loads(f.read())

cpus_data = json_data["cpus"]

with open(sys.argv[2], "w+") as f:
    fields = [
        "CPU",
        "Frequency (kHz)",
        "Power (mW)",
        "Energy (J)"
    ]

    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for cpu, cpu_data in cpus_data.items():
        for freq, freq_data in cpu_data["freqs"].items():
            freq_data = freq_data["idle"]

            writer.writerow({
                "CPU": cpu,
                "Frequency (kHz)": freq,
                "Power (mW)": freq_data["power_mean"],
                "Energy (J)": freq_data["energy_joules"],
            })
