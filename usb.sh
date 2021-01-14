#!/bin/sh

# DEPENDENCIES: dropbear dhcp

# Mount USB and pty (SSH terminal) pseudo-filesystems
mount -t configfs configfs /sys/kernel/config
mkdir /dev/pts
mount -t devpts devpts /dev/pts

# For SSH shell
hostname phone

# USB (reference: Halium initrd)
LOCAL_IP=10.15.19.82
gadget=/sys/kernel/config/usb_gadget/g1
strings=$gadget/strings/0x409
func_config=$gadget/configs/c.1/strings/0x409
mkdir -p $strings
mkdir -p $func_config
# Generic "Google Android" (fastboot) VID:PID
echo -n 0x0b05 > $gadget/idVendor
echo -n 0x4daf > $gadget/idProduct
# Product strings
echo -n "Linux" > $strings/manufacturer
echo -n "Alpine GNU/Linux" > $strings/product
echo -n "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$LOCAL_IP" > $strings/serialnumber
# RNDIS
mkdir $gadget/functions/rndis.usb0
echo -n rndis > $func_config/configuration
ln -s $gadget/functions/rndis.usb0 $gadget/configs/c.1/
echo -n "$(ls -1 /sys/class/udc | head -1)" > $gadget/UDC

# Basic network and services
ip link set lo up
ifconfig usb0 $LOCAL_IP netmask 255.255.255.0
dropbear -RBFE &

# DHCP
mkdir /tmp/usb
touch /tmp/usb/dhcpd4.leases
INTERFACES=usb0 dhcpd -4 -f -cf /dhcpd.conf -pf /tmp/usb/dhcpd4.pid -lf /tmp/usb/dhcpd4.leases &
echo "SSH server running at $LOCAL_IP"

set +v
