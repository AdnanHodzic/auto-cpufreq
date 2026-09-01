#!/usr/bin/env bash

VERSION='20'
cpucount=`cat /proc/cpuinfo | grep processor | wc -l`
FLROOT=/sys/devices/system/cpu
FWROOT=/sys/firmware
PPROOT=/sys/class/platform-profile
DRIVER=auto
VERBOSE=0
WRITE_ERROR=0
WRITE_ERROR_REPORTED=0

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
  echo "  -p, --pp                    Platform profile options"
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
  echo
  echo "Platform profile examples"
  echo "      cpufreqctl --pp                 Get current platform profile"
  echo "      cpufreqctl --pp --available     List available platform profiles"
  echo "      cpufreqctl --pp --set=balanced  Set a platform profile"
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
  local TARGET_VALUE="${1:-$VALUE}"

  if [ -w "$FLNM" ]; then
    if [ $WRITE_ERROR_REPORTED -eq 0 ]; then
      if ! echo "$TARGET_VALUE" > "$FLNM"; then
        WRITE_ERROR=1
        WRITE_ERROR_REPORTED=1
      fi
    elif ! echo "$TARGET_VALUE" > "$FLNM" 2>/dev/null; then
      WRITE_ERROR=1
    fi
  fi
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
    return 1
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
  echo $(awk '{a[NR]=$1} END{if(a[1]<a[2]) print a[1]; else print a[2]}' $FLROOT/cpu$CORE/cpufreq/cpuinfo_min_freq $FLROOT/cpu$CORE/cpufreq/scaling_min_freq)
}

function get_frequency_max_limit () {
  if [ -z $CORE ]; then CORE=0; fi
  echo $(awk '{a[NR]=$1} END{if(a[1]>a[2]) print a[1]; else print a[2]}' $FLROOT/cpu$CORE/cpufreq/cpuinfo_max_freq $FLROOT/cpu$CORE/cpufreq/scaling_max_freq)
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
    return 1
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
        verbose "Acceptable values: performance|balance_performance|default|balance_power|power or a number in the range [0-15]"
        return 1
      ;;
    esac
  fi

  if [ -z $CORE ]; then
    i=0
    while [ $i -ne $cpucount ]; do
      FLNM="$FLROOT/cpu"$i"/power/energy_perf_bias"
      write_value "$EPB_VALUE"
      i=`expr $i + 1`
    done
  else echo $EPB_VALUE > $FLROOT/cpu$CORE/power/energy_perf_bias
  fi
}

