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

echo -e "\n* Reloading systemd manager configuration"
systemctl daemon-reload

echo -e "\n* Stopping auto-cpufreq daemon (systemd) service"
systemctl stop auto-cpufreq

echo -e "\n* Starting auto-cpufreq daemon (systemd) service"
systemctl start auto-cpufreq

echo -e "\n* Enabling auto-cpufreq daemon (systemd) service at boot"
systemctl enable auto-cpufreq

echo -e "\n------------------ auto-cpufreq daemon installed and running -----------------\n"

echo -e "To view live log, run:\nauto-cpufreq --log"
echo -e "\nTo disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove"

echo -e "\n-------------------------------------------------------------------------------\n"