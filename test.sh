#!/bin/bash


#if [ -f /etc/os-release ] && eval "$(cat /etc/os-release)" && [[ $ID == "manjaro" || $ID == "arch" || $ID == "endeavouros" || $ID == "garuda" || $ID == "artix" ]]; then
#	echo test
#	if [[ $ID != "garuda" ]]; then
#		echo passed
#    	fi
#fi


#distro_() {
[ -f /etc/os-release ] && eval "$(cat /etc/os-release)"
#}

function installing_pkgs() {
	echo -e "\nDetected an distribution\n"
	echo -e "\nSetting up Python environment\n"
}

function detected_distro() {
	echo -e "\nDetected $1 distribution"
	separator
	echo -e "\nSetting up Python environment\n"
}

separator
if [ -f /etc/debian_version ]; then
	detected_distro "Debian based"
elif [ -f /etc/redhat-release ]; then
elif [ -f /etc/solus-release ]; then

elif [ -f /etc/os-release ];then
	eval "$(cat /etc/os-release)"
	case $ID in
		opensuse-leap)
			zypper install -y python3 python3-pip python3-setuptools python3-devel gcc dmidecode
			;;
		opensuse)
			detected_distro "Debian based"
    			echo -e "\nDetected an OpenSUSE ditribution\n\nSetting up Python environment\n"
			zypper install -y python38 python3-pip python3-setuptools python3-devel gcc dmidecode
			;;
		arch|manjaro|endeavouros|garuda|artix)
    			echo -e "\nDetected an Arch Linux based ditribution\n\nSetting up Python environment\n"
			pacman -S --noconfirm --needed python python-pip python-setuptools base-devel dmidecode
			[ $ID != "artix" ] && update_service_file
			;;
		void)
    			echo -e "\nDetected Void Linux ditribution\n\nSetting up Python environment\n"
    			xbps-install -Suy python3 python3-pip python3-devel python3-setuptools base-devel dmidecode
			;;
		*)
			echo bye;;
	esac
fi
install
separator
complete_msg
separator
