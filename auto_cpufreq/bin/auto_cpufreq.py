#!/usr/bin/env python3
#
# auto-cpufreq - Automatic CPU speed & power optimizer for Linux
#
# Blog post: https://foolcontrol.org/?p=3124
import click
from os import geteuid
from subprocess import check_call
from sys import argv

from auto_cpufreq import prints
from auto_cpufreq.commands import *
from auto_cpufreq.core import current_gov_msg, read_stats
from auto_cpufreq.dialogs import app_version
from auto_cpufreq.globals import AVAILABLE_GOVERNORS, AVAILABLE_SHELLS

@click.command()
@click.option('-m', '--monitor', is_flag=True, help='Monitor and see suggestions for CPU optimizations')
@click.option('-l', '--live', is_flag=True, help='Monitor and make (temp.) suggested CPU optimizations')
@click.option('-d', '--daemon', is_flag=True, help='Run daemon for (temp.) automatic CPU optimizations')
@click.option('-i', '--install', is_flag=True, help='Install daemon for (permanent) automatic CPU optimizations')
@click.option('-u', '--update', is_flag=True, help='Update daemon and package for (permanent) automatic CPU optimizations')
@click.option('-r', '--remove', is_flag=True, help='Remove daemon for (permanent) automatic CPU optimizations')
@click.option('-f', '--force', is_flag=False, required=False, help='Force use governors. Setting to "reset" will go back to normal mode', type=click.Choice((*AVAILABLE_GOVERNORS, 'reset')))
@click.option('-c', '--config', is_flag=False, required=False, help='Use config file at defined path')
@click.option('--color', is_flag=True, required=False, help='Use output with color')
@click.option('--stats', is_flag=True, help='View live stats of CPU optimizations made by daemon')
@click.option('--get-state', is_flag=True, hidden=True)
@click.option('--completions', is_flag=True, help='Enables shell completions, available for '+', '.join(AVAILABLE_SHELLS))
@click.option('--debug', is_flag=True, help='Show debug info (include when submitting bugs)')
@click.option('--version', is_flag=True, help='Show currently installed version')
@click.option('--donate', is_flag=True, help='Support the project')
def main(monitor, live, daemon, install, update, remove, force, config, color, stats, get_state, completions, debug, version, donate):
    prints.COLOR = color
    if len(argv) == 1:
        help_command()
        return
    
    if geteuid() != 0:
        try: check_call(['sudo', *argv])
        except:
            print_error('Must be run root to work')
            exit(1)
        return

    if force is not None: force_command(force)
    if monitor: monitor_command(config)
    elif live: live_command(config)
    elif daemon: daemon_command(config)
    elif install: install_command()
    elif update: update_command()
    elif remove: remove_command()
    elif stats:
        check_auto_cpufreq_daemon_state(True)
        read_stats()
    elif get_state:
        check_auto_cpufreq_daemon_state(True)
        current_gov_msg()
    elif completions: completions_command()
    elif debug: debug_command()
    elif version: app_version()
    elif donate: donnate_command()
                
if __name__ == '__main__': main()