function resolve_platform_profile_paths () {
  local devices=()
  local path

  PLATFORM_PROFILE_PATH=""
  PLATFORM_PROFILE_CHOICES_PATH=""
  PLATFORM_PROFILE_CHOICES_IS_AGGREGATE=0
  PLATFORM_PROFILE_MODERN_COUNT=0

  for path in "$PPROOT"/platform-profile-*; do
    if [ -d "$path" ]; then
      devices+=("$path")
    fi
  done
  PLATFORM_PROFILE_MODERN_COUNT=${#devices[@]}

  if [ ${#devices[@]} -eq 1 ] && [ -e "${devices[0]}/profile" ]; then
    PLATFORM_PROFILE_PATH="${devices[0]}/profile"
    if [ -e "${devices[0]}/choices" ]; then
      PLATFORM_PROFILE_CHOICES_PATH="${devices[0]}/choices"
    elif [ -e "$FWROOT/acpi/platform_profile_choices" ]; then
      PLATFORM_PROFILE_CHOICES_PATH="$FWROOT/acpi/platform_profile_choices"
      PLATFORM_PROFILE_CHOICES_IS_AGGREGATE=1
    fi
    return 0
  fi

  # With multiple handlers, keep using the kernel's aggregate compatibility
  # interface so one config value is never applied to only one provider.
  if [ -e "$FWROOT/acpi/platform_profile" ]; then
    PLATFORM_PROFILE_PATH="$FWROOT/acpi/platform_profile"
    if [ -e "$FWROOT/acpi/platform_profile_choices" ]; then
      PLATFORM_PROFILE_CHOICES_PATH="$FWROOT/acpi/platform_profile_choices"
      PLATFORM_PROFILE_CHOICES_IS_AGGREGATE=1
    fi
    return 0
  fi

  return 1
}

function get_common_modern_platform_profiles () {
  local common=()
  local next=()
  local initialized=0
  local path
  local choices
  local choice
  local candidate
  local found

  for path in "$PPROOT"/platform-profile-*; do
    [ -d "$path" ] || continue
    [ -e "$path/choices" ] || return 1

    if ! choices=$(cat "$path/choices" 2>/dev/null); then
      return 1
    fi

    if [ $initialized -eq 0 ]; then
      for choice in $choices; do
        if [ "$choice" != "custom" ]; then
          common+=("$choice")
        fi
      done
      initialized=1
      continue
    fi

    next=()
    for candidate in "${common[@]}"; do
      found=0
      for choice in $choices; do
        if [ "$candidate" = "$choice" ]; then
          found=1
          break
        fi
      done
      if [ $found -eq 1 ]; then
        next+=("$candidate")
      fi
    done
    common=("${next[@]}")
  done

  if [ $initialized -eq 0 ]; then
    return 1
  fi

  # An empty intersection is a known result: there is no profile that can be
  # applied safely to every handler.
  echo "${common[*]}"
}

function resolve_available_platform_profiles () {
  AVAILABLE_PLATFORM_PROFILES=""

  local choices
  local choice
  local filtered=()

  if [ -n "$PLATFORM_PROFILE_CHOICES_PATH" ] && \
     choices=$(cat "$PLATFORM_PROFILE_CHOICES_PATH" 2>/dev/null); then
    if [ $PLATFORM_PROFILE_CHOICES_IS_AGGREGATE -eq 1 ]; then
      for choice in $choices; do
        if [ "$choice" != "custom" ]; then
          filtered+=("$choice")
        fi
      done
      AVAILABLE_PLATFORM_PROFILES="${filtered[*]}"
    else
      AVAILABLE_PLATFORM_PROFILES="$choices"
    fi
    return 0
  fi

  # Match the Python manager's fallback when a single modern handler has a
  # choices attribute that exists but cannot be read.
  if [ $PLATFORM_PROFILE_MODERN_COUNT -eq 1 ] && \
     [ $PLATFORM_PROFILE_CHOICES_IS_AGGREGATE -eq 0 ] && \
     [ -e "$FWROOT/acpi/platform_profile_choices" ]; then
    filtered=()
    if choices=$(cat "$FWROOT/acpi/platform_profile_choices" 2>/dev/null); then
      for choice in $choices; do
        if [ "$choice" != "custom" ]; then
          filtered+=("$choice")
        fi
      done
      AVAILABLE_PLATFORM_PROFILES="${filtered[*]}"
      return 0
    fi
  fi

  # With multiple handlers, fall back to the intersection of the per-handler
  # choices if the aggregate choices attribute is missing or unreadable.
  if [ $PLATFORM_PROFILE_MODERN_COUNT -gt 1 ] && \
     [ "$PLATFORM_PROFILE_PATH" = "$FWROOT/acpi/platform_profile" ]; then
    if AVAILABLE_PLATFORM_PROFILES=$(get_common_modern_platform_profiles); then
      return 0
    fi
  fi

  AVAILABLE_PLATFORM_PROFILES=""
  return 1
}

function get_platform_profile () {
  resolve_platform_profile_paths || return 1
  cat "$PLATFORM_PROFILE_PATH"
}

function get_available_platform_profiles () {
  resolve_platform_profile_paths || return 1
  resolve_available_platform_profiles || return 1
  echo "$AVAILABLE_PLATFORM_PROFILES"
}

function set_platform_profile () {
  resolve_platform_profile_paths || {
    echo "Platform Profile is not available on this system" >&2
    return 1
  }

  local current_profile
  if ! current_profile=$(cat "$PLATFORM_PROFILE_PATH" 2>/dev/null) || [ -z "$current_profile" ]; then
    echo "Platform Profile current state could not be read; no change was made" >&2
    return 1
  fi

  local choice
  local available=0

  if resolve_available_platform_profiles; then
    for choice in $AVAILABLE_PLATFORM_PROFILES; do
      if [ "$choice" = "$VALUE" ]; then
        available=1
        break
      fi
    done

    if [ $available -eq 0 ]; then
      echo "Platform Profile '$VALUE' is not available (available: $AVAILABLE_PLATFORM_PROFILES)" >&2
      return 1
    fi
  elif [ "$current_profile" != "$VALUE" ]; then
    echo "Platform Profile '$VALUE' was not changed because available profiles could not be determined" >&2
    return 1
  fi

  # A no-op is safe with missing choices only after any available choices have
  # been consulted. This keeps aggregate `custom` invalid even when it happens
  # to be the current aggregate state.
  if [ "$current_profile" = "$VALUE" ]; then
    return 0
  fi

  if ! echo "$VALUE" > "$PLATFORM_PROFILE_PATH"; then
    echo "Failed to write Platform Profile '$VALUE'" >&2
    return 1
  fi

  local applied_profile
  if ! applied_profile=$(cat "$PLATFORM_PROFILE_PATH" 2>/dev/null); then
    echo "Platform Profile '$VALUE' was written but the resulting state could not be read" >&2
    return 1
  fi

  if [ "$applied_profile" != "$VALUE" ]; then
    echo "Platform Profile '$VALUE' was not applied (current: $applied_profile)" >&2
    return 1
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
    if [ ! -z $AVAILABLE ]; then
      get_available_platform_profiles
    elif [ -z $VALUE ]; then
      verbose "Getting Platform Profile"
      get_platform_profile
    else
      verbose "Setting Platform Profile to $VALUE"
      set_platform_profile
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
    if [ -z "$CORE" ]; then
      verbose "Should be specify --core=NUMBER"
      false
    else
      verbose "Power on CPU Core"$CORE
      echo "1" > $FLROOT/cpu"$CORE"/online
    fi
  ;;
  --off)
    if [ -z "$CORE" ]; then
      verbose "Should be specify --core=NUMBER"
      false
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

COMMAND_STATUS=$?

if [ -n "$VALUE" ] || [ "$OPTION" = "--on" ] || [ "$OPTION" = "--off" ]; then
  if [ $WRITE_ERROR -ne 0 ]; then
    exit $WRITE_ERROR
  fi

  exit $COMMAND_STATUS
fi

exit 0
