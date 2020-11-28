#!/usr/bin/env python3

import json
import csv
import sys

with open(sys.argv[1], "r") as f:
    json_data = json.loads(f.read())

col_name = sys.argv[2]
cpus_data = json_data["cpus"]

with open(sys.argv[3], "w+") as f:
    fields = [
        "Frequency (kHz)",
        *[f"CPU {cpu} {col_name}" for cpu in cpus_data.keys()]
    ]

    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    freqs = []

    for cpu, cpu_data in cpus_data.items():
        freqs += cpu_data["freqs"].keys()

    freqs.sort(reverse=True)
    for freq in freqs:
        row = {
            "Frequency (kHz)": freq
        }

        for cpu, cpu_data in cpus_data.items():
            if freq in cpu_data["freqs"]:
                row[f"CPU {cpu} {col_name}"] = str(cpu_data["freqs"][freq]["active"][col_name])
            else:
                row[f"CPU {cpu} {col_name}"] = ""

        writer.writerow(row)
