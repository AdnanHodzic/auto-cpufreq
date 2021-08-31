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

# First argument is the "sv" path, second argument is the "service" path this
# only exist because the path between distros may vary
runit_ln() {
	echo -e "\n* Deploy auto-cpufreq runit unit file"
	mkdir "$1"/sv/auto-cpufreq
	cp /usr/local/share/auto-cpufreq/scripts/run "$1"/sv/auto-cpufreq
	chmod +x "$1"/sv/auto-cpufreq/run

	echo -e "\n* Creating symbolic link ($2/service/auto-cpufreq -> $1/sv/auto-cpufreq)"
	ln -s "$1"/sv/auto-cpufreq "$2"/service
}

# sv commands
sv_cmd() {
	echo -e "\n* Stopping auto-cpufreq daemon (runit) service"
	sv stop auto-cpufreq
	echo -e "\n* Starting auto-cpufreq daemon (runit) service"
	sv start auto-cpufreq
	sv up auto-cpufreq
}

# Installation for runit, we still look for the distro because of the path may
# vary.
if [ "$(ps h -o comm 1)" = "runit" ];then
	if [ -f /etc/os-release ];then
		eval "$(cat /etc/os-release)"
		separator
		case $ID in
			void)
				runit_ln /etc /var
				sv_cmd
			;;
			artix)
			# Note: Artix supports other inits than runnit
				runit_ln /etc/runit /run/runit
				sv_cmd
			;;
			*)
				echo -e "\n* Runit init detected but your distro is not supported\n"
				echo -e "\n* Please open an issue on https://github.com/AdnanHodzic/auto-cpufreq\n"

		esac
	fi
# Install script for systemd
else
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
fi
