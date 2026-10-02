#!/usr/bin/env bash
#
# auto-cpufreq daemon install script
# reference: https://github.com/AdnanHodzic/auto-cpufreq
# Thanks to https://github.com/errornonamer for openrc fix

MID="$((`tput cols` / 2))"
SHARE_DIR=/opt/auto-cpufreq/current/share
[ -d "$SHARE_DIR/scripts" ] || SHARE_DIR=/usr/local/share/auto-cpufreq

echo
printf "%0.s─" $(seq $(( (MID-(${#1}/2)-2) / 2 )))
printf " Running auto-cpufreq daemon install script "
printf "%0.s─" $(seq $(( (MID-(${#1}/2)-2) / 2 )))
echo; echo

# root check
if ((EUID != 0)); then
  echo; echo "Must be run as root (i.e: 'sudo $0')."; echo
  exit 1
fi

# First argument is the init name, second argument is the start command, third argument is the enable command
function auto_cpufreq_install {
    echo -e "\n* Enabling auto-cpufreq daemon ($1) at boot"
    [ -z "${3:-}" ] || $3 || return $?
    echo -e "\n* Starting auto-cpufreq daemon ($1) service"
    [ -z "${2:-}" ] || $2 || return $?
}

function publish_service_file {
    (
      local source="$1" target="$2" mode="$3" staging_parent="$4"
      local staged_file

      staged_file="$(mktemp "$staging_parent/.auto-cpufreq.XXXXXXXX")" || exit $?
      trap 'rm -f -- "$staged_file"' EXIT
      cp -- "$source" "$staged_file" || exit $?
      chmod "$mode" "$staged_file" || exit $?
      # Publish only complete files, without replacing a target created since
      # ownership validation. A failed copy must not poison the next retry.
      ln -T -- "$staged_file" "$target" || exit $?
    )
}

function directory_contains_only {
    local allowed allowed_name entry
    local directory="$1"
    shift

    for entry in "$directory"/* "$directory"/.[!.]* "$directory"/..?*; do
      [ -e "$entry" ] || [ -L "$entry" ] || continue
      allowed=false
      for allowed_name in "$@"; do
        if [ "${entry##*/}" = "$allowed_name" ]; then
          allowed=true
          break
        fi
      done
      $allowed || return 1
    done
    return 0
}

function runit_service_is_managed {
    local managed_run="$SHARE_DIR/scripts/auto-cpufreq-runit"
    local service_dir="$1"

    [ -e "$service_dir" ] || [ -L "$service_dir" ] || return 0
    [ -d "$service_dir" ] && [ ! -L "$service_dir" ] || return 1
    directory_contains_only "$service_dir" run supervise || return 1

    if [ -e "$service_dir/run" ] || [ -L "$service_dir/run" ]; then
      [ -f "$service_dir/run" ] \
        && [ ! -L "$service_dir/run" ] \
        && cmp -s -- "$managed_run" "$service_dir/run" \
        || return 1
    elif [ -e "$service_dir/supervise" ] || [ -L "$service_dir/supervise" ]; then
      return 1
    fi

    [ ! -e "$service_dir/supervise" ] \
      && [ ! -L "$service_dir/supervise" ] \
      || [ -d "$service_dir/supervise" ]
}

function s6_service_is_managed {
    local managed_dir="$SHARE_DIR/scripts/auto-cpufreq-s6"
    local service_dir="$1"
    local service_file

    [ -e "$service_dir" ] || [ -L "$service_dir" ] || return 0
    [ -d "$service_dir" ] && [ ! -L "$service_dir" ] || return 1
    directory_contains_only "$service_dir" run type || return 1

    for service_file in run type; do
      if [ -e "$service_dir/$service_file" ] \
        || [ -L "$service_dir/$service_file" ]; then
        [ -f "$service_dir/$service_file" ] \
          && [ ! -L "$service_dir/$service_file" ] \
          && cmp -s -- "$managed_dir/$service_file" "$service_dir/$service_file" \
          || return 1
      fi
    done
    return 0
}

case "$(ps h -o comm 1)" in
  dinit) 
    echo -e "\n* Deploying auto-cpufreq (dinit) unit file"
    cp "$SHARE_DIR/scripts/auto-cpufreq-dinit" /etc/dinit.d/auto-cpufreq || exit $?

    auto_cpufreq_install "dinit" "dinitctl start auto-cpufreq" "dinitctl enable auto-cpufreq" || exit $?
  ;;
  init) 
    echo -e "\n* Deploying auto-cpufreq openrc unit file"
    cp "$SHARE_DIR/scripts/auto-cpufreq-openrc" /etc/init.d/auto-cpufreq || exit $?
    chmod +x /etc/init.d/auto-cpufreq || exit $?

    auto_cpufreq_install "openrc" "rc-service auto-cpufreq start" "rc-update add auto-cpufreq" || exit $?
  ;;
  runit)
    # First argument is the "sv" path, second argument is the "service" path
    runit_ln() {
      local active_link="$2/service/auto-cpufreq"
      local service_dir="$1/sv/auto-cpufreq"

      echo -e "\n* Deploying auto-cpufreq (runit) unit file"
      # A service directory is host configuration, not an opaque deployment
      # target. Reuse it only when it contains our run script and runit's own
      # supervision state; otherwise preserve the administrator's files.
      if ! runit_service_is_managed "$service_dir"; then
        echo "Error: Refusing to replace an unmanaged runit service path: $service_dir"
        return 1
      fi
      mkdir -p "$service_dir" || return $?
      if [ ! -e "$service_dir/run" ]; then
        # Keep staging outside the service directory so an interrupted copy
        # cannot leave an unexpected entry in an otherwise managed service.
        publish_service_file "$SHARE_DIR/scripts/auto-cpufreq-runit" \
          "$service_dir/run" 755 "$1/sv" || return $?
      fi
      chmod +x "$service_dir/run" || return $?

      echo -e "\n* Creating symbolic link ($active_link -> $service_dir)"
      if [ -L "$active_link" ]; then
        if [ "$(readlink "$active_link")" != "$service_dir" ]; then
          echo "Error: Refusing to replace an unmanaged runit service link: $active_link"
          return 1
        fi
      elif [ -e "$active_link" ]; then
        echo "Error: Refusing to replace an unmanaged runit service path: $active_link"
        return 1
      else
        ln -s "$service_dir" "$active_link" || return $?
      fi

      # `sv start` is the documented waiting form of `sv up`; one command is
      # sufficient both to request and verify that the service reached "up".
      sv start "$active_link" || return $?
    }

    if [ -f /etc/os-release ];then
      eval "$(cat /etc/os-release)"
      case $ID in
        void) runit_ln /etc /var || exit $?;;
        artix) runit_ln /etc/runit /run/runit || exit $?;;
        *)
          echo -e "\n* Runit init detected but your distro is not supported\n"
          echo -e "\n* Please open an issue on https://github.com/AdnanHodzic/auto-cpufreq\n"
          exit 1
      esac
    else
      echo -e "\n* Runit init detected but /etc/os-release is unavailable\n"
      exit 1
    fi
  ;;
  systemd)
    systemd_unit=/etc/systemd/system/auto-cpufreq.service
    managed_systemd_unit="$SHARE_DIR/scripts/auto-cpufreq.service"
    if [ -L "$systemd_unit" ] \
      || { [ -e "$systemd_unit" ] \
        && ! cmp -s -- "$managed_systemd_unit" "$systemd_unit"; }; then
      echo "Error: Refusing to replace an unmanaged systemd unit: $systemd_unit"
      exit 1
    fi
    if [ ! -e "$systemd_unit" ]; then
      echo -e "Deploying auto-cpufreq systemd unit file"
      publish_service_file "$managed_systemd_unit" "$systemd_unit" \
        644 /etc/systemd/system || exit $?
    fi

    echo -e "\n* Reloading systemd manager configuration"
    systemctl daemon-reload || exit $?

    auto_cpufreq_install "systemd" "systemctl start auto-cpufreq" "systemctl enable auto-cpufreq" || exit $?
  ;;
  s6-svscan)
    for required_command in flock s6-service s6-db-reload s6-rc; do
      if ! command -v "$required_command" > /dev/null 2>&1; then
        echo "Error: $required_command is required to install the auto-cpufreq s6 service."
        exit 1
      fi
    done
    s6_service_dir=/etc/s6/sv/auto-cpufreq
    s6_removing_dir=/etc/s6/sv/.auto-cpufreq-removing
    s6_bundle_entry=/etc/s6/adminsv/default/contents.d/auto-cpufreq
    # Installation and removal share the source-directory inode lock. Atomic
    # rename alone cannot serialize their multi-step bundle changes.
    exec 8</etc/s6/sv || exit $?
    if ! flock -n 8; then
      echo "Error: Another auto-cpufreq s6 lifecycle operation is in progress."
      exit 1
    fi
    if [ -e "$s6_removing_dir" ] || [ -L "$s6_removing_dir" ]; then
      echo "Error: An s6 removal is unfinished. Retry 'sudo auto-cpufreq --remove' first."
      exit 1
    fi
    echo -e "\n* Deploying auto-cpufreq (s6) unit file"
    if ! s6_service_is_managed "$s6_service_dir"; then
      echo "Error: Refusing to replace an unmanaged s6 service path: $s6_service_dir"
      exit 1
    fi
    if [ ! -f "$s6_service_dir/run" ] || [ ! -f "$s6_service_dir/type" ]; then
      (
        staged_dir="$(mktemp -d /etc/s6/sv/.auto-cpufreq-install.XXXXXXXX)" || exit $?
        trap 'rm -rf -- "$staged_dir"' EXIT
        cp -r "$SHARE_DIR/scripts/auto-cpufreq-s6/." "$staged_dir/" || exit $?
        chmod 755 "$staged_dir" || exit $?
        # s6-rc-compile ignores dot directories. Publish a new definition as
        # one rename, so another database build never sees half a service.
        if [ ! -e "$s6_service_dir" ]; then
          mv -T -- "$staged_dir" "$s6_service_dir" || exit $?
        else
          # Older attempts may have left a managed, incomplete directory.
          # Repair only missing files; never truncate its existing definition.
          for service_file in run type; do
            [ -e "$s6_service_dir/$service_file" ] || \
              ln -T -- "$staged_dir/$service_file" "$s6_service_dir/$service_file" || exit $?
          done
        fi
      ) || exit $?
    fi

    echo -e "\n* Add auto-cpufreq service (s6) to default bundle"
    if [ ! -e "$s6_bundle_entry" ] && [ ! -L "$s6_bundle_entry" ]; then
      s6-service add default auto-cpufreq 8<&- || exit $?
    fi

    echo -e "\n* Update daemon service bundle (s6)"
    s6-db-reload 8<&- || exit $?

    auto_cpufreq_install "s6" "s6-rc -u change auto-cpufreq default" 8<&- || exit $?
  ;;
  *)
    echo -e "\n* Unsupported init system detected, could not install the daemon\n"
    echo -e "\n* Please open an issue on https://github.com/AdnanHodzic/auto-cpufreq\n"
    exit 1
  ;;
esac
