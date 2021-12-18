#!/bin/bash
#
# auto-cpufreq daemon install script
# reference: https://github.com/AdnanHodzic/auto-cpufreq
dir=`pwd`
echo -e "\n------------------ Running auto-cpufreq daemon install script ------------------"

if [[ $EUID != 0 ]];
then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')\n"
	exit 1
fi

echo -e "\n* Deploying auto-cpufreq openrc unit file"
cp /usr/local/share/auto-cpufreq/scripts/auto-cpufreq /etc/init.d/auto-cpufreq
chmod +x /etc/init.d/auto-cpufreq

echo -e "Starting auto-cpufreq daemon (openrc) service"
rc-service auto-cpufreq start

echo -e "\n* Enabling auto-cpufreq daemon (openrc) service at boot"
rc-update add auto-cpufreq
