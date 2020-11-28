#include <sys/syscall.h>
#include <sys/reboot.h>
#include <unistd.h>
#include <linux/reboot.h>

int main(int argc, char **argv) {
    syscall(__NR_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, argv[1]);
    return 0;
}
