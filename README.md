# auto-cpufreq

Automatic CPU speed & power optimizer for, Linux based on active monitoring of a laptop's battery state, CPU usage, CPU temperature and system load. Ultimately allowing you to improve battery life without making any compromises.

For tl;dr folks there's a: [Youtube: auto-cpufreq - tool demo](https://www.youtube.com/watch?v=QkYRpVEEIlg)

[![](http://img.youtube.com/vi/QkYRpVEEIlg/0.jpg)](http://www.youtube.com/watch?v=QkYRpVEEIlg)

## Looking for developers and co-maintainers

auto-cpufreq is looking for [co-maintainers & open source developers to help shape future of the project!](https://github.com/AdnanHodzic/auto-cpufreq/discussions/312)

## Index

* [Why do I need auto-cpufreq?](https://github.com/AdnanHodzic/auto-cpufreq/#why-do-i-need-auto-cpufreq)
    * [Supported architectures and devices](https://github.com/AdnanHodzic/auto-cpufreq/#supported-architectures-and-devices)
* [Features](https://github.com/AdnanHodzic/auto-cpufreq/#features)
* [Installing auto-cpufreq](https://github.com/AdnanHodzic/auto-cpufreq/#installing-auto-cpufreq)
    * [Snap store](https://github.com/AdnanHodzic/auto-cpufreq/#snap-store)
    * [auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq/#auto-cpufreq-installer)
    * [AUR package (Arch/Manjaro Linux)](https://github.com/AdnanHodzic/auto-cpufreq/#aur-package-archmanjaro-linux)
* [Post Installation]
* [Configuring auto-cpufreq](https://github.com/AdnanHodzic/auto-cpufreq/#configuring-auto-cpufreq)
    * [1: power_helper.py script](https://github.com/AdnanHodzic/auto-cpufreq/#1-power_helperpy-script)
    * [2: auto-cpufreq config file](https://github.com/AdnanHodzic/auto-cpufreq/#2-auto-cpufreq-config-file)
        * [Example config file contents](https://github.com/AdnanHodzic/auto-cpufreq/#example-config-file-contents)
* [How to run auto-cpufreq](https://github.com/AdnanHodzic/auto-cpufreq/#how-to-run-auto-cpufreq)
* [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq/#auto-cpufreq-modes-and-options)
    * [monitor](https://github.com/AdnanHodzic/auto-cpufreq/#monitor)
    * [live](https://github.com/AdnanHodzic/auto-cpufreq/#live)
    * [Install - auto-cpufreq daemon](https://github.com/AdnanHodzic/auto-cpufreq/#install---auto-cpufreq-daemon)
    * [Remove - auto-cpufreq daemon](https://github.com/AdnanHodzic/auto-cpufreq/#remove---auto-cpufreq-daemon)
    * [stats](https://github.com/AdnanHodzic/auto-cpufreq/#stats)
* [Troubleshooting](https://github.com/AdnanHodzic/auto-cpufreq/#troubleshooting)
* [Discussion](https://github.com/AdnanHodzic/auto-cpufreq/#discussion)
* [Donate](https://github.com/AdnanHodzic/auto-cpufreq/#donate)
    * [Financial donation](https://github.com/AdnanHodzic/auto-cpufreq/#financial-donation)
        * [Paypal](https://github.com/AdnanHodzic/auto-cpufreq/#paypal)
        * [BitCoin](https://github.com/AdnanHodzic/auto-cpufreq/#bitcoin)
    * [Code contribution](https://github.com/AdnanHodzic/auto-cpufreq/#code-contribution)

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

* Fedora users will [encounter following error](https://twitter.com/killyourfm/status/1291697985236144130) due to `cgroups v2` [being in development](https://github.com/snapcore/snapd/pull/7825). This problem can be resolved by either running `sudo snap run auto-cpufreq` after the snap installation or by using the [auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq/#auto-cpufreq-installer) which doesn't have this issue.

### auto-cpufreq-installer

Get source code, run installer and follow on screen instructions:

```
git clone https://github.com/AdnanHodzic/auto-cpufreq.git
cd auto-cpufreq && sudo ./auto-cpufreq-installer
```

In case you encounter any problems with `auto-cpufreq-installer`, please [submit a bug report](https://github.com/AdnanHodzic/auto-cpufreq/issues/new).

### AUR package (Arch/Manjaro Linux)

* [Binary Package](https://aur.archlinux.org/packages/auto-cpufreq)
(For the latest binary release on github)
* [Git Package](https://aur.archlinux.org/packages/auto-cpufreq-git)
(For the latest commits/changes) \
Please note that this git package is currently unmaintained & has issues. Until someone starts maintaining it, use the [manual script installer](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-installer) if you intend to have the latest changes.

## Post Installation
After installation `auto-cpufreq` will be available as a binary and you can refer to [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-modes-and-options) for more information on how to run and configure `auto-cpufreq`.

## Configuring auto-cpufreq

auto-cpufreq makes all decisions automatically based on various factors like cpu usage, temperature or system load. However, it's possible to perform additional configurations in 2 ways:

### 1: power_helper.py script

If detected as running, auto-cpufreq will disable [GNOME Power profiles service](https://twitter.com/fooctrl/status/1467469508373884933), which would otherwise cause conflicts and cause problems.

By default auto-cpufreq uses `balanced` mode which works the best on various systems. However, if you're not reaching maximum frequencies your CPU is capable of with auto-cpufreq ([#361](https://github.com/AdnanHodzic/auto-cpufreq/issues/361)), you can switch to `performance` mode. Which will result in higher frequencies by default, but also results in higher energy use (battery consumption).

If you installed auto-cpufreq using [auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq/edit/master/README.md#auto-cpufreq-installer), you can switch to `performance` mode by running:

`sudo auto-cpufreq --install_performance`

Or if you installed auto-cpufreq using [Snap package](https://github.com/AdnanHodzic/auto-cpufreq/edit/master/README.md#snap-store) you can switch to `performance` mode by running:

`sudo python3 power_helper.py --gnome_power_disable performance`

**Please Note:**  
The `power_helper.py` script is located at `auto_cpufreq/power_helper.py`


After this step, all necessary changes will still be made automatically. However, if you wish to perform additional "manual" settings this can be done by following instructions explained in next step.

### 2: auto-cpufreq config file

You can configure seperate profiles for the battery and power supply. These profiles will let you pick which governor to use, and how and when turbo boost is enabled. The possible values for turbo boost behavior are `always`, `auto` and `never`. The default behavior is `auto`, which only kicks in during high load.

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

* [monitor](https://github.com/AdnanHodzic/auto-cpufreq/#monitor)
    - Monitor and see suggestions for CPU optimizations

* [live](https://github.com/AdnanHodzic/auto-cpufreq/#live)
    - Monitor and make (temp.) suggested CPU optimizations

* [install](https://github.com/AdnanHodzic/auto-cpufreq/#install---auto-cpufreq-daemon) / [remove](https://github.com/AdnanHodzic/auto-cpufreq/#remove---auto-cpufreq-daemon)
    - Install/remove daemon for (permanent) automatic CPU optimizations

* [install_performance](https://github.com/AdnanHodzic/auto-cpufreq/#1-power_helperpy-script)
    - Install daemon in "performance" mode.

* [stats](https://github.com/AdnanHodzic/auto-cpufreq/#stats)
    - View live stats of CPU optimizations made by daemon

* config TEXT
    - Use config file at defined path

* debug
    - Show debug info (include when submitting bugs)

* version
    - Show currently installed version

* [donate](https://github.com/AdnanHodzic/auto-cpufreq/#financial-donation)
    - To support the project

* help
    - Shows all of the above options

Running `auto-cpufreq --help` will print the same list of options as above. Read [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq/#auto-cpufreq-modes-and-options) for more details.

## auto-cpufreq modes and options

### Monitor

`sudo auto-cpufreq --monitor`

No changes are made to the system, and is solely made for demonstration purposes what auto-cpufreq could do differently for your system.

### Live

`sudo auto-cpufreq --live`

Necessary changes are temporarily made to the system which are lost with system reboot. This mode is made to evaluate what the system would behave with auto-cpufreq permanently running on the system.

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

You can also stop the service with:

`systemctl stop auto-cpufreq`

and stop it from persistenctly starting with:

`systemctl disable auto-cpufreq`

### Stats

If daemon has been installed, live stats of CPU/system load monitoring and optimization can be seen by running:

`auto-cpufreq --stats`

## Troubleshooting

**Q:** If after installing auto-cpufreq you're (still) experiencing:
* high CPU temperatures
* CPU is not scaling to minimum/maximum frequencies
* suboptimal CPU performance

**A:** If you're using `intel_pstate` CPU management driver consider changing it to: `acpi-cpufreq`.

This can be done by editing `/etc/default/grub` file and appending `intel_pstate=disable` to `GRUB_CMDLINE_LINUX_DEFAULT` line, followed by `sudo update-grub`

Example line change:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash intel_pstate=disable"
```

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
