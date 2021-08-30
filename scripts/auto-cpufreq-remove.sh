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


if [ -f /etc/os-release ] && eval "$(cat /etc/os-release)" && [[ $ID == "void"* ]]; then
    echo -e "\n* Stopping auto-cpufreq daemon (runit) service"
    sv stop auto-cpufreq

    echo -e "\n* Removing auto-cpufreq daemon (runit) unit files"
    rm -rf /etc/sv/auto-cpufreq
    rm -rf /var/service/auto-cpufreq
elif [ -f /etc/os-release ] && eval "$(cat /etc/os-release)" && [[ $ID == "artix"* ]]; then
    echo -e "\n* Stopping auto-cpufreq daemon (runit) service"
    sv stop auto-cpufreq

    echo -e "\n* Removing auto-cpufreq daemon (runit) unit files"
    rm -rf /etc/runit/sv/auto-cpufreq
    rm -rf /run/runit/service/auto-cpufreq
else
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
fi
