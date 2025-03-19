#!/usr/bin/env python3
#
# auto-cpufreq - Automatic CPU speed & power optimizer for Linux
#
# Blog post: https://foolcontrol.org/?p=3124

# core import
import logging
import sys, time
from subprocess import run
from shutil import rmtree
from gi.repository import GLib
from auto_cpufreq.battery_scripts.battery import *
from auto_cpufreq.config.config import config as conf, find_config_file
from auto_cpufreq.core import *
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.modules.observer import observer
from auto_cpufreq.modules.handler import system_events_handler
from auto_cpufreq.modules.system_monitor import ViewType, SystemMonitor
from auto_cpufreq.power_helper import *
from threading import Thread

from auto_cpufreq.types import ObserverEvent

@click.command()
@click.option("--monitor", is_flag=True, help="Monitor and see suggestions for CPU optimizations")
@click.option("--live", is_flag=True, help="Monitor and make (temp.) suggested CPU optimizations")
@click.option("--daemon", is_flag=True, hidden=True)
@click.option("--install", is_flag=True, help="Install daemon for (permanent) automatic CPU optimizations")
@click.option("--update", is_flag=False, help="Update daemon and package for (permanent) automatic CPU optimizations", flag_value="--update")
@click.option("--remove", is_flag=True, help="Remove daemon for (permanent) automatic CPU optimizations")
@click.option("--force", is_flag=False, help="Force use of either \"powersave\" or \"performance\" governors. Setting to \"reset\" will go back to normal mode")
@click.option("--config", is_flag=False, required=False, help="Use config file at defined path",)
@click.option("--stats", is_flag=True, help="View live stats of CPU optimizations made by daemon")
@click.option("--get-state", is_flag=True, hidden=True)
@click.option("--completions", is_flag=False, help="Enables shell completions for bash, zsh and fish.\n Possible values bash|zsh|fish")
@click.option("--debug", is_flag=True, help="Show debug info (include when submitting bugs)")
@click.option("--version", is_flag=True, help="Show currently installed version")
@click.option("--donate", is_flag=True, help="Support the project")
def main(monitor, live, daemon, install, update, remove, force, config, stats, get_state, completions, debug, version, donate):
    # display info if config file is used
    config_path = find_config_file(config)
    conf.set_path(config_path)
    def config_info_dialog():
        if conf.has_config():
            print("\nUsing settings defined in " + config_path + " file")

    if len(sys.argv) == 1:
        print("\n" + "-" * 32 + " auto-cpufreq " + "-" * 33 + "\n")
        print("Automatic CPU speed & power optimizer for Linux")
 
        print("\nExample usage:\nauto-cpufreq --monitor")
        print("\n-----\n")

        run(["auto-cpufreq", "--help"])
        footer()
    else:
        # set governor override unless None or invalid
        if force is not None:
            not_running_daemon_check()
            root_check() # Calling root_check before set_override as it will require sudo access
            set_override(force) # Calling set override, only if force has some values

        if monitor:
            root_check()
            battery_setup()
            conf.notifier.start()
            if IS_INSTALLED_WITH_SNAP:
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect()
                tlp_service_detect()
                
            if IS_INSTALLED_WITH_SNAP or tlp_stat_exists or (systemctl_exists and not bool(gnome_power_status)):
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    conf.notifier.stop()
                    sys.exit(0)
            
            monitor = SystemMonitor(suggestion=True, type=ViewType.MONITOR)
            monitor.run(on_quit=conf.notifier.stop)
        elif live:
            root_check()
            battery_setup()
            conf.notifier.start()
            if IS_INSTALLED_WITH_SNAP:
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect_install()
                gnome_power_stop_live()
                tuned_stop_live()
                tlp_service_detect()
            
            if IS_INSTALLED_WITH_SNAP or tlp_stat_exists or (systemctl_exists and not bool(gnome_power_status)):
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    conf.notifier.stop()
                    sys.exit(0)
            
            cpufreqctl()
            def live_daemon():
                # Redirect stdout to suppress prints
                class NullWriter:
                    def write(self, _): pass
                    def flush(self): pass
                try:
                    sys.stdout = NullWriter()
                    
                    while True:
                        time.sleep(1)
                        set_autofreq()
                except:
                    pass
            
            def live_daemon_off():
                gnome_power_start_live()
                tuned_start_live()
                cpufreqctl_restore()
                conf.notifier.stop()
            
            thread = Thread(target=live_daemon, daemon=True)
            thread.start()
            
            monitor = SystemMonitor(type=ViewType.LIVE)
            monitor.run(on_quit=live_daemon_off)
        elif daemon:
            config_info_dialog()
            root_check()
            file_stats()
            if IS_INSTALLED_WITH_SNAP and SNAP_DAEMON_CHECK == "enabled":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            elif not IS_INSTALLED_WITH_SNAP:
                gnome_power_detect()
                tlp_service_detect()
            battery_setup()
            conf.notifier.start()
            # while True:
            #     try:
            #         footer()
            #         gov_check()
            #         cpufreqctl()
            #         distro_info()
            #         sysinfo()
            #         set_autofreq()
            #         countdown(2)
            #     except KeyboardInterrupt: break
            observer.listen(
                event=ObserverEvent.POWER_SOURCE, 
                callback=system_events_handler.handle_power_source,
            )
            observer.listen(
                event=ObserverEvent.SYS_LOAD, 
                callback=system_events_handler.handle_sys_load,
            )
            observer.listen(
                event=ObserverEvent.SYS_TEMP, 
                callback=system_events_handler.handle_sys_temp,
            )
            system_events_handler.init()
            try:
                thread: Thread = observer.start()
                logging.info("Daemon started, pid: %s", os.getpid())
                loop = GLib.MainLoop()
                loop.run()
            except (KeyboardInterrupt, SystemExit):
                observer.stop()
                conf.notifier.stop()
        elif install:
            root_check()
            if IS_INSTALLED_WITH_SNAP:
                running_daemon_check()
                gnome_power_detect_snap()
                tlp_service_detect_snap()
                bluetooth_notif_snap()
                gov_check()
                run("snapctl set daemon=enabled", shell=True)
                run("snapctl start --enable auto-cpufreq", shell=True)
            else:
                running_daemon_check()
                gov_check()
                deploy_daemon()
            deploy_complete_msg()
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
                if len(sys.argv) == 2: custom_dir = sys.argv[1] 
                    
            if IS_INSTALLED_WITH_SNAP:
                print("Detected auto-cpufreq was installed using snap")
                # refresh snap directly using this command
                # path wont work in this case

                print("Please update using snap package manager, i.e: `sudo snap refresh auto-cpufreq`.")
                #check for AUR 
            elif IS_INSTALLED_WITH_AUR: print("Arch-based distribution with AUR support detected. Please refresh auto-cpufreq using your AUR helper.")
            else:
                is_new_update = check_for_update()
                if not is_new_update: return
                ans = input("Do you want to update auto-cpufreq to the latest release? [Y/n]: ").strip().lower()
                if not os.path.exists(custom_dir): os.makedirs(custom_dir)
                if os.path.exists(os.path.join(custom_dir, "auto-cpufreq")): rmtree(os.path.join(custom_dir, "auto-cpufreq"))
                if ans in ['', 'y', 'yes']:
                    remove_daemon()
                    remove_complete_msg()
                    new_update(custom_dir)
                    print("enabling daemon")
                    run(["auto-cpufreq", "--install"])
                    print("auto-cpufreq is installed with the latest version")
                    run(["auto-cpufreq", "--version"])
                else: print("Aborted")
        elif remove:
            root_check()
            if IS_INSTALLED_WITH_SNAP:
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
            else: remove_daemon()
            remove_complete_msg()
        elif stats:
            not_running_daemon_check()
            config_info_dialog()
            if IS_INSTALLED_WITH_SNAP:
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            else:
                gnome_power_detect()
                tlp_service_detect()
            
            if IS_INSTALLED_WITH_SNAP or tlp_stat_exists or (systemctl_exists and not bool(gnome_power_status)):
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    conf.notifier.stop()
                    sys.exit(0)
            
            monitor = SystemMonitor(type=ViewType.STATS)
            monitor.run()
        elif get_state:
            not_running_daemon_check()
            override = get_override()
            print(override)
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
            else: print("Invalid Option, try bash|zsh|fish as argument to --completions")
        elif debug:
            # ToDo: add status of GNOME Power Profile service status
            config_info_dialog()
            root_check()
            battery_get_thresholds()
            cpufreqctl()
            footer()
            distro_info()
            sysinfo()
            print()
            app_version()
            print()
            python_info()
            print()
            device_info()
            print(f"Battery is: {'' if charging() else 'dis'}charging")
            print()
            app_res_use()
            get_load()
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
            print(GITHUB+"#donate")
            footer()
                
if __name__ == "__main__": main()
