#!/usr/bin/env bash

VERSION='20'
cpucount=`cat /proc/cpuinfo | grep processor | wc -l`
FLROOT=/sys/devices/system/cpu
FWROOT=/sys/firmware
DRIVER=auto
VERBOSE=0

## parse special options
for i in "$@"; do
  case $i in
    -v|--verbose)
      VERBOSE=1
      shift
    ;;
    -s=*|--set=*)
      VALUE="${i#*=}"
      shift
    ;;
    -c=*|--core=*)
      CORE="${i#*=}"
      shift
    ;;
    -a|--available)
      AVAILABLE=1
      shift
    ;;
    -*)
      OPTION=$i
      shift
    ;;
    *) exit 1;;
  esac
done

function help () {
  echo "Package version: "$VERSION
  echo "Usage: cpufreqctl [OPTION[=VALUE]...]"
  echo
  echo "  -h, --help                  Show help options"
  echo "      --version               Package version"
  echo "  -v, --verbose               Verbose output"
  echo
  echo "  -s, --set       =VALUE      Set VALUE for selected option"
  echo "  -c, --core      =NUMBER     Apply selected option just for the core NUMBER (0 ~ N - 1)"
  echo "  -a, --available             Get available values instand of default: current"
  echo
  echo "  -d, --driver                Current processor driver"
  echo "  -g, --governor              Scaling governor's options"
  echo "  -e, --epp                   Governor's energy_performance_preference options"
  echo "  -f, --frequency             Frequency options"
  echo "      --on                    Turn on --core=NUMBER"
  echo "      --off                   Turn off --core=NUMBER"
  echo "      --frequency-min         Minimal frequency options"
  echo "      --frequency-max         Maximum frequency options"
  echo "      --frequency-min-limit   Get minimal frequency limit"
  echo "      --frequency-max-limit   Get maximum frequency limit"
  echo "  -b, --boost                 Current cpu boost value"
  echo
  echo "intel_pstate options"
  echo "      --no-turbo              Current no_turbo value"
  echo "      --min-perf              Current min_perf_pct options"
  echo "      --max-perf              Current max_perf_pct options"
  echo
  echo "Events options"
  echo "      --throttle              Get thermal throttle counter"
  echo "      --throttle-event        Get kernel thermal throttle events counter"
  echo "      --irqbalance            Get irqbalance presence"
}

function info () {
  echo "CPU driver: "`driver`
  echo "Governors: "`cat $FLROOT/cpu0/cpufreq/scaling_available_governors`
  echo "Frequencies: "`cat $FLROOT/cpu0/cpufreq/scaling_available_frequencies`
  echo
  echo "Usage:"
  echo "## list scaling governors:"
  echo "cpufreqctl --governor"
  echo
  echo "## Set all active cpu cores to the 'performance' scaling governor:"
  echo "cpufreqctl --governor --set=performance"
  echo
  echo "## Set 'performance' scaling governor for the selected core:"
  echo "cpufreqctl --governor --set=performance --core=0"
  echo
  echo "Use --help argument to see available options"
}

verbose () {
  if [ $VERBOSE = 1 ]; then echo $1; fi
}

function driver () {
  cat $FLROOT/cpu0/cpufreq/scaling_driver
}

function write_value () {
  if [ -w $FLNM ]; then echo $VALUE > $FLNM 2>/dev/null; fi
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
      if [ $i = 0 ]; then ag=`cat $FLROOT/cpu0/cpufreq/scaling_governor`
      else ag=$ag' '`cat $FLROOT/cpu$i/cpufreq/scaling_governor`
      fi
      i=`expr $i + 1`
    done
    echo $ag
  else cat $FLROOT/cpu$CORE/cpufreq/scaling_governor
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
  else echo $VALUE > $FLROOT/cpu$CORE/cpufreq/scaling_governor
  fi
}

function get_frequency () {
  if [ -z $CORE ]; then
    i=0
    V=0
    M=$(cat "$FLROOT/cpu0/cpufreq/scaling_cur_freq")
    while [ $i -ne $cpucount ]; do
      V=$(cat "$FLROOT/cpu"$i"/cpufreq/scaling_cur_freq")
      if [[ $V > $M ]]; then M=$V; fi
      i=`expr $i + 1`
    done
    echo "$M"
  else cat $FLROOT/cpu$CORE/cpufreq/scaling_cur_freq
  fi
}

