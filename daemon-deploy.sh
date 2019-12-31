#!/usr/bin/env bash
#
# auto-cpufreq daemon script
# reference: https://github.com/AdnanHodzic/auto-cpufreq

if (( $EUID != 0 )); 
then
	echo -e "\nERROR\nMust be run as root (i.e: 'sudo $0')."
	exit 1
fi

logs_file="/var/log/auto-cpufreq.log"

python3 auto-cpufreq.py --live > $logs_file 2>&1 &

echo -e "\n------------------------ auto-cpufreq -----------------------------\n"
echo -e "auto-cpufreq daemon started and running in background."
echo -e "\nLogs are available in:\n$logs_file"
echo -e "\nView live logs by running i.e: \ntail -n 50 -f $logs_file"
echo -e "\n-------------------------------------------------------------------\n"
