#!/usr/bin/env python3
#
# auto-cpufreq - Automatic CPU speed & power optimizer for Linux
#
# Blog post: https://foolcontrol.org/?p=3124

# core import
import sys
import time
from click import UsageError
from subprocess import call, run

# sys.path.append("../")
from auto_cpufreq.core import *
from auto_cpufreq.power_helper import *
from auto_cpufreq.battery_scripts.battery import *
# cli
@click.command()
@click.option("--monitor", is_flag=True, help="Monitor and see suggestions for CPU optimizations")
@click.option("--live", is_flag=True, help="Monitor and make (temp.) suggested CPU optimizations")
@click.option("--install", is_flag=True, help="Install daemon for (permanent) automatic CPU optimizations")
@click.option("--update", is_flag=False, help="Update daemon and package for (permanent) automatic CPU optimizations", flag_value="--update")
@click.option("--remove", is_flag=True, help="Remove daemon for (permanent) automatic CPU optimizations")

@click.option("--stats", is_flag=True, help="View live stats of CPU optimizations made by daemon")
@click.option("--force", is_flag=False, help="Force use of either \"powersave\" or \"performance\" governors. Setting to \"reset\" will go back to normal mode")
@click.option("--get-state", is_flag=True, hidden=True)
@click.option(
    "--config",
    is_flag=False,
    default="/etc/auto-cpufreq.conf",
    help="Use config file at defined path",
)
@click.option("--debug", is_flag=True, help="Show debug info (include when submitting bugs)")
@click.option("--version", is_flag=True, help="Show currently installed version")
@click.option("--donate", is_flag=True, help="Support the project")
@click.option("--completions", is_flag=False, help="Enables shell completions for bash, zsh and fish.\n Possible values bash|zsh|fish")
@click.option("--log", is_flag=True, hidden=True)
@click.option("--daemon", is_flag=True, hidden=True)
def main(config, daemon, debug, update, install, remove, live, log, monitor, stats, version, donate, force, get_state, completions):

    # display info if config file is used
    def config_info_dialog():
        if get_config(config) and hasattr(get_config, "using_cfg_file"):
            print("\nUsing settings defined in " + config + " file")

    # set governor override unless None or invalid
    if force is not None:
        not_running_daemon_check()
        root_check() # Calling root_check before set_override as it will require sudo access
        set_override(force) # Calling set override, only if force has some values

    if len(sys.argv) == 1:
        print("\n" + "-" * 32 + " auto-cpufreq " + "-" * 33 + "\n")
        print("Automatic CPU speed & power optimizer for Linux")
 
        print("\nExample usage:\nauto-cpufreq --monitor")
        print("\n-----\n")

        run(["auto-cpufreq", "--help"])
        footer()
    else:
        if daemon:
            config_info_dialog()
            root_check()
            file_stats()
            if os.getenv("PKG_MARKER") == "SNAP" and dcheck == "enabled":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
                battery_setup()
                while True:
                    footer()
                    gov_check()
                    cpufreqctl()
                    distro_info()
                    sysinfo()
                    set_autofreq()
                    countdown(2)
            elif os.getenv("PKG_MARKER") != "SNAP":
                gnome_power_detect()
                tlp_service_detect()
                battery_setup()
                while True:
                    footer()
                    gov_check()
                    cpufreqctl()
                    distro_info()
                    sysinfo()
                    set_autofreq()
                    countdown(2)
            else:
                pass
            #"daemon_not_found" is not defined
                #daemon_not_found()
        elif monitor:
            config_info_dialog()
            root_check()
            print('\nNote: You can quit monitor mode by pressing "ctrl+c"')
            battery_setup()
            battery_get_thresholds()
            if os.getenv("PKG_MARKER") == "SNAP":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect()
                tlp_service_detect()
            while True:
                time.sleep(1)
                running_daemon_check()
                footer()
                gov_check()
                cpufreqctl()
                distro_info()
                sysinfo()
                mon_autofreq()
                countdown(2)
        elif live:
            root_check()
            config_info_dialog()
            print('\nNote: You can quit live mode by pressing "ctrl+c"')
            time.sleep(1)
            battery_setup()
            battery_get_thresholds()
            if os.getenv("PKG_MARKER") == "SNAP":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect_install()
                gnome_power_stop_live()
                tlp_service_detect()
            while True:
                try:
                    running_daemon_check()
                    footer()
                    gov_check()
                    cpufreqctl()
                    distro_info()
                    sysinfo()
                    set_autofreq()
                    countdown(2)
                except KeyboardInterrupt:
                    gnome_power_start_live()
                    print("")
                    sys.exit()
        elif stats:
            not_running_daemon_check()
            config_info_dialog()
            print('\nNote: You can quit stats mode by pressing "ctrl+c"')
            if os.getenv("PKG_MARKER") == "SNAP":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect()
                tlp_service_detect()
            read_stats()
        elif log:
            deprecated_log_msg()
        elif get_state:
            not_running_daemon_check()
            override = get_override()
            print(override)
        elif debug:
            # ToDo: add status of GNOME Power Profile service status
            config_info_dialog()
            root_check()
            cpufreqctl()
            footer()
            distro_info()
            sysinfo()
            print("")
            app_version()
            print("")
            python_info()
            print("")
            device_info()
            if charging():
                print("Battery is: charging")
            else:
                print("Battery is: discharging")
            print("")
            app_res_use()
            display_load()
            get_current_gov()
            get_turbo()
            footer()
        elif version:
            footer()
            distro_info()
            app_version()
            footer()
        elif donate:
            footer()
            print("If auto-cpufreq helped you out and you find it useful ...\n")
            print("Show your appreciation by donating!")
            print("https://github.com/AdnanHodzic/auto-cpufreq/#donate")
            footer()
        elif install:
            if os.getenv("PKG_MARKER") == "SNAP":
                root_check()
                running_daemon_check()
                gnome_power_detect_snap()
                tlp_service_detect_snap()
                bluetooth_notif_snap()
                gov_check()
                run("snapctl set daemon=enabled", shell=True)
                run("snapctl start --enable auto-cpufreq", shell=True)
                deploy_complete_msg()
            else:
                root_check()
                running_daemon_check()
                gov_check()
                deploy_daemon()
                deploy_complete_msg()
        elif remove:
            if os.getenv("PKG_MARKER") == "SNAP":
                root_check()
                run("snapctl set daemon=disabled", shell=True)
                run("snapctl stop --disable auto-cpufreq", shell=True)
                if auto_cpufreq_stats_path.exists():
                    if auto_cpufreq_stats_file is not None:
                        auto_cpufreq_stats_file.close()

                    auto_cpufreq_stats_path.unlink()
                # ToDo: 
                # {the following snippet also used in --update, update it there too(if required)}
                # * undo bluetooth boot disable
                gnome_power_rm_reminder_snap()
                remove_complete_msg()
            else:
                root_check()
                remove_daemon()
                remove_complete_msg()
        elif update:
            root_check()
            custom_dir = "/opt/auto-cpufreq/source"
            for arg in sys.argv:
                if arg.startswith("--update="):
                    custom_dir = arg.split("=")[1]
                    sys.argv.remove(arg)
                    
            if "--update" in sys.argv:
                update = True
                sys.argv.remove("--update")
                if len(sys.argv) == 2:
                    custom_dir = sys.argv[1] 
                    
            if os.getenv("PKG_MARKER") == "SNAP":
                print("Detected auto-cpufreq was installed using snap")
                # refresh snap directly using this command
                # path wont work in this case

                print("Please update using snap package manager, i.e: `sudo snap refresh auto-cpufreq`.")
                #check for AUR 
            elif subprocess.run(["bash", "-c", "command -v pacman >/dev/null 2>&1"]).returncode == 0 and subprocess.run(["bash", "-c", "pacman -Q auto-cpufreq >/dev/null 2>&1"]).returncode == 0:
                print("Arch-based distribution with AUR support detected. Please refresh auto-cpufreq using your AUR helper.")
            else:
                is_new_update = check_for_update()
                if not is_new_update:
                    return
                ans = input("Do you want to update auto-cpufreq to the latest release? [Y/n]: ").strip().lower()
                if not os.path.exists(custom_dir):
                    os.makedirs(custom_dir)
                if os.path.exists(os.path.join(custom_dir, "auto-cpufreq")):
                    shutil.rmtree(os.path.join(custom_dir, "auto-cpufreq"))
                if ans in ['', 'y', 'yes']:
                    remove_daemon()
                    remove_complete_msg()
                    new_update(custom_dir)
                    print("enabling daemon")
                    run(["auto-cpufreq", "--install"])
                    print("auto-cpufreq is installed with the latest version")
                    run(["auto-cpufreq", "--version"])
                else:
                    print("Aborted")

        elif completions:
            if completions == "bash":
                print("Run the below command in your current shell!\n")
                print("echo 'eval \"$(_AUTO_CPUFREQ_COMPLETE=bash_source auto-cpufreq)\"' >> ~/.bashrc")
                print("source ~/.bashrc")
            elif completions == "zsh":
                print("Run the below command in your current shell!\n")
                print("echo 'eval \"$(_AUTO_CPUFREQ_COMPLETE=zsh_source auto-cpufreq)\"' >> ~/.zshrc")
                print("source ~/.zshrc")
            elif completions == "fish":
                print("Run the below command in your current shell!\n")
                print("echo '_AUTO_CPUFREQ_COMPLETE=fish_source auto-cpufreq | source' > ~/.config/fish/completions/auto-cpufreq.fish")
            else:
                print("Invalid Option, try bash|zsh|fish as argument to --completions")
                


if __name__ == "__main__":
    main()
