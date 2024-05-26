#!/usr/bin/env bash
#
# auto-cpufreq daemon removal script
# reference: https://github.com/AdnanHodzic/auto-cpufreq
# Thanks to https://github.com/errornonamer for openrc fix

MID="$((`tput cols` / 2))"
function header {
  echo
	printf "%0.s─" $(seq $((MID-(${#1}/2)-2)))
	printf " $1 "
	printf "%0.s─" $(seq $((MID-(${#1}/2)-2)))
	echo
}
header "Running auto-cpufreq daemon removal script"

# root check
if ((EUID != 0)); then
  echo; echo "Must be run as root (i.e: 'sudo $0')."; echo
  exit 1
fi

# First argument is the init name, second argument is the stop command, third argument is the disable command and the fourth is the "service" path
function auto_cpufreq_remove {
  echo -e "\n* Stopping auto-cpufreq daemon ($1) service"
  $2
  echo -e "\n* Disabling auto-cpufreq daemon ($1) at boot"
  $3
  echo -e "\n* Removing auto-cpufreq daemon ($1) unit file"
  rm $4
}

case "$(ps h -o comm 1)" in
  dinit) auto_cpufreq_remove "dinit" "dinitctl stop auto-cpufreq" "dinitctl disable auto-cpufreq" "/etc/dinit.d/auto-cpufreq";;
  init) auto_cpufreq_remove "openrc" "rc-service auto-cpufreq stop" "rc-update del auto-cpufreq" "/etc/init.d/auto-cpufreq";;
  runit)
    # First argument is the "sv" path, second argument is the "service" path
    rm_sv() {
      auto_cpufreq_remove "runit" "sv stop auto-cpufreq" "" "-rf $1/sv/auto-cpufreq $2/service/auto-cpufreq"
    }

    if [ -f /etc/os-release ]; then
      . /etc/os-release
      case $ID in
        void) rm_sv /etc /var;;
        artix) rm_sv /etc/runit /run/runit;;
        *)
          echo -e "\n* Runit init detected but your distro is not supported\n"
          echo -e "\n* Please open an issue on https://github.com/AdnanHodzic/auto-cpufreq\n"
        ;;
      esac
    fi
  ;;
  systemd)
    auto_cpufreq_remove "systemd" "systemctl stop auto-cpufreq" "systemctl disable auto-cpufreq" "/etc/systemd/system/auto-cpufreq.service"

    echo -e "\n* Reloading systemd manager configuration"
    systemctl daemon-reload

    echo "reset failed"
    systemctl reset-failed
  ;;
  s6-svscan)
    auto_cpufreq_remove "s6" "" "s6-service delete default auto-cpufreq" "-rf /etc/s6/sv/auto-cpufreq"
    
    echo -e "\n* Update daemon service bundle (s6)"
    s6-db-reload
  ;;
  *)
    echo -e "\n* Unsupported init system detected, could not remove the daemon"
    echo -e "\n* Please open an issue on https://github.com/AdnanHodzic/auto-cpufreq\n"
  ;;
esac
