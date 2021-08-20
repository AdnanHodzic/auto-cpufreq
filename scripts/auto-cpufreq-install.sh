#!/bin/bash
#
# auto-cpufreq daemon install script
# reference: https://github.com/AdnanHodzic/auto-cpufreq

echo -e "\n------------------ Running auto-cpufreq daemon install script ------------------"

if [[ $EUID != 0 ]]; 
then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')\n"
	exit 1
fi


# Install script for runit
if [ -f /etc/os-release ] && eval "$(cat /etc/os-release)" && [[ $ID == "void"* ]]; then
    echo -e "\n* Deploy auto-cpufreq runit unit file"
    mkdir /etc/sv/auto-cpufreq
    cp /usr/local/share/auto-cpufreq/scripts/run /etc/sv/auto-cpufreq
    chmod +x /etc/sv/auto-cpufreq/run

    echo -e "\n* Creating symbolic link (/var/service/auto-cpufreq -> /etc/sv/auto-cpufreq)"
    ln -s /etc/sv/auto-cpufreq /var/service

    echo -e "\n* Stopping auto-cpufreq daemon (runit) service"
    sv stop auto-cpufreq

    echo -e "\n* Starting auto-cpufreq daemon (runit) service"
    sv start auto-cpufreq
    sv up auto-cpufreq


# Install script for systemd
else
    echo -e "\n* Deploy auto-cpufreq systemd unit file"
    cp /usr/local/share/auto-cpufreq/scripts/auto-cpufreq.service /etc/systemd/system/auto-cpufreq.service

    echo -e "\n* Reloading systemd manager configuration"
    systemctl daemon-reload

    echo -e "\n* Stopping auto-cpufreq daemon (systemd) service"
    systemctl stop auto-cpufreq

    echo -e "\n* Starting auto-cpufreq daemon (systemd) service"
    systemctl start auto-cpufreq

    echo -e "\n* Enabling auto-cpufreq daemon (systemd) service at boot"
    systemctl enable auto-cpufreq
fi
