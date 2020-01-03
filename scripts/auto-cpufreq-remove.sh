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

echo -e "\n* Stopping auto-cpufreq systemd service"
systemctl stop auto-cpufreq

echo -e "\n* Disabling auto-cpufreq systemd service at boot"
systemctl disable auto-cpufreq

#if [ -f /lib/systemd/system/auto-cpufreq.service ];
#then
#	rm /lib/systemd/system/auto-cpufreq.service
#	systemctl daemon-reload

#if [ -f /etc/systemd/system/auto-cpufreq.service ];
#then
#	rm /etc/systemd/system/auto-cpufreq.service
#	systemctl daemon-reload

rm /lib/systemd/system/auto-cpufreq.service
rm /etc/systemd/system/auto-cpufreq.service

echo -e "\n* Reloading systemd manager configuration"
systemctl daemon-reload

echo -e "reset failed"
systemctl reset-failed

echo -e "\n* Removing auto-cpufreq daemon deploy script"
rm /usr/bin/auto-cpufreq-deploy

echo -e "\n* Removing auto-cpufreq daemon run script"
rm /usr/bin/auto-cpufreq-run

echo -e "\n* Removing auto-cpufreq binary"
rm /usr/bin/auto-cpufreq

echo -e "\n* Removing auto-cpufreq log file"
rm /var/log/auto-cpufreq.log

echo "kill any remaining instances"
pkill -f auto-cpufreq