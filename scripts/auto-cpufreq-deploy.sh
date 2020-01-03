#!/usr/bin/env bash
#
# auto-cpufreq daemon deploy script
# reference: https://github.com/AdnanHodzic/auto-cpufreq

echo -e "\n------------------ Running auto-cpufreq daemon deploy script ------------------"

if [[ $EUID != 0 ]]; 
then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')\n"
	exit 1
fi

#touch /var/log/auto-cpufreq.log

echo -e "\n* Reloading systemd manager configuration"
systemctl daemon-reload

echo -e "\n* Stopping auto-cpufreq systemd service"
systemctl stop auto-cpufreq

echo -e "\n* Starting auto-cpufreq systemd service"
systemctl start auto-cpufreq

#echo -e "\n* Enabling auto-cpufreq systemd service at boot"
#systemctl enable auto-cpufreq

#echo -e "\n* Running auto-cpufreq binary"
#/usr/bin/python3 /usr/bin/auto-cpufreq --live > $logs_file 2>&1 &

echo -e "\n------\n"