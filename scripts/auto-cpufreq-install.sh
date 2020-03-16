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