#!/usr/bin/env python3
#
# auto-cpufreq - Automatic CPU speed & power optimizer for Linux
#
# Blog post: https://foolcontrol.org/?p=3124

# core import
import sys, time, os
from subprocess import run
from shutil import rmtree

from auto_cpufreq.battery_scripts.battery import *
from auto_cpufreq.config.config import config as conf, find_config_file
from auto_cpufreq.core import *
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP, SNAP_DAEMON_CHECK
from auto_cpufreq.modules.system_monitor import ViewType, SystemMonitor
# import everything from power_helper, including bluetooth_disable and bluetooth_enable
from auto_cpufreq.power_helper import *
from threading import Thread

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
@click.option("--bluetooth_boot_off", is_flag=True, help="Turn off Bluetooth on boot")
@click.option("--bluetooth_boot_on", is_flag=True, help="Turn on Bluetooth on boot")
@click.option("--debug", is_flag=True, help="Show debug info (include when submitting bugs)")
@click.option("--version", is_flag=True, help="Show currently installed version")
@click.option("--donate", is_flag=True, help="Support the project")
def main(monitor, live, daemon, install, update, remove, force, config, stats, get_state,
         bluetooth_boot_off,
         bluetooth_boot_on,
         debug, version, donate):
    # display info if config file is used
    config_path = find_config_file(config)
    conf.set_path(config_path)
    def config_info_dialog():
        if conf.has_config():
            print("\nUsing settings defined in " + config_path + " file")

    # Check for empty arguments first
    is_empty_run = len(sys.argv) == 1

    # set governor override unless None or invalid, but not if it's an empty run
    if not is_empty_run and force is not None:
        not_running_daemon_check()
        root_check()
        set_override(force)

    # Handle empty run after potential force override is processed or skipped
    if is_empty_run:
        print("\n" + "-" * 32 + " auto-cpufreq " + "-" * 33 + "\n")
        print("Automatic CPU speed & power optimizer for Linux")
        print("\nExample usage:\nauto-cpufreq --monitor")
        print("\n-----\n")
        run(["auto-cpufreq", "--help"])
        footer()
    # Handle other flags if it's not an empty run
    else:
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

            # Determine if confirmation is needed
            needs_confirmation = IS_INSTALLED_WITH_SNAP or tlp_stat_exists
            # Check gnome_power_status only if relevant variables exist
            if not IS_INSTALLED_WITH_SNAP and 'systemctl_exists' in globals() and systemctl_exists and 'gnome_power_status' in locals() and not bool(gnome_power_status):
                 needs_confirmation = True

            if needs_confirmation:
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    conf.notifier.stop()
                    sys.exit(0)

            monitor_instance = SystemMonitor(suggestion=True, type=ViewType.MONITOR)
            monitor_instance.run(on_quit=conf.notifier.stop)
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

            # Determine if confirmation is needed
            needs_confirmation = IS_INSTALLED_WITH_SNAP or tlp_stat_exists
            # Check gnome_power_status only if relevant variables exist
            if not IS_INSTALLED_WITH_SNAP and 'systemctl_exists' in globals() and systemctl_exists and 'gnome_power_status' in locals() and not bool(gnome_power_status):
                 needs_confirmation = True

            if needs_confirmation:
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    conf.notifier.stop()
                    sys.exit(0)

            cpufreqctl()
            def live_daemon():
                class NullWriter:
                    def write(self, _): pass
                    def flush(self): pass
                original_stdout = sys.stdout
                try:
                    sys.stdout = NullWriter()
                    while True:
                        time.sleep(1)
                        set_autofreq()
                except Exception as e: # Catch specific exceptions if possible
                    print(f"Error in live daemon thread: {e}", file=original_stdout) # Log errors
                finally:
                    sys.stdout = original_stdout # Ensure stdout is restored

            def live_daemon_off():
                gnome_power_start_live()
                tuned_start_live()
                cpufreqctl_restore()
                conf.notifier.stop()

            thread = Thread(target=live_daemon, daemon=True)
            thread.start()

            monitor_instance = SystemMonitor(type=ViewType.LIVE)
            monitor_instance.run(on_quit=live_daemon_off)
        elif daemon:
            config_info_dialog()
            root_check()
            file_stats() # This function from core.py likely uses the stats paths internally
            if IS_INSTALLED_WITH_SNAP and SNAP_DAEMON_CHECK == "enabled":
                gnome_power_detect_snap()
                tlp_service_detect_snap()
            elif not IS_INSTALLED_WITH_SNAP:
                gnome_power_detect()
                tlp_service_detect()
            battery_setup()
            conf.notifier.start()
            print("Starting auto-cpufreq daemon...") # Add startup message
            try:
                # Initial setup before loop
                gov_check()
                cpufreqctl()
                distro_info() # Show info once on start
                sysinfo()     # Show info once on start
                while True:
                    set_autofreq()
                    time.sleep(2) # Use simple sleep instead of countdown
            except KeyboardInterrupt:
                print("\nDaemon interrupted. Restoring settings...")
            finally: # Ensure cleanup happens
                conf.notifier.stop()
                cpufreqctl_restore() # Restore system state when daemon stops
                footer()
        elif install:
            root_check()
            if IS_INSTALLED_WITH_SNAP:
                running_daemon_check()
                gnome_power_detect_snap()
                tlp_service_detect_snap()
                bluetooth_notif_snap() # Warn about bluetooth boot setting
                gov_check()
                run("snapctl set daemon=enabled", shell=True, check=True)
                run("snapctl start --enable auto-cpufreq", shell=True, check=True)
            else:
                running_daemon_check()
                gov_check()
                deploy_daemon() # This function from core.py likely uses stats paths
            deploy_complete_msg()
        elif update:
            root_check()
            custom_dir = "/opt/auto-cpufreq/source"
            update_flag_present = False
            args_to_remove = []
            # Simplified update argument parsing
            if "--update" in sys.argv:
                 update_flag_present = True
                 args_to_remove.append("--update")
                 # Simple check if next arg exists and isn't another flag
                 idx = sys.argv.index("--update")
                 if idx + 1 < len(sys.argv) and not sys.argv[idx+1].startswith('--'):
                      custom_dir = sys.argv[idx+1]
                      args_to_remove.append(custom_dir)
            else:
                 for arg in sys.argv:
                     if arg.startswith("--update="):
                         update_flag_present = True
                         custom_dir = arg.split("=", 1)[1]
                         args_to_remove.append(arg)
                         break # Found it, no need to check further

            # Remove the parsed arguments
            # This prevents them from being misinterpreted later if code relies on sys.argv directly
            _original_argv = sys.argv[:] # Make a copy if needed elsewhere
            sys.argv = [arg for arg in sys.argv if arg not in args_to_remove]


            if update_flag_present:
                if IS_INSTALLED_WITH_SNAP:
                    print("Detected auto-cpufreq was installed using snap")
                    print("Please update using snap package manager, i.e: `sudo snap refresh auto-cpufreq`.")
                elif IS_INSTALLED_WITH_AUR:
                    print("Arch-based distribution with AUR support detected. Please refresh auto-cpufreq using your AUR helper.")
                else:
                    is_new_update = check_for_update()
                    if not is_new_update: return
                    ans = input(f"Update source will be placed in '{custom_dir}'.\nDo you want to update auto-cpufreq to the latest release? [Y/n]: ").strip().lower()

                    if ans in ['', 'y', 'yes']:
                         # Ensure directory exists
                        os.makedirs(custom_dir, exist_ok=True)
                        auto_cpufreq_subdir = os.path.join(custom_dir, "auto-cpufreq")
                        if os.path.isdir(auto_cpufreq_subdir):
                            print(f"Removing existing source sub-directory: {auto_cpufreq_subdir}")
                            try:
                                rmtree(auto_cpufreq_subdir)
                            except OSError as e:
                                print(f"Error removing directory {auto_cpufreq_subdir}: {e}")
                                print("Update aborted.")
                                return # Stop update if cleanup fails

                        print("Removing existing installation (if any)...")
                        remove_daemon() # Call remove logic first
                        # remove_complete_msg() # Optional message
                        print(f"Downloading new version to {custom_dir}...")
                        new_update(custom_dir) # Download the update
                        print("Running installer for the updated version...")
                        # Use subprocess.run to call the install command of the main script
                        install_result = run([_original_argv[0], "--install"], check=False) # Use original script path
                        if install_result.returncode == 0:
                            print("\nUpdate and installation successful.")
                            run([_original_argv[0], "--version"])
                        else:
                            print("\nError during installation after update. Please check messages above.")
                    else:
                        print("Update aborted.")
            # else: # If neither --update nor --update= was found
                # Potentially show help or an error if update was expected
                # print("Update command not used correctly.")
                # run([_original_argv[0], "--help"])

        elif remove:
            root_check()
            if IS_INSTALLED_WITH_SNAP:
                run("snapctl stop auto-cpufreq", shell=True, check=False)
                run("snapctl set daemon=disabled", shell=True, check=True)
                # run("snapctl disable auto-cpufreq", shell=True, check=True) # Deprecated? Use stop --disable
                run("snapctl stop --disable auto-cpufreq", shell=True, check=True) # Correct way to stop and disable

                # Check if stats path/file variables exist before using them
                # These should be available from 'from auto_cpufreq.core import *'
                if 'auto_cpufreq_stats_path' in globals() and auto_cpufreq_stats_path.exists():
                    # Close file handle safely
                    if 'auto_cpufreq_stats_file' in globals() and auto_cpufreq_stats_file is not None:
                        if not auto_cpufreq_stats_file.closed:
                            try:
                                auto_cpufreq_stats_file.close()
                            except Exception as e:
                                print(f"Warning: Could not close stats file handle: {e}")
                        # Set to None after closing or if already closed
                        # auto_cpufreq_stats_file = None # Modifying imported var might be tricky

                    # Remove the file
                    try:
                        auto_cpufreq_stats_path.unlink()
                        print(f"Removed stats file: {auto_cpufreq_stats_path}")
                    except OSError as e:
                        print(f"Warning: Could not remove stats file {auto_cpufreq_stats_path}: {e}")

                # Reminders
                gnome_power_rm_reminder_snap()
                bluetooth_on_notif_snap()
            else:
                remove_daemon() # Defined in core.py, handles service removal and cleanup including stats file
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

            # Determine if confirmation is needed
            needs_confirmation = IS_INSTALLED_WITH_SNAP or tlp_stat_exists
             # Check gnome_power_status only if relevant variables exist
            if not IS_INSTALLED_WITH_SNAP and 'systemctl_exists' in globals() and systemctl_exists and 'gnome_power_status' in locals() and not bool(gnome_power_status):
                 needs_confirmation = True

            if needs_confirmation:
                try:
                    input("press Enter to continue or Ctrl + c to exit...")
                except KeyboardInterrupt:
                    # conf.notifier might not be started for stats mode
                    sys.exit(0)

            monitor_instance = SystemMonitor(type=ViewType.STATS)
            monitor_instance.run()
        elif get_state:
            not_running_daemon_check()
            override = get_override()
            print(override)

        elif bluetooth_boot_off:
            if IS_INSTALLED_WITH_SNAP:
                footer()
                bluetooth_notif_snap()
                footer()
            else:
                footer()
                root_check()
                bluetooth_disable()
                footer()
        elif bluetooth_boot_on:
            if IS_INSTALLED_WITH_SNAP:
                footer()
                bluetooth_on_notif_snap()
                footer()
            else:
                footer()
                root_check()
                bluetooth_enable()
                footer()
        elif debug:
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
            # Check charging status function exists and call it
            if 'charging' in globals() and callable(charging):
                 print(f"Battery is: {'' if charging() else 'dis'}charging")
            else:
                 print("Battery status unavailable.")
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
        # else: # Optional: Handle unrecognized flags if not caught by click
        #    print(f"Error: Unrecognized arguments.")
        #    run([_original_argv[0], "--help"])


if __name__ == "__main__":
     try:
         import click
     except ImportError:
         print("Error: Required dependency 'click' not found. Please install it (e.g., pip install click)")
         sys.exit(1)
     # Call main entry point
     main()