#!/usr/bin/env python3

import json
import sys

with open(sys.argv[1], "r") as f:
    json_data = json.loads(f.read())

cpus_data = json_data["cpus"]
for cpu, cpu_data in cpus_data.items():
    cpu = int(cpu)
    print(f"cpu{cpu}:")

    eff_freqs = set()

    # Start with the most efficient freq
    freqs = cpu_data["freqs"]
    max_eff_freq, max_eff = max(
        ((int(freq), freq_data["active"]["ulpmark_cm_score"]) for freq, freq_data in freqs.items()),
        key=lambda opp: opp[1]
    )
    print((max_eff_freq, max_eff))
    eff_freqs.add(max_eff_freq)

    # Add the max freq
    max_freq = max(int(freq) for freq in freqs.keys())
    max_freq_eff = freqs[str(max_freq)]["active"]["ulpmark_cm_score"]
    eff_freqs.add(max_freq)

    # Add efficient intermediate freqs
    last_freq = max_eff_freq
    freq_keys = list(map(int, freqs.keys()))
    for freq_i, (freq, freq_data) in enumerate(freqs.items()):
        freq = int(freq)
        eff = freq_data["active"]["ulpmark_cm_score"]

        # Clock compensation: if 500 MHz passed with no freq step
        if freq - last_freq < 500000:
            # Ignore freqs slower than most efficient
            if freq < max_eff_freq:
                continue

            # Less efficient than max freq
            if eff < max_freq_eff:
                continue

            # Less efficient than next freq
            #next_freq = freq_keys[min(freq_keys.index(freq) + 1, len(freqs) - 1)]
            #if freqs[str(next_freq)]["active"]["ulpmark_cm_score"] >= eff:
            #    continue

        last_freq = freq
        eff_freqs.add(freq)
        print(freq)

    # Remove inefficient freqs
    ineff_freqs = freqs.keys() - eff_freqs
    for freq in ineff_freqs:
        del freqs[str(freq)]

    print()

with open(sys.argv[2], "w+") as f:
    f.write(json.dumps(json_data))
