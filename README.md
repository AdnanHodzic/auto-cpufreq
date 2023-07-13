# auto-cpufreq

Automatic CPU speed & power optimizer for, Linux based on active monitoring of a laptop's battery state, CPU usage, CPU temperature and system load. Ultimately allowing you to improve battery life without making any compromises.

For tl;dr folks there's a: [Youtube: auto-cpufreq - tool demo](https://www.youtube.com/watch?v=QkYRpVEEIlg)

[![](http://img.youtube.com/vi/QkYRpVEEIlg/0.jpg)](http://www.youtube.com/watch?v=QkYRpVEEIlg)

## Looking for developers and co-maintainers

auto-cpufreq is looking for [co-maintainers & open source developers to help shape future of the project!](https://github.com/AdnanHodzic/auto-cpufreq/discussions/312)

## Index

* [Why do I need auto-cpufreq?](#why-do-i-need-auto-cpufreq)
    * [Supported architectures and devices](#supported-architectures-and-devices)
* [Features](#features)
* [Installing auto-cpufreq](#installing-auto-cpufreq)
    * [Snap store](#snap-store)
    * [auto-cpufreq-installer](#auto-cpufreq-installer)
    * [AUR package (Arch/Manjaro Linux)](#aur-package-archmanjaro-linux)
* [Post Installation](#post-installation)
* [Configuring auto-cpufreq](#configuring-auto-cpufreq)
    * [1: power_helper.py script (Snap package install only)](#1-power_helperpy-script-snap-package-install-only)
    * [2: `--force` governor override](#2---force-governor-override)
    * [3: auto-cpufreq config file](#3-auto-cpufreq-config-file)
        * [Example config file contents](#example-config-file-contents)
* [How to run auto-cpufreq](#how-to-run-auto-cpufreq)
* [auto-cpufreq modes and options](#auto-cpufreq-modes-and-options)
    * [monitor](#monitor)
    * [live](#live)
    * [overriding governor](#overriding-governor)
    * [Install - auto-cpufreq daemon](#install---auto-cpufreq-daemon)
    * [Remove - auto-cpufreq daemon](#remove---auto-cpufreq-daemon)
    * [stats](#stats)
* [Troubleshooting](#troubleshooting)
    * [AUR](#aur)
* [Discussion](#discussion)
* [Donate](#donate)
    * [Financial donation](#financial-donation)
        * [Paypal](#paypal)
        * [BitCoin](#bitcoin)
    * [Code contribution](#code-contribution)

## Why do I need auto-cpufreq?

One of the problems with Linux today on laptops is that the CPU will run in an unoptimized manner which will negatively reflect on battery life. For example, the CPU will run using "performance" governor with turbo boost enabled regardless if it's plugged in to power or not.

These issues can be mitigated by using tools like [indicator-cpufreq](https://itsfoss.com/cpufreq-ubuntu/) or [cpufreq](https://github.com/konkor/cpufreq), but these still require manual action from your side which can be daunting and cumbersome.

Using tools like [TLP](https://github.com/linrunner/TLP) can help in this situation with extending battery life (which is something I used to do for numerous years), but it also might come with its own set of problems, like losing turbo boost.

With that said, I needed a simple tool which would automatically make "cpufreq" related changes, save battery like TLP, but let Linux kernel do most of the heavy lifting. That's how auto-cpufreq was born.

Please note: auto-cpufreq aims to replace TLP in terms of functionality and after you install auto-cpufreq _it's recommended to remove TLP_. If both are used for same functionality, i.e: to set CPU frequencies it'll lead to unwanted results like overheating. Hence, only use [both tools in tandem](https://github.com/AdnanHodzic/auto-cpufreq/discussions/176) if you know what you're doing.

The Tool/daemon that does not conflict with auto-cpufreq in any way, and is even recommended to have running alongside, is [thermald](https://wiki.debian.org/thermald).

#### Supported architectures and devices

Supported devices must have an Intel, AMD or ARM CPUs. This tool was developed to improve performance and battery life on laptops, but running it on desktop/servers (to lower power consumption) should also be possible.

## Features

* Monitoring
  * Basic system information
  * CPU frequency (system total & per core)
  * CPU usage (system total & per core)
  * CPU temperature (total average & per core)
  * Battery state
  * System load
* CPU frequency scaling, governor and [turbo boost](https://en.wikipedia.org/wiki/Intel_Turbo_Boost) management based on
  * Battery state
  * CPU usage (total & per core)
  * CPU temperature in combination with CPU utilization/load (prevent overheating)
  * System load
* Automatic CPU & power optimization (temporary and persistent)

## Installing auto-cpufreq

### Snap store

auto-cpufreq is available on the [snap store](https://snapcraft.io/auto-cpufreq), or can be installed using CLI:

```
sudo snap install auto-cpufreq
```

**Please note:**
* Make sure [snapd](https://snapcraft.io/docs/installing-snapd) is installed and `snap version` version is >= 2.44 for `auto-cpufreq` to fully work due to [recent snapd changes](https://github.com/snapcore/snapd/pull/8127).

* Fedora users will [encounter following error](https://twitter.com/killyourfm/status/1291697985236144130) due to `cgroups v2` [being in development](https://github.com/snapcore/snapd/pull/7825). This problem can be resolved by either running `sudo snap run auto-cpufreq` after the snap installation or by using the [auto-cpufreq-installer](#auto-cpufreq-installer) which doesn't have this issue.

### auto-cpufreq-installer

Get source code, run installer and follow on screen instructions:

```
git clone https://github.com/AdnanHodzic/auto-cpufreq.git
cd auto-cpufreq && sudo ./auto-cpufreq-installer
```

In case you encounter any problems with `auto-cpufreq-installer`, please [submit a bug report](https://github.com/AdnanHodzic/auto-cpufreq/issues/new).

### AUR package (Arch/Manjaro Linux)

*AUR is currently unmaintained & has issues*! Until someone starts maintaining it, use the [auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-installer) if you intend to have the latest changes as otherwise you'll run into errors, i.e: [#471](https://github.com/AdnanHodzic/auto-cpufreq/issues/471). However, if you still wish to use AUR then follow the [Troubleshooting](#aur) section for solved known issues.

* [Binary Package](https://aur.archlinux.org/packages/auto-cpufreq)
(For the latest binary release on github)
* [Git Package](https://aur.archlinux.org/packages/auto-cpufreq-git)
(For the latest commits/changes)

## Post Installation
After installation `auto-cpufreq` will be available as a binary and you can refer to [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-modes-and-options) for more information on how to run and configure `auto-cpufreq`.

## Configuring auto-cpufreq

auto-cpufreq makes all decisions automatically based on various factors like cpu usage, temperature or system load. However, it's possible to perform additional configurations:

### 1: power_helper.py script (Snap package install **only**)

When installing auto-cpufreq using [auto-cpufreq-installer](#auto-cpufreq-installer) if it detects [GNOME Power profiles service](https://twitter.com/fooctrl/status/1467469508373884933) is running it will automatically disable it. Otherwise this daemon will cause conflicts and various other performance issues.

However, when auto-cpufreq is installed as Snap package it's running as part of a container with limited permissions to your host machine, hence it's *highly recommended* you disable GNOME Power Profiles Daemon using `power_helper.py` script.

**Please Note:**<br>
The [`power_helper.py`](https://github.com/AdnanHodzic/auto-cpufreq/blob/master/auto_cpufreq/power_helper.py) script is located at `auto_cpufreq/power_helper.py`. In order to have access to it, you need to first clone
the repository:

`git clone https://github.com/AdnanHodzic/auto-cpufreq`

Navigate to repo location where `power_helper.py` resides, i.e:

`cd auto-cpufreq/auto_cpufreq`

Make sure to have `psutil` Python library installed before next step, i.e: `sudo python3 -m pip install psutil`

Then disable GNOME Power Profiles Daemon by running:

`sudo python3 power_helper.py --gnome_power_disable`

### 2: `--force` governor override

By default auto-cpufreq uses `balanced` mode which works the best on various systems and situations.

However, you can override this behaviour by switching to `performance` or `powersave` mode manually. Performance will result in higher frequencies by default, but also results in higher energy use (battery consumption) and should be used if max performance is necessary. Otherwise `powersave` will do the opposite and extend the battery life to its maximum.

See [`--force` flag](#overriding-governor) for more info.

### 3: auto-cpufreq config file

You can configure separate profiles for the battery and power supply. These profiles will let you pick which governor to use, and how and when turbo boost is enabled. The possible values for turbo boost behavior are `always`, `auto` and `never`. The default behavior is `auto`, which only kicks in during high load.

By default, auto-cpufreq does not use the config file! If you wish to use it, the location where config needs to be placed for it to be read automatically is: `/etc/auto-cpufreq.conf`

#### Example config file contents
```
# settings for when connected to a power source
[charger]
# see available governors by running: cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
# preferred governor.
governor = performance

# minimum cpu frequency (in kHz)
# example: for 800 MHz = 800000 kHz --> scaling_min_freq = 800000
# see conversion info: https://www.rapidtables.com/convert/frequency/mhz-to-hz.html
# to use this feature, uncomment the following line and set the value accordingly
# scaling_min_freq = 800000

# maximum cpu frequency (in kHz)
# example: for 1GHz = 1000 MHz = 1000000 kHz -> scaling_max_freq = 1000000
# see conversion info: https://www.rapidtables.com/convert/frequency/mhz-to-hz.html
# to use this feature, uncomment the following line and set the value accordingly
# scaling_max_freq = 1000000

# turbo boost setting. possible values: always, auto, never
turbo = auto

# settings for when using battery power
[battery]
# see available governors by running: cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
# preferred governor
governor = powersave

# minimum cpu frequency (in kHz)
# example: for 800 MHz = 800000 kHz --> scaling_min_freq = 800000
# see conversion info: https://www.rapidtables.com/convert/frequency/mhz-to-hz.html
# to use this feature, uncomment the following line and set the value accordingly
# scaling_min_freq = 800000

# maximum cpu frequency (in kHz)
# see conversion info: https://www.rapidtables.com/convert/frequency/mhz-to-hz.html
# example: for 1GHz = 1000 MHz = 1000000 kHz -> scaling_max_freq = 1000000
# to use this feature, uncomment the following line and set the value accordingly
# scaling_max_freq = 1000000

# turbo boost setting. possible values: always, auto, never
turbo = auto
```

## How to run auto-cpufreq
auto-cpufreq should be run with with one of the following options:

* [monitor](#monitor)
    - Monitor and see suggestions for CPU optimizations

* [live](#live)
    - Monitor and make (temp.) suggested CPU optimizations

* [install](#install---auto-cpufreq-daemon) / [remove](#remove---auto-cpufreq-daemon)
    - Install/remove daemon for (permanent) automatic CPU optimizations

* [install_performance](#1-power_helperpy-script)
    - Install daemon in "performance" mode.

* [stats](#stats)
    - View live stats of CPU optimizations made by daemon

* [force=TEXT](#overriding-governor)
    - Force use of either the "powersave" or "performance" governor. Setting to "reset" goes back to normal mode

* config=TEXT
    - Use config file at defined path

* debug
    - Show debug info (include when submitting bugs)

* version
    - Show currently installed version

* [donate](#financial-donation)
    - To support the project

* help
    - Shows all of the above options

Running `auto-cpufreq --help` will print the same list of options as above. Read [auto-cpufreq modes and options](#auto-cpufreq-modes-and-options) for more details.

## auto-cpufreq modes and options

### Monitor

`sudo auto-cpufreq --monitor`

No changes are made to the system, and is solely made for demonstration purposes what auto-cpufreq could do differently for your system.

### Live

`sudo auto-cpufreq --live`

Necessary changes are temporarily made to the system which are lost with system reboot. This mode is made to evaluate what the system would behave with auto-cpufreq permanently running on the system.

### Overriding governor

`sudo auto-cpufreq --force=governor`

Force use of either "powersave" or "performance" governors. Setting to "reset" will go back to normal mode
Please note that any set override will persist even after reboot.

### Install - auto-cpufreq daemon

Necessary changes are made to the system for auto-cpufreq CPU optimization to persist across reboots. The daemon is deployed and then started as a systemd service. Changes are made automatically and live stats are generated for monitoring purposes.

Install the daemon using this command (after installing auto-cpufreq):

`sudo auto-cpufreq --install`

This will enable the auto-cpufreq service (equivalent to `systemctl enable auto-cpufreq`) to start on boot, and start it (equivalent to `systemctl start auto-cpufreq`).

After the daemon is installed, `auto-cpufreq` is available as a binary and is running in the background. Its stats can be viewed by running: `auto-cpufreq --stats`

Since daemon is running as a systemd service, its status can be seen by running:

`systemctl status auto-cpufreq`

If the install has been performed as part of snap package, daemon status can be verified by running:

`systemctl status snap.auto-cpufreq.service.service`

### Remove - auto-cpufreq daemon

auto-cpufreq daemon and its systemd service, along with all its persistent changes can be removed by running:

`sudo auto-cpufreq --remove`

This does the equivalent of `systemctl stop auto-cpufreq && systemctl disable auto-cpufreq`.

Note that the given command should be used instead of using just `systemctl`.

### Stats

If daemon has been installed, live stats of CPU/system load monitoring and optimization can be seen by running:

`auto-cpufreq --stats`

## Troubleshooting

**Q:** If after installing auto-cpufreq you're (still) experiencing:
* high CPU temperatures
* CPU is not scaling to minimum/maximum frequencies
* suboptimal CPU performance

**A:** If you're using `intel_pstate/amd-pstate` CPU management driver, consider changing it to `acpi-cpufreq`.

This can be done by editing the `GRUB_CMDLINE_LINUX_DEFAULT` params in `/etc/default/grub`. For instance:

```
    sudo nano /etc/default/grub
    # make sure you have nano installed, or you can use your favorite text editor.
```

For Intel users:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash intel_pstate=disable"
```

For AMD users:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash initcall_blacklist=amd_pstate_init amd_pstate.enable=0"
```

Once you have made the necessary changes to the GRUB configuration file, you can update it by running `sudo update-grub` or `sudo grub-mkconfig -o /boot/grub/grub.cfg` on Arch Linux. On the other hand, for Fedora, you can update the configuration file by running one of the following commands:

```
    sudo grub2-mkconfig -o /etc/grub2.cfg
```

```
    sudo grub2-mkconfig -o /etc/grub2-efi.cfg
```

```
    sudo grub2-mkconfig -o /boot/grub2/grub.cfg
    # Legacy boot method for grub update.
```

### AUR

* The command ```sudo auto-cpufreq --install``` produces error [#471](https://github.com/AdnanHodzic/auto-cpufreq/issues/471) please don't use it.
    * This script is supposed to automate the process of enabling auto-cpufreq.service so you need to manually open terminal and type
    ~~~
    sudo systemctl enable --now auto-cpufreq.service
    ~~~
    for the service to work.
* Power Profiles Daemon is [automatically disabled by auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq#1-power_helperpy-script-snap-package-install-only) due to it's conflict with auto-cpufreq.service. However this doesn't happen with AUR package and will lead to problems (i.e: [#463](https://github.com/AdnanHodzic/auto-cpufreq/issues/463)) if not masked manually.
    * So open your terminal and type
    ~~~
    sudo systemctl mask power-profiles-daemon.service
    ~~~
    Following this command ```enable``` the auto-cpufreq.service if you haven't already.

## Discussion:

* Blogpost: [auto-cpufreq - Automatic CPU speed & power optimizer for Linux](http://foolcontrol.org/?p=3124)

## Donate

Showing your support and appreciation for auto-cpufreq project can be done in two ways:

* Financial donation
* Code contribution

### Financial donation

If auto-cpufreq helped you out and you find it useful, show your appreciation by donating (any amount) to the project!

##### PayPal
[![paypal](https://www.paypalobjects.com/en_US/NL/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=7AHCP5PU95S4Y&item_name=Contribution+for+work+on+auto-cpufreq&currency_code=EUR&source=url)

##### BitCoin
[bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87](bitcoin:bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87)

[![bitcoin](https://foolcontrol.org/wp-content/uploads/2019/08/btc-donate-displaylink-debian.png)](bitcoin:bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87)

### Code contribution

Other ways of supporting the project consists of making a code or documentation contribution. If you have an idea for a new features or want to implement some of the existing feature requests or fix some of the [bugs & issues](https://github.com/AdnanHodzic/auto-cpufreq/issues) please make your changes and submit a [pull request](https://github.com/AdnanHodzic/auto-cpufreq/pulls) which I'll be glad to review. If your changes are accepted you'll be credited as part of [releases page](https://github.com/AdnanHodzic/auto-cpufreq/releases).

**Please note: auto-cpufreq is looking for co-maintainers & open source developers to [help shape future of the project!](https://github.com/AdnanHodzic/auto-cpufreq/discussions/312)**