function set_frequency () {
  set_driver
  if [ $DRIVER = 'pstate' ]; then
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
  else echo $VALUE > $FLROOT/cpu$CORE/cpufreq/scaling_setspeed
  fi
}

function get_frequency_min () {
  if [ -z $CORE ]; then CORE=0; fi
  cat $FLROOT/cpu$CORE/cpufreq/scaling_min_freq
}

function set_frequency_min () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_min_freq"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > $FLROOT/cpu$CORE/cpufreq/scaling_min_freq
  fi
}

function get_frequency_max () {
  if [ -z $CORE ]; then CORE=0; fi
  cat $FLROOT/cpu$CORE/cpufreq/scaling_max_freq
}

function set_frequency_max () {
  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/cpufreq/scaling_max_freq"
      write_value
      i=`expr $i + 1`
    done
  else echo $VALUE > $FLROOT/cpu$CORE/cpufreq/scaling_max_freq
  fi
}

function get_frequency_min_limit () {
  if [ -z $CORE ]; then CORE=0; fi
  cat $FLROOT/cpu$CORE/cpufreq/cpuinfo_min_freq
}

function get_frequency_max_limit () {
  if [ -z $CORE ]; then CORE=0; fi
  cat $FLROOT/cpu$CORE/cpufreq/cpuinfo_max_freq
}

function get_energy_performance_preference () {
  if [ -z $CORE ]; then
    i=0
    ag=''
    while [ $i -ne $cpucount ]; do
      if [ $i = 0 ]; then
        ag=`cat $FLROOT/cpu0/cpufreq/energy_performance_preference`
      else
        ag=$ag' '`cat $FLROOT/cpu$i/cpufreq/energy_performance_preference`
      fi
      i=`expr $i + 1`
    done
    echo $ag
  else cat $FLROOT/cpu$CORE/cpufreq/energy_performance_preference
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
  else echo $VALUE > $FLROOT/cpu$CORE/cpufreq/energy_performance_preference
  fi
}


function get_energy_performance_bias () {
  if [ -z $CORE ]; then
    i=0
    ag=''
    while [ $i -ne $cpucount ]; do
      if [ $i = 0 ]; then
        ag=`cat $FLROOT/cpu0/power/energy_perf_bias`
      else
        ag=$ag' '`cat $FLROOT/cpu$i/power/energy_perf_bias`
      fi
      i=`expr $i + 1`
    done
    echo $ag
  else cat $FLROOT/cpu$CORE/power/energy_perf_bias
  fi
}

function set_energy_performance_bias () {
  if [ `driver` != 'intel_pstate' ]; then
    verbose "EPB is not supported by a driver other than intel_pstate"
    return
  fi
  local EPB_VALUE=6 # default value
  if [[ "$VALUE" =~ ^[0-9]+$ && $VALUE -ge 0 && $VALUE -le 15 ]]; then
    EPB_VALUE=$VALUE
  else
    case $VALUE in
      performance) EPB_VALUE=0;;
      balance_performance) EPB_VALUE=4;;
      default) EPB_VALUE=6;;
      balance_power) EPB_VALUE=8;;
      power) EPB_VALUE=15;;
      *)
        verbose "Invalid value provided for EPB"
        verbose "Acceptable values: performance|balance-power|default|balance-power|power or a number in the range [0-15]"
        return
      ;;
    esac
  fi

  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/power/energy_perf_bias"
      if [ -w $FLNM ]; then echo $EPB_VALUE > $FLNM; fi
      i=`expr $i + 1`
    done
  else echo $EPB_VALUE > $FLROOT/cpu$CORE/power/energy_perf_bias
  fi
}

