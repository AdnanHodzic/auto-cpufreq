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

echo -e "\n* Stopping auto-cpufreq daemon (systemd) service"
systemctl stop auto-cpufreq

echo -e "\n* Disabling auto-cpufreq daemon (systemd) at boot"
systemctl disable auto-cpufreq

echo -e "\n* Removing auto-cpufreq daemon (systemd) unit file"
rm /etc/systemd/system/auto-cpufreq.service

echo -e "\n* Reloading systemd manager configuration"
systemctl daemon-reload

echo -e "reset failed"
systemctl reset-failed

echo -e "\n* Removing auto-cpufreq daemon install script"
rm /usr/bin/auto-cpufreq-install

echo -e "\n* Removing auto-cpufreq binary"
rm /usr/bin/auto-cpufreq

echo -e "\n* Removing auto-cpufreq log file"
rm /var/log/auto-cpufreq.log

echo -e "\n-------------------------------------------------------------------------------\n"
