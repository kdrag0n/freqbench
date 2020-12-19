# Commonly-used config options for freqbench

# Should usually stay the same
# Note that this is NOT like Android where everything is in /dev/block
# For eMMC devices: /dev/mmcblk0
BLOCK_DEV=/dev/sda

# Whether to enable verbose debug logging during the benchmark
# DO NOT ENABLE for final benchmarking!
# The extra framebuffer memory copies caused by it will influence results.
DEBUG=false

# How often to sample power usage while benchmarking (in milliseconds)
# 0 = auto (default is based on fuel gauge)
POWER_SAMPLE_INTERVAL=0