case $OPTION in
  -h|--help) help;;
  --version) echo $VERSION;;
  -d|--driver) driver;;
  -g|--governor)
    if [ ! -z $AVAILABLE ]; then cat $FLROOT/cpu0/cpufreq/scaling_available_governors
    elif [ -z $VALUE ]; then
      verbose "Getting CPU"$CORE" governors"
      get_governor
    else
      verbose "Setting CPU"$CORE" governors to "$VALUE
      set_governor
    fi
  ;;
  -e|--epp)
    if [ ! -z $AVAILABLE ]; then cat $FLROOT/cpu0/cpufreq/energy_performance_available_preferences
    elif [ -z $VALUE ]; then
      verbose "Getting CPU"$CORE" EPPs"
      get_energy_performance_preference
    else
      verbose "Setting CPU"$CORE" EPPs to "$VALUE
      set_energy_performance_preference
    fi
  ;;
  --epb)
    if [ ! -z $AVAILABLE ]; then cat $FLROOT/cpu0/power/energy_perf_bias
    elif [ -z $VALUE ]; then 
      verbose "Getting CPU"$CORE" EPBs"
      get_energy_performance_bias
    else
      verbose "Setting CPU"$CORE" EPBs to "$VALUE
      set_energy_performance_bias
    fi
  ;;
  -p|--pp)
    if [ ! -z $AVAILABLE ]; then cat $FWROOT/acpi/platform_profile_choices
    elif [ -z $VALUE ]; then
      verbose "Getting Platform Profile"
      cat $FWROOT/acpi/platform_profile
    else
      verbose "Getting Platform Profile to "$VALUE
      echo $VALUE > $FWROOT/acpi/platform_profile
    fi
  ;;
  -f|--frequency)
    if [ ! -z $AVAILABLE ]; then cat $FLROOT/cpu0/cpufreq/scaling_available_frequencies
    elif [ -z $VALUE ]; then
      verbose "Getting CPU"$CORE" frequency"
      get_frequency
    else
      verbose "Setting CPU"$CORE" frequency to "$VALUE
      set_frequency
    fi
  ;;
  --no-turbo)
    if [ -z $VALUE ]; then
      verbose "Getting no_turbo value"
      cat $FLROOT/intel_pstate/no_turbo
    else
      verbose "Setting no_turbo value "$VALUE
      echo $VALUE > $FLROOT/intel_pstate/no_turbo
    fi
  ;;
  -b|--boost)
    if [ -z $VALUE ]; then
      verbose "Getting boost value"
      cat $FLROOT/cpufreq/boost
    else
      verbose "Setting boost value "$VALUE
      echo $VALUE > $FLROOT/cpufreq/boost
    fi
  ;;
  --frequency-min)
    if [ -z $VALUE ]; then
      verbose "Getting CPU"$CORE" minimal frequency"
      get_frequency_min
    else
      verbose "Setting CPU"$CORE" minimal frequency to "$VALUE
      set_frequency_min
    fi
  ;;
  --frequency-max)
    if [ -z $VALUE ]; then
      verbose "Getting CPU"$CORE" maximal frequency"
      get_frequency_max
    else
      verbose "Setting CPU"$CORE" maximal frequency to "$VALUE
      set_frequency_max
    fi
  ;;
  --frequency-min-limit)
    verbose "Getting CPU"$CORE" minimal frequency limit"
    get_frequency_min_limit
  ;;
  --frequency-max-limit)
    verbose "Getting CPU"$CORE" maximum frequency limit"
    get_frequency_max_limit
  ;;
  --min-perf)
    if [ -z $VALUE ]; then
      verbose "Getting min_perf_pct value"
      cat $FLROOT/intel_pstate/min_perf_pct
    else
      verbose "Setting min_perf_pct value "$VALUE
      echo $VALUE > $FLROOT/intel_pstate/min_perf_pct
    fi
  ;;
  --max-perf)
    if [ -z $VALUE ]; then
      verbose "Getting max_perf_pct value"
      cat $FLROOT/intel_pstate/max_perf_pct
    else
      verbose "Setting max_perf_pct value "$VALUE
      echo $VALUE > $FLROOT/intel_pstate/max_perf_pct
    fi
  ;;
  --on)
    if [ -z $CORE ]; then verbose "Should be specify --core=NUMBER"
    else
      verbose "Power on CPU Core"$CORE
      echo "1" > $FLROOT/cpu"$CORE"/online
    fi
  ;;
  --off)
    if [ -z $CORE ]; then verbose "Should be specify --core=NUMBER"
    else
      verbose "Power off CPU Core$CORE"
      echo "0" > $FLROOT/cpu"$CORE"/online
    fi
  ;;
  --throttle)
    i=1
    V=0
    M=$(cat "$FLROOT/cpu0/thermal_throttle/core_throttle_count")
    while [ $i -ne $cpucount ]; do
      V=$(cat "$FLROOT/cpu$i/thermal_throttle/core_throttle_count")
      M=`expr $M + $V`
      i=`expr $i + 1`
    done
    echo "$M"
  ;;
  --throttle-events)
    M=$(journalctl --dmesg --boot --since=yesterday | grep "cpu clock throttled" | wc -l)
    echo "$M"
  ;;
  --irqbalance)
    M=$(ps -A | grep irqbalance)
    echo "$M"
  ;;
  *)
    info
    exit 1
  ;;
esac

exit 0
