#!/bin/bash
#
# workaround for running Daemon without polluting syslog (#53, #82)
$SNAP/bin/auto-cpufreq --daemon 2>&1 >> $SNAP_DATA/auto-cpufreq.stats
