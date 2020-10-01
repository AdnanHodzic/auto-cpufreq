# auto-cpufreq

Automatic CPU speed & power optimizer for Linux based on active monitoring of laptop's battery state, CPU usage and system load. Ultimately allowing you to improve battery life without making any compromises.

For tl;dr folks there's a: [Youtube: auto-cpufreq - tool demo](https://www.youtube.com/watch?v=QkYRpVEEIlg)

[![](http://img.youtube.com/vi/QkYRpVEEIlg/0.jpg)](http://www.youtube.com/watch?v=QkYRpVEEIlg"")


## Why do I need auto-cpufreq?

One of the problems with Linux today on laptops is that CPU will run in unoptimized manner which will negatively reflect on battery life. For example, CPU will run using "performance" governor with turbo boost enabled regardless if it's plugged in to power or not.

Issue can be mitigated by using tools like [indicator-cpufreq](https://itsfoss.com/cpufreq-ubuntu/) or [cpufreq](https://github.com/konkor/cpufreq), but these still require manual action from your side which can be daunting and cumbersome.

Using tools like [TLP](https://github.com/linrunner/TLP) will help in this situation with extending battery life (which is something I did for numerous years now), but it also might come with its own set of problems, like losing turbo boost.

With that said, I needed a simple tool which would automatically make "cpufreq" related changes, save battery like TLP, but let Linux kernel do most of the heavy lifting. That's how auto-cpufreq was born.

Please note: this tool doesn't conflict and [works great in tandem with TLP](https://www.reddit.com/r/linux/comments/ejxx9f/github_autocpufreq_automatic_cpu_speed_power/fd4y36k/).

#### Supported architectures and devices

Supported devices must have an Intel, AMD or ARM CPU's. This tool was developed to improve performance and battery life on laptops, but running it on desktop/servers (to lower power consumption) should also be possible. 

## Features

* Monitoring 
  * Basic system information
  * CPU frequency (system total & per core)
  * CPU usage (system total & per core)
  * Battery state
  * System load
* CPU frequency scaling, governor and [turbo boost](https://en.wikipedia.org/wiki/Intel_Turbo_Boost) management based on
  * battery state
  * CPU usage
  * System load
* Automatic CPU & power optimization (temporary and persistent)

## Installing auto-cpufreq

### Snap store

auto-cpufreq is available on [snap store](https://snapcraft.io/auto-cpufreq), or can be installed using CLI:

```
sudo snap install auto-cpufreq
```

**Please note:** 
* Make sure [snapd](https://snapcraft.io/docs/installing-snapd) is installed and `snap version` version is >= 2.44 for `auto-cpufreq` to fully work due to [recent snapd changes](https://github.com/snapcore/snapd/pull/8127).

* Fedora users will [encounter following error](https://twitter.com/killyourfm/status/1291697985236144130). Due to `cgroups v2` [being in development](https://github.com/snapcore/snapd/pull/7825). This problem can be resolved by either running `sudo snap run auto-cpufreq` after snap installation. Or using [auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq/#auto-cpufreq-installer) which doesn't have this issue.

### auto-cpufreq-installer

Get source code, run installer and follow on screen instructions:

```
git clone https://github.com/AdnanHodzic/auto-cpufreq.git
cd auto-cpufreq && sudo ./auto-cpufreq-installer
```

In case you encounter any problems with `auto-cpufreq-installer`, please [submit a bug report](https://github.com/AdnanHodzic/auto-cpufreq/issues/new).

### AUR package (Arch/Manjaro Linux)

[AUR package is available](https://aur.archlinux.org/packages/auto-cpufreq-git/) for install. After which `auto-cpufreq` will be available as a binary and you can refer to [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-modes-and-options).

**Please note:** If you want to install auto-cpufreq daemon, do not run `auto-cpufeq --install` otherwise you'll run into an issue: [#91](https://github.com/AdnanHodzic/auto-cpufreq/issues/91), [#96](https://github.com/AdnanHodzic/auto-cpufreq/issues/96).

Instead run `systemctl start auto-cpufreq` to start the service. Run `systemctl status auto-cpufreq` to see the status of service, and `systemctl enable auto-cpufreq` for service to persist running accross reboots. 

## How to run auto-cpufreq

auto-cpufreq can be run by simply running the `auto-cpufreq` and following on screen instructions, i.e:

`sudo auto-cpufreq`

## auto-cpufreq modes and options

### Monitor

`sudo auto-cpufreq --monitor`

No changes are made to the system, and is solely made for demonstration purposes what auto-cpufreq could do differently for your system.

### Live

`sudo auto-cpufreq --live`

Necessary changes are temporarily made to the system which are lost with system reboot. This mode is made to evaluate what the system would behave with auto-cpufreq permanently running on the system.

### Install - auto-cpufreq daemon

Necessary changes are made to the system for auto-cpufreq CPU optimizaton to persist across reboots. Daemon is deployed and then started as a systemd service. Changes are made automatically and live log is made for monitoring purposes.

`sudo auto-cpufreq --install`

After daemon is installed, `auto-cpufreq` is available as a binary and is running in the background. Its logs can be viewed by running: `auto-cpufreq --log`

Since daemon is running as a systemd service, its status can be seen by running:

`systemctl status auto-cpufreq`

If install has been performed as part of snap package, daemon status can be verified by running: 

`systemctl status snap.auto-cpufreq.service.service`

### Remove - auto-cpufreq daemon

auto-cpufreq daemon and its systemd service, along with all its persistent changes can be removed by running:

`sudo auto-cpufreq --remove`

### Log

If daemon has been instaled, live log of CPU/system load monitoring and optimizaiton can be seen by running:

`auto-cpufreq --log`

## Discussion:

* Blogpost: [auto-cpufreq - Automatic CPU speed & power optimizer for Linux](http://foolcontrol.org/?p=3124)

## Donate

Since I'm working on this project in free time, please consider supporting this project by making a donation of any amount!

##### PayPal
[![paypal](https://www.paypalobjects.com/en_US/NL/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=7AHCP5PU95S4Y&item_name=Contribution+for+work+on+auto-cpufreq&currency_code=EUR&source=url)

##### BitCoin
[bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87](bitcoin:bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87)

[![bitcoin](https://foolcontrol.org/wp-content/uploads/2019/08/btc-donate-displaylink-debian.png)](bitcoin:bc1qlncmgdjyqy8pe4gad4k2s6xtyr8f2r3ehrnl87)
