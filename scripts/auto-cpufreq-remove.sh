#!/usr/bin/env bash
#
# auto-cpufreq daemon removal script
# reference: https://github.com/AdnanHodzic/auto-cpufreq

echo -e "\n------------------ Running auto-cpufreq daemon removal script ------------------"

if [[ $EUID != 0 ]]; 
then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')\n"
	exit 1
fi

logs_file="/var/log/auto-cpufreq.log"

echo -e "\n* Disabling auto-cpufreq systemd service at boot"
systemctl disable auto-cpufreq

echo -e "\n* Stopping auto-cpufreq systemd service"
systemctl stop auto-cpufreq

echo -e "\n* Reloading systemd manager configuration"
systemctl daemon-reload