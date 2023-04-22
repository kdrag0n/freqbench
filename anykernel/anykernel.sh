# AnyKernel3 Ramdisk Mod Script
# osm0sis @ xda-developers

## AnyKernel setup
# begin properties
properties() { '
kernel.string=freqbench - CPU benchmark by kdrag0n
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
supported.versions=
supported.patchlevels=
'; } # end properties

# shell variables
block=auto;
is_slot_device=auto;
ramdisk_compression=auto;


## AnyKernel methods (DO NOT CHANGE)
# import patching functions/variables - see for reference
. tools/ak3-core.sh;


## AnyKernel install
split_boot;

cores=$(grep '^processor' /proc/cpuinfo | wc -l)
all_cpus=0-$((cores - 1))
bench_cpus=1-$((cores - 1))
patch_cmdline rcu_nocbs rcu_nocbs=$all_cpus
patch_cmdline isolcpus isolcpus=$bench_cpus
patch_cmdline nohz_full nohz_full=$bench_cpus
patch_cmdline loglevel loglevel=0
patch_cmdline printk.devkmsg printk.devkmsg=on
patch_cmdline skip_initramfs ""

mv $home/rd-new.cpio.gz $home/ramdisk-new.cpio

flash_boot;
## end install

