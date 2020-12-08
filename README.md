# freqbench

![Power usage in mW per frequency per cluster for Qualcomm Snapdragon 835, 855, and 765G](https://user-images.githubusercontent.com/7930239/101429518-fb3a3a80-38b7-11eb-8005-5edf2d12a4d6.png)

freqbench is a comprehensive CPU benchmark that benchmarks each CPU frequency step on each frequency scaling domain (e.g. ARM DynamIQ/big.LITTLE cluster). It is based on a minimal Alpine Linux userspace with the [EEMBC CoreMark](https://www.eembc.org/coremark/) workload and a Python benchmark coordinator.

Results include:

- Performance (CoreMark scores)
- Performance efficiency (CoreMarks per MHz)
- Power usage (in milliwatts)
- Energy usage (in millijoules and joules)
- Energy efficiency (ULPMark-CM scores: iterations per second per millijoule of energy used)
- Baseline power usage
- Time elapsed
- CPU frequency scaling stats during the benchmark (for validation)
- Diagnostic data (logs, kernel version, kernel command line, interrupts, processes)
- Raw power samples in machine-readable JSON format (for postprocessing)

## Why?

A benchmark like this can be useful for many reasons:

- Creating energy models for EAS (Energy-Aware Scheduling)
- Correcting inaccurate EAS energy models
- Analyzing performance and power trends
- Comparing efficiency across SoC and CPU generations
- Improving performance and battery life of mobile devices by utilizing the race-to-idle phenomenon with efficient frequencies

## Usage

Set the following kernel config options:

```bash
CONFIG_NO_HZ_FULL=y
CONFIG_CPU_FREQ_TIMES=n  # may not exist
CONFIG_CPU_FREQ_GOV_POWERSAVE=y
CONFIG_CPU_FREQ_GOV_USERSPACE=y
CONFIG_DEVTMPFS=y
CONFIG_HZ_100=y
```

Example commit: [kirin_defconfig: Configure for freqbench](https://github.com/kdrag0n/proton_zf6/commit/d5e931add54ad)

If you have any commits that prevent userspace from controlling CPU affinities and utilization, frequencies, or anything of the sort, revert them for the benchmark to work properly. Here are some common examples of such commits in downstream kernels and their corresponding reverts:

- [Performance-critical IRQs and kthreads](https://github.com/kdrag0n/proton_kernel_wahoo/commit/29b315cd5f3a6)
- [Existing efficient frequency tables](https://github.com/kdrag0n/proton_kernel_wahoo/commit/9b98ee3fabd14)
- [Preventing userspace from setting minimum CPU frequencies](https://github.com/kdrag0n/proton_kernel_wahoo/commit/d9d2fe54e87f9)
- [Ratelimiting fuel gauge queries](https://github.com/kdrag0n/proton_kernel_wahoo/commit/87ac3f89c7392)

Example freqbench kernel adaptations:

- [Pixel 2, msm-4.4](https://github.com/kdrag0n/proton_kernel_wahoo/commits/alpine-fbench)
- [ZenFone 6, msm-4.14](https://github.com/kdrag0n/proton_zf6/commits/alpine-fbench-basic-example)
- [Pixel 5, msm-4.19](https://github.com/kdrag0n/proton_kernel_redbull/commits/alpine-fbench-basic-example) (this device uses boot image v3, so it follows the manual boot image guide below)

Compile and flash your new kernel. Note that Android will not work properly on this kernel, so make sure you take a backup of your old boot image to restore later.

If necessary, adjust the config parameters in `config.sh`. Most modern devices will not need any changes. Run `pack-zip.sh` and flash `freqbench-installer.zip`.

Unplug the device immediately, before the device starts booting. Do not try to wait for it to finish booting. Leaving the device plugged in will invalidate all power results.

Finally, wait until the device reboots itself. Do not touch the device, any of its buttons, or plug/unplug it during the test. It will be frozen on the bootloader splash screen; do not assume that it is broken. The benchmark is expected to take a long time; 1 hour is reasonable for a slower CPU.

Once the benchmark is done, retrieve the results from `/cache/freqbench` if your device has a cache partition, or `/persist/freqbench` otherwise (newer devices with A/B partitions don't have a cache partition).

**If you have any problems, check the troubleshooting section before opening an issue!**

### Manual boot image creation

Manually creating a new boot image with the kernel and ramdisk is only for advanced users. Use the AnyKernel3 installer unless you have good reason to do this.

Additional kernel config options:

```bash
CONFIG_CMDLINE="isolcpus=1-7 nohz_full=1-7 loglevel=0 printk.devkmsg=on"
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

After the benchmark finishes, results can be found in `/cache/freqbench`, `/persist/freqbench`, or `/mnt/vendor/persist/freqbench`, in that order of preference. The first path that exists on your device will be used. Human-readable results, raw machine-readable JSON data, and diagnostic information are included for analysis.

## Post-processing

Several post-processing scripts, all written in Python and many using `matplotlib`, are available:

### Legacy energy model

Create a legacy EAS energy model for use with older kernels.

Optional argument after path to results: `key_type/value_type`

Key types:

- Frequency (default) - looks like `652800` or `2323200`
- Capacity - looks like `139` or `1024`

You must use the correct key type for your kernel. When in doubt, refer to your original energy model and check which one the numbers look more like.

Value types:

- Power (default)
- Energy (experimental)

Do not change the value type unless you know what you're doing.

Example usage: `./legacy_em.py results.json cap/power`

### Simplified energy model

Create a simplified EAS energy model for use with newer kernels.

Because voltages defined by the CPU frequency scaling driver cannot easily be accessed from userspace, you will need to provide them. Each frequency step for each cluster have its voltage specified as an argument: `cpu#.khz=microvolts`

For Qualcomm SoCs on the msm-4.19 kernel, voltages can be obtained by booting the kernel (with or without freqbench doesn't matter, as long as you can get kernel logs) with [this commit](https://github.com/kdrag0n/proton_kernel_redbull/commit/8db0557716a4) and searching for lines containing `volt=` in the kernel log.

For msm-4.9 and msm-4.14, the process is the same but with [this commit](https://github.com/kdrag0n/proton_zf6/commit/f7cc2d654f1b9) and searching for `open_loop_voltage` instead.

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

### I want to debug it while it's running

freqbench offers interactive debugging via SSH over virtual USB Ethernet; the device acts as a USB Ethernet adapter and exposes an SSH server on the internal network. Uncomment `source /usb.sh` in init.sh to enable it and boot freqbench again. The feature is disabled by default to avoid unnecessary USB setup that may influence benchmark results, so keeping it enabled for a final benchmark run is not recommended.

Connect your device to a computer over USB. You should see something like this in your kernel logs if you are running Linux:

```log
[7064379.627645] usb 7-3: new high-speed USB device number 114 using xhci_hcd
[7064379.772208] usb 7-3: New USB device found, idVendor=0b05, idProduct=4daf, bcdDevice= 4.14
[7064379.772210] usb 7-3: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[7064379.772211] usb 7-3: Product: Alpine GNU/Linux
[7064379.772211] usb 7-3: Manufacturer: Linux
[7064379.772212] usb 7-3: SerialNumber: ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@10.15.19.82
[7064379.818904] rndis_host 7-3:1.0 usb0: register 'rndis_host' at usb-0000:47:00.1-3, RNDIS device, da:34:ab:99:c5:81
[7064379.870018] rndis_host 7-3:1.0 enp71s0f1u3: renamed from usb0
```

Run the SSH command in the serial number field to open a shell to the device. The password is empty, so just press enter when asked to input a password.
