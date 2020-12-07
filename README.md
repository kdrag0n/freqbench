# freqbench

freqbench is a comprehensive CPU benchmark that benchmarks each CPU frequency step on each frequency scaling domain (e.g. ARM DynamIQ/big.LITTLE cluster). It is based on a minimal Alpine Linux userspace with the [EEMBC CoreMark](https://www.eembc.org/coremark/) workload and a Python benchmark coordinator.

## Usage

Set the following kernel config options:

```bash
CONFIG_NO_HZ_FULL=y
CONFIG_CPU_FREQ_TIMES=n  # may not exist
CONFIG_CPU_FREQ_GOV_POWERSAVE=y
CONFIG_CPU_FREQ_GOV_USERSPACE=y
CONFIG_DEVTMPFS=y
```

If you have any commits that prevent userspace from controlling CPU affinities and utilization, frequencies, or anything of the sort, revert them for the benchmark to work properly. Here are some common examples of such commits in downstream kernels and their corresponding reverts:

- [Performance-critical IRQs and kthreads](https://github.com/kdrag0n/proton_kernel_wahoo/commit/29b315cd5f3a6)
- [Existing efficient frequency tables](https://github.com/kdrag0n/proton_kernel_wahoo/commit/9b98ee3fabd14)
- [Preventing userspace from setting minimum CPU frequencies](https://github.com/kdrag0n/proton_kernel_wahoo/commit/d9d2fe54e87f9)

Compile and flash your new kernel. Note that Android will not work properly on this kernel, so make sure you take a backup of your old boot image to restore later.

Adjust the config parameters in `bench.py` as appropriate for your device. Run `pack-zip.sh` and flash `freqbench-installer.zip`.

Unplug the device immediately, before the device starts booting. Do not try to wait for it to finish booting. Leaving the device plugged in will invalidate all power results.

Finally, wait until the device reboots itself and then retrieve the results from `/persist/freqbench`. Do not touch the device, any of its buttons, or plug/unplug it during the test. It will be frozen on the bootloader splash screen; do not assume that it is broken. The benchmark is expected to take a long time; 1 hour is reasonable for a slower CPU.

**If you have any problems, check the troubleshooting section before opening an issue!**

### Manual boot image creation

Manually creating a new boot image with the kernel and ramdisk is only for advanced users. Use the AnyKernel3 installer unless you have good reason to do this.

Additional kernel config options:

```bash
CONFIG_CMDLINE="isolcpus=1-7 nohz_full=1-7 loglevel=0"
CONFIG_CMDLINE_EXTEND=y
```

If you do not have 8 CPU cores, adjust `1-7` to `1-<core count - 1>`. Single-core CPUs are not supported.

Create a boot image with your modified kernel and the freqbench ramdisk:

For boot image v0/v1 devices:

```bash
cd boot-v1
./unpack.sh path/to/normal/boot.img
./pack.sh
# New boot image will be created as new.img
```

For boot image v3 devices:

```bash
# Extract values from boot.img and update pack-img.sh accordingly
./pack-img.sh
# New boot image will be created as bench.img
```

After that, boot the modified image with `fastboot boot` if your device supports it, or flash it to the boot/recovery partition and boot that manually.

## Results

After the benchmark finishes, results can be found in `/persist/freqbench`, or `/mnt/vendor/persist/freqbench` on some devices. Human-readable results, raw machine-readable JSON data, and diagnostic information are included for analysis.

## Post-processing

Several post-processing scripts, all written in Python and many using `matplotlib`, are available:

### Legacy energy model

Create a legacy EAS energy model for use with older kernels.

Example usage: `./legacy_em.py results.json`

### Simplified energy model

Create a simplified EAS energy model for use with newer kernels.

Because voltages defined by the CPU frequency scaling driver cannot easily be accessed from userspace, you will need to provide them. Each frequency step for each cluster have its voltage specified as an argument: `cpu#.khz=microvolts`

Example usage: `./simplified_em.py results.json 1.300000=580000 1.576000=580000 1.614400=580000 1.864000=644000 1.1075200=708000 1.1363200=788000 1.1516800=860000 1.1651200=888000 1.1804800=968000 6.652800=624000 6.940800=672000 6.1152000=704000 6.1478400=752000 6.1728000=820000 6.1900800=864000 6.2092800=916000 6.2208000=948000 7.806400=564000 7.1094400=624000 7.1401600=696000 7.1766400=776000 7.1996800=836000 7.2188800=888000 7.2304000=916000 7.2400000=940000`

### Efficient frequencies (experimental)

Derive a list of efficient frequencies for each cluster and create a new results.json with only those frequencies included.

Note that this script is **experimental** and may not produce optimal results. Manual tuning of the resulting frequency tables is recommended.

Example usage: `./efficient_freqs.py results.json`

### Cross-CPU cluster graph

![Performance (iter/s) across 835, 855, and 765G](https://user-images.githubusercontent.com/7930239/101309012-19446400-3800-11eb-8418-bb9293b08871.png)

Graph a value for each cluster across different SoCs/CPUs.

Arguments:

- Add a SoC: `SoC-1:soc1/results.json`
- Specify the value to graph: `load/value` (load is idle/active)
- Set a flag: `+flagname` (soccolor, minscl)

Example usage: `./cross_cpu_cluster_graph.py 835:results/p2/main/results.json 855:results/zf6/main/results.json 855+:results/rog2/main/results.json 765G:results/p5/new-final/results.json active/power_mean +soccolor +minscl`

### Unified cluster graph

![Performance (iter/s) across 765G little, big, and prime clusters](https://user-images.githubusercontent.com/7930239/101309506-712f9a80-3801-11eb-9ae6-8dba84f063d4.png)

Graph a value for each cluster within the same SoC/CPU.

Example usage: `./unified_cluster_graph.py results.json coremark_score`

### Unified cluster column

Extract a value for each cluster within the same SoC/CPU and write the results into a CSV file.

Example usage: `./unified_cluster_csv.py results.json coremark_score cm_scores.csv`

## Troubleshooting

### Kernel panics on boot

If your kernel panics on boot, disable `CONFIG_CPU_FREQ_STAT`. If that causes the kernel to fail to compile, cherry-pick [cpufreq: Fix build with stats disabled](https://github.com/kdrag0n/proton_kernel_wahoo/commit/21e76d090e092).

### Results vary too much

Check kernel.log, pre- and post-bench interrupts, running processes, and cpufreq stats from the results directory to diagnose the issue.

### It's still running after an hour

If you have a slow CPU with a lot of frequency steps, this is not entirely unreasonable.
