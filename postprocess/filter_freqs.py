#!/usr/bin/env python3

import json
import sys

with open(sys.argv[1], "r") as f:
    json_data = json.loads(f.read())

allowed_opps = set(tuple(int(v) for v in opp.split(".")) for opp in sys.argv[3:])
cpus_data = json_data["cpus"]
for cpu, cpu_data in cpus_data.items():
    cpu = int(cpu)
    freqs = cpu_data["freqs"]

    remove_freqs = freqs.keys() - set(str(freq) for opp_cpu, freq in allowed_opps if opp_cpu == cpu)
    for freq in remove_freqs:
        del freqs[str(freq)]

with open(sys.argv[2], "w+") as f:
    f.write(json.dumps(json_data))
