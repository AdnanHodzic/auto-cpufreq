#!/bin/sh
# auto-cpufreq wrapper — uses system Python packages
exec /usr/bin/python3 -m auto_cpufreq.bin.auto_cpufreq "$@"