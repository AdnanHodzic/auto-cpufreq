#!/usr/bin/env bash

VERSION='20'
cpucount=`cat /proc/cpuinfo|grep processor|wc -l`
FLROOT=/sys/devices/system/cpu
DRIVER=auto
VERBOSE=0

## parse special options
for i in "$@"
do
case $i in
  -v|--verbose)
    VERBOSE=1
    shift
  ;;
  --set=*)
    VALUE="${i#*=}"
    shift
  ;;
  -c=*|--core=*)
    CORE="${i#*=}"
    shift
  ;;
  --available)
    AVAILABLE=1
    shift
  ;;
  -*)
    OPTION=$i
    shift
  ;;
  *) # unknown
  ;;
esac
done

function help () {
  echo "Package version: "$VERSION
  echo "Usage:"
  echo "  cpufreqctl [OPTION[=VALUE]...]"
  echo ""
  echo "  --help                 Show help options"
  echo "  --version              Package version"
  echo "  --verbose, -v          Verbose output"
  echo ""
  echo "  --set=VALUE            Set VALUE for selected option"
  echo "  --core=NUMBER          Apply selected option just for the core NUMBER (0 ~ N - 1)"
  echo "  --available            Get available values instand of default: current"
  echo ""
  echo "  --driver               Current processor driver"
  echo "  --governor             Scaling governor's options"
  echo "  --epp                  Governor's energy_performance_preference options"
  echo "  --frequency            Frequency options"
  echo "  --on                   Turn on --core=NUMBER"
  echo "  --off                  Turn off --core=NUMBER"
  echo "  --frequency-min        Minimal frequency options"
  echo "  --frequency-max        Maximum frequency options"
  echo "  --frequency-min-limit  Get minimal frequency limit"
  echo "  --frequency-max-limit  Get maximum frequency limit"
  echo "  --boost                Current cpu boost value"
  echo ""
  echo "intel_pstate options"
  echo "  --no-turbo      Current no_turbo value"
  echo "  --min-perf      Current min_perf_pct options"
  echo "  --max-perf      Current max_perf_pct options"
  echo ""
  echo "Events options"
  echo "  --throttle      Get thermal throttle counter"
  echo "  --throttle-event Get kernel thermal throttle events counter"
  echo "  --irqbalance     Get irqbalance presence"
}

function info () {
  echo "CPU driver: "`driver`
  echo "Governors: "`cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors`
  echo "Frequencies: "`cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies`
  echo ""
  echo "Usage:"
  echo "## list scaling governors:"
  echo "cpufreqctl --governor"
  echo ""
  echo "## Set all active cpu cores to the 'performance' scaling governor:"
  echo "cpufreqctl --governor --set=performance"
  echo ""
  echo "## Set 'performance' scaling governor for the selected core:"
  echo "cpufreqctl --governor --set=performance --core=0"
  echo ""
  echo "Use --help argument to see available options"
}

verbose () {
  if [ $VERBOSE = 1 ]; then echo $1; fi
}

function driver () {
  cat $FLROOT/cpu0/cpufreq/scaling_driver
}

function write_value () {
  if [ -w $FLNM ]; then echo $VALUE > $FLNM; fi
}

function set_driver () {
  DRIVER=`driver`
  case $DRIVER in
    intel*|*pstate*) DRIVER=pstate;;
    *)DRIVER=acpi;;
  esac
}

function get_governor () {
  if [ -z $CORE ]
  then
    i=0
    ag=''
    while [ $i -ne $cpucount ]; do
      if [ $i = 0 ]; then ag=`cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`
      else ag=$ag' '`cat /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor`
      fi
      i=`expr $i + 1`
    done
    echo $ag
  else cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_governor
  fi
}

function set_governor () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_governor"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_governor
  fi
}

function get_frequency () {
  if [ -z $CORE ]; then
    i=0
    V=0
    M=$(cat "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    while [ $i -ne $cpucount ]; do
      V=$(cat "/sys/devices/system/cpu/cpu"$i"/cpufreq/scaling_cur_freq")
      if [[ $V > $M ]]; then M=$V; fi
      i=`expr $i + 1`
    done
    echo "$M"
  else cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_cur_freq
  fi
}

function set_frequency () {
  set_driver
  if [ $DRIVER = 'pstate']; then
    echo "Unavailable function for intel_pstate"
    return
  fi
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_setspeed"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_setspeed
  fi
}

function get_frequency_min () {
  if [ -z $CORE ]; then CORE=0; fi
  cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_min_freq
}

function set_frequency_min () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_min_freq"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_min_freq
  fi
}

function get_frequency_max () {
  if [ -z $CORE ]; then CORE=0; fi
  cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_max_freq
}

function set_frequency_max () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_max_freq"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_max_freq
  fi
}

function get_frequency_min_limit () {
  if [ -z $CORE ]; then CORE=0; fi
  cat /sys/devices/system/cpu/cpu$CORE/cpufreq/cpuinfo_min_freq
}

function get_frequency_max_limit () {
  if [ -z $CORE ]; then CORE=0; fi
  cat /sys/devices/system/cpu/cpu$CORE/cpufreq/cpuinfo_max_freq
}

function get_energy_performance_preference () {
  if [ -z $CORE ]; then
    i=0
    ag=''
    while [ $i -ne $cpucount ]; do
      if [ $i = 0 ]; then
        ag=`cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference`
      else
        ag=$ag' '`cat /sys/devices/system/cpu/cpu$i/cpufreq/energy_performance_preference`
      fi
      i=`expr $i + 1`
    done
    echo $ag
  else cat /sys/devices/system/cpu/cpu$CORE/cpufreq/energy_performance_preference
  fi
}

function set_energy_performance_preference () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/energy_performance_preference"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > /sys/devices/system/cpu/cpu$CORE/cpufreq/energy_performance_preference
  fi
}

# No options
if [ -z $OPTION ]; then
  info
  exit
fi
if [ $OPTION = "--help" ]; then
  help
  exit
fi
if [ $OPTION = "--version" ]; then
  echo $VERSION
  exit
fi
if [ $OPTION = "--driver" ]; then
	driver
	exit
fi
if [ $OPTION = "--governor" ]; then
  if [ ! -z $AVAILABLE ]; then
    cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
    exit
  fi
  if [ -z $VALUE ]; then
    verbose "Getting CPU"$CORE" governors"
    get_governor
  else
    verbose "Setting CPU"$CORE" governors to "$VALUE
    set_governor
  fi
  exit
fi
if [ $OPTION = "--epp" ]; then
  if [ ! -z $AVAILABLE ]; then
    cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences
    exit
  fi
  if [ -z $VALUE ]; then
    verbose "Getting CPU"$CORE" EPPs"
    get_energy_performance_preference
  else
    verbose "Setting CPU"$CORE" EPPs to "$VALUE
    set_energy_performance_preference
  fi
  exit
fi
if [ $OPTION = "--frequency" ]; then
  if [ ! -z $AVAILABLE ]; then
    cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
    exit
  fi
  if [ -z $VALUE ]
  then
    verbose "Getting CPU"$CORE" frequency"
    get_frequency
  else
    verbose "Setting CPU"$CORE" frequency to "$VALUE
    set_frequency
  fi
  exit
fi
if [ $OPTION = "--no-turbo" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting no_turbo value"
    cat /sys/devices/system/cpu/intel_pstate/no_turbo
  else
    verbose "Setting no_turbo value "$VALUE
    echo $VALUE > /sys/devices/system/cpu/intel_pstate/no_turbo
  fi
  exit
fi
if [ $OPTION = "--boost" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting boost value"
    cat /sys/devices/system/cpu/cpufreq/boost
  else
    verbose "Setting boost value "$VALUE
    echo $VALUE > /sys/devices/system/cpu/cpufreq/boost
  fi
  exit
fi
if [ $OPTION = "--frequency-min" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting CPU"$CORE" minimal frequency"
    get_frequency_min
  else
    verbose "Setting CPU"$CORE" minimal frequency to "$VALUE
    set_frequency_min
  fi
  exit
fi
if [ $OPTION = "--frequency-max" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting CPU"$CORE" maximal frequency"
    get_frequency_max
  else
    verbose "Setting CPU"$CORE" maximal frequency to "$VALUE
    set_frequency_max
  fi
  exit
fi
if [ $OPTION = "--frequency-min-limit" ]
then
    verbose "Getting CPU"$CORE" minimal frequency limit"
    get_frequency_min_limit
fi
if [ $OPTION = "--frequency-max-limit" ]
then
    verbose "Getting CPU"$CORE" maximum frequency limit"
    get_frequency_max_limit
fi
if [ $OPTION = "--min-perf" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting min_perf_pct value"
    cat /sys/devices/system/cpu/intel_pstate/min_perf_pct
  else
    verbose "Setting min_perf_pct value "$VALUE
    echo $VALUE > /sys/devices/system/cpu/intel_pstate/min_perf_pct
  fi
  exit
fi
if [ $OPTION = "--max-perf" ]
then
  if [ -z $VALUE ]
  then
    verbose "Getting max_perf_pct value"
    cat /sys/devices/system/cpu/intel_pstate/max_perf_pct
  else
    verbose "Setting max_perf_pct value "$VALUE
    echo $VALUE > /sys/devices/system/cpu/intel_pstate/max_perf_pct
  fi
  exit
fi
if [ $OPTION = "--on" ]
then
  if [ -z $CORE ]
  then
    verbose "Should be specify --core=NUMBER"
  else
    verbose "Power on CPU Core"$CORE
    echo "1" > $FLROOT/cpu"$CORE"/online
  fi
  exit
fi
if [ $OPTION = "--off" ]
then
  if [ -z $CORE ]
  then
    verbose "Should be specify --core=NUMBER"
  else
    verbose "Power off CPU Core"$CORE
    echo "0" > $FLROOT/cpu"$CORE"/online
  fi
  exit
fi

if [ $OPTION = "--throttle" ]
then
  i=1
  V=0
  M=$(cat "/sys/devices/system/cpu/cpu0/thermal_throttle/core_throttle_count")
  while [ $i -ne $cpucount ]
  do
    V=$(cat "/sys/devices/system/cpu/cpu"$i"/thermal_throttle/core_throttle_count")
    M=`expr $M + $V`
    i=`expr $i + 1`
  done
  echo "$M"
  exit
fi
if [ $OPTION = "--throttle-events" ]
then
  M=$(journalctl --dmesg --boot --since=yesterday | grep "cpu clock throttled" | wc -l)
  echo "$M"
  exit
fi
if [ $OPTION = "--irqbalance" ]
then
  M=$(ps -A |grep irqbalance)
  echo "$M"
  exit
fi
