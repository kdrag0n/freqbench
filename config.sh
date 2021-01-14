# Common config options for freqbench

# Whether to enable verbose debug logging during the benchmark
# DO NOT ENABLE for final benchmarking!
# The extra framebuffer memory copies caused by it will influence results.
DEBUG=false

# How often to sample power usage while benchmarking (in milliseconds)
# 0 = auto (default is based on fuel gauge)
POWER_SAMPLE_INTERVAL=0

# Whether to expose an SSH server for debugging over virtual USB Ethernet
# Do not enable for final benchmarking
USB_DEBUG=false
