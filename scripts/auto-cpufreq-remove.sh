#!/usr/bin/env bash
#
# auto-cpufreq daemon removal script
# reference: https://github.com/AdnanHodzic/auto-cpufreq

echo -e "\n------------------ Running auto-cpufreq daemon removal script ------------------"

if [[ $EUID != 0 ]]; then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')\n"
	exit 1
fi

echo -e "\n* Stopping auto-cpufreq daemon (openrc) service"
rc-service auto-cpufreq stop

echo -e "\n* Disabling auto-cpufreq daemon (openrc) at boot"
rc-update del auto-cpufreq

echo -e "\n* Removing auto-cpufreq daemon (openrc) unit file"
rm /etc/init.d/auto-cpufreq
