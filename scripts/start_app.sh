#!/usr/bin/sh

# load python virtual environment
venv_dir=/opt/auto-cpufreq/venv
. "$venv_dir/bin/activate"
python_command="$venv_dir/bin/auto-cpufreq-gtk"

# if [ "$XDG_SESSION_TYPE" = "wayland" ] ; then
#     # necessary for running on wayland
#     xhost +SI:localuser:root
#     pkexec $python_command
#     xhost -SI:localuser:root
#     xhost
# else
#     pkexec $python_command
# fi

$python_command