# auto-cpufreq

Automatic CPU speed & power optimizer for Linux. Actively monitors laptop battery state, CPU usage, CPU temperature, and system load, ultimately allowing you to improve battery life without making any compromises.

For tl;dr folks:

[Youtube: auto-cpufreq v2.0 release & demo of all available features and options](https://www.youtube.com/watch?v=SPGpkZ0AZVU)

[![](https://img.youtube.com/vi/SPGpkZ0AZVU/0.jpg)](https://www.youtube.com/watch?v=QkYRpVEEIlg)

[Youtube: auto-cpufreq - tool demo](https://www.youtube.com/watch?v=QkYRpVEEIlg)

[![](https://img.youtube.com/vi/QkYRpVEEIlg/0.jpg)](https://www.youtube.com/watch?v=QkYRpVEEIlg)

Example of auto-cpufreq GUI (available >= v2.0)

<img src="http://foolcontrol.org/wp-content/uploads/2023/09/auto-cpufreq-v2-gui.png" width="480" alt="Example of auto-cpufreq desktop entry (icon)"/>

Example of `auto-cpufreq --stats` CLI output

<img src="https://foolcontrol.org/wp-content/uploads/2023/09/auto-cpufreq-CLI.png" width="480" alt="Example of auto-cpufreq desktop entry (icon)"/>

## Looking for developers and co-maintainers

* If you would like to discuss anything regarding auto-cpufreq or its development, please join the [auto-cpufreq Discord server!](https://discord.gg/Sjauxtj6kH)
* auto-cpufreq is looking for [co-maintainers & open source developers to help shape the future of the project!](https://github.com/AdnanHodzic/auto-cpufreq/discussions/312)

## Index

* [Why do I need auto-cpufreq?](#why-do-i-need-auto-cpufreq)
    * [Supported architectures and devices](#supported-architectures-and-devices)
* [Features](#features)
* [Installing auto-cpufreq](#installing-auto-cpufreq)
    * [auto-cpufreq-installer](#auto-cpufreq-installer)
    * [Snap Store](#snap-store)
    * [AUR package (Arch/Manjaro Linux)](#aur-package-archmanjaro-linux)
    * [NixOS](#nixos)
    * [For developers](#installation-development-mode-only)
* [Post-installation](#post-installation)
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
    * [Update - auto-cpufreq update](#update---auto-cpufreq-update)
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

One of the problems with Linux today on laptops is that the CPU will run in an unoptimized manner which will negatively impact battery life. For example, the CPU may run using the "performance" governor with turbo boost enabled regardless of whether it's plugged into a power outlet or not.

These issues can be mitigated by using tools like [indicator-cpufreq](https://itsfoss.com/cpufreq-ubuntu/) or [cpufreq](https://github.com/konkor/cpufreq), but those still require manual action from your side which can be daunting and cumbersome.

Tools like [TLP](https://github.com/linrunner/TLP) (which I used for numerous years) can help extend battery life, but may also create their own set of problems, such as losing turbo boost.

Given all of the above, I needed a simple tool that would automatically make CPU frequency-related changes and save battery life, but let the Linux kernel do most of the heavy lifting. That's how auto-cpufreq was born.

Please note: auto-cpufreq aims to replace TLP in terms of functionality, so after you install auto-cpufreq _it's recommended to remove TLP_. Using both for the same functionality (i.e., to set CPU frequencies) will lead to unwanted results like overheating. Hence, only use [both tools in tandem](https://github.com/AdnanHodzic/auto-cpufreq/discussions/176) if you know what you're doing.

One tool/daemon that does not conflict with auto-cpufreq in any way, and is even recommended to have running alongside, is [thermald](https://wiki.debian.org/thermald).

#### Supported architectures and devices

Only devices with an Intel, AMD, or ARM CPU are supported. This tool was developed to improve performance and battery life on laptops, but running it on desktops/servers (to lower power consumption) should also be possible.

## Features

* Monitoring
  * Basic system information
  * CPU frequency (system total & per core)
  * CPU usage (system total & per core)
  * CPU temperature (total average & per core)
  * Battery state
  * System load
* CPU frequency scaling, governor, and [turbo boost](https://en.wikipedia.org/wiki/Intel_Turbo_Boost) management based on
  * Battery state
  * CPU usage (total & per core)
  * CPU temperature in combination with CPU utilization/load (to prevent overheating)
  * System load
* Automatic CPU & power optimization (temporary and persistent)

## Installing auto-cpufreq

### auto-cpufreq-installer

Get source code, run installer, and follow on-screen instructions:

```
git clone https://github.com/AdnanHodzic/auto-cpufreq.git
cd auto-cpufreq && sudo ./auto-cpufreq-installer
```

### Snap Store

*Please note: while all [auto-cpufreq >= v2.0 CLI functionality](https://www.youtube.com/watch?v=SPGpkZ0AZVU&t=295s) will work as intended, [the GUI won't be available on Snap package installs](http://foolcontrol.org/wp-content/uploads/2023/10/auto-cpufreq-v2-snap-deprecation-notice.png) due to [Snap package confinement limitations](https://forum.snapcraft.io/t/pkexec-not-found-python-gtk-gnome-app/36579). Hence, please consider installing auto-cpufreq using [auto-cpufreq-installer](#auto-cpufreq-installer)*.

auto-cpufreq is available on the [Snap Store](https://snapcraft.io/auto-cpufreq) or via CLI:

```
sudo snap install auto-cpufreq
```

**Please note:**
* Make sure [snapd](https://snapcraft.io/docs/installing-snapd) is installed and `snap version` is >= 2.44 for `auto-cpufreq` to fully work due to [recent snapd changes](https://github.com/snapcore/snapd/pull/8127).

* Fedora users will [encounter the following error](https://twitter.com/killyourfm/status/1291697985236144130) due to `cgroups v2` [being in development](https://github.com/snapcore/snapd/pull/7825). This problem can be resolved by either running `sudo snap run auto-cpufreq` after the snap installation or by using the [auto-cpufreq-installer](#auto-cpufreq-installer) which doesn't have this issue.

### AUR package (Arch/Manjaro Linux)

*The AUR packages below are often unmaintained & have issues*! Unless you see evidence of good recent maintenance, use the [auto-cpufreq-installer](#auto-cpufreq-installer) instead as otherwise you'll run into errors (e.g., [#471](https://github.com/AdnanHodzic/auto-cpufreq/issues/471)). If you still choose to install via AUR, see the [Troubleshooting](#aur) section for solved known issues.

* [Binary Package](https://aur.archlinux.org/packages/auto-cpufreq)
(for the latest binary release)
* [Git Package](https://aur.archlinux.org/packages/auto-cpufreq-git)
(for the latest commits/changes)

### NixOS

<details>
<summary>Flakes</summary>
<br>

This repo contains a flake that exposes a NixOS Module that manages and offers options for auto-cpufreq. To use it, add the flake as an input to your `flake.nix` file and enable the module:

```nix 
# flake.nix

{

    inputs = {
        # ---Snip---
        auto-cpufreq = {
            url = "github:adnanhodzic/auto-cpufreq/nix";
            inputs.nixpkgs.follows = "nixpkgs";
        };
        # ---Snip---
    }

    outputs = {nixpkgs, auto-cpufreq, ...} @ inputs: {
        nixosConfigurations.HOSTNAME = nixpkgs.lib.nixosSystem {
            specialArgs = { inherit inputs; };
            modules = [
                ./configuration.nix
                auto-cpufreq.nixosModules.default
            ];
        };
    } 
}
```
Then you can enable the program in your `configuration.nix` file:
```nix
# configuration.nix

{inputs, pkgs, ...}: {
    # ---Snip---
    programs.auto-cpufreq.enable = true;
    # optionally, you can configure your auto-cpufreq settings, if you have any
    programs.auto-cpufreq.settings = {
    charger = {
      governor = "performance";
      turbo = "auto";
    };

    battery = {
      governor = "powersave";
      turbo = "auto";
    };
  };
    # ---Snip---
}
```
</details>

<details>
<summary>Nixpkgs</summary>
<br>

There is a nixpkg available, but it is more prone to being outdated, whereas the flake pulls from the latest commit. You can install it in your `configuration.nix` and enable the system service:
```nix
# configuration.nix

# ---Snip---
environment.systemPackages = with pkgs; [
    auto-cpufreq
];

services.auto-cpufreq.enable = true;
# ---Snip---
```
</details>

### Installation (development mode only)

- If you have `poetry` installed:
  ```bash
  git clone https://github.com/AdnanHodzic/auto-cpufreq.git
  cd auto-cpufreq
  poetry install
  poetry run auto-cpufreq --help
  ```

- Alternatively, we can use an editable pip install for development purposes:
  ```bash
  git clone https://github.com/AdnanHodzic/auto-cpufreq.git
  cd auto-cpufreq
  # set up virtual environment (details removed for brevity)
  pip3 install -e .
  auto-cpufreq
  ```
- Regularly run `poetry update` if you get any inconsistent lock file issues.

## Post-installation

After installation, `auto-cpufreq` is available as a binary. Refer to [auto-cpufreq modes and options](https://github.com/AdnanHodzic/auto-cpufreq#auto-cpufreq-modes-and-options) for detailed information on how to run and configure `auto-cpufreq`.

## Configuring auto-cpufreq

auto-cpufreq makes all decisions automatically based on various factors such as CPU usage, temperature, and system load. However, it's possible to perform additional configurations:

### 1: power_helper.py script (Snap package install **only**)

When installing auto-cpufreq via [auto-cpufreq-installer](#auto-cpufreq-installer), if it detects the [GNOME Power Profiles service](https://twitter.com/fooctrl/status/1467469508373884933) is running, it will automatically disable it. Otherwise, that daemon will cause conflicts and various other performance issues. 

However, when auto-cpufreq is installed as a Snap package it's running as part of a container with limited permissions, hence it's *highly recommended* to disable the GNOME Power Profiles daemon using the `power_helper.py` script.

**Please Note:**<br>
The [`power_helper.py`](https://github.com/AdnanHodzic/auto-cpufreq/blob/master/auto_cpufreq/power_helper.py) script is located within the auto-cpufreq repo at `auto_cpufreq/power_helper.py`. In order to access it, first clone
the repository:

`git clone https://github.com/AdnanHodzic/auto-cpufreq`

Navigate to the directory where `power_helper.py` resides:

`cd auto-cpufreq/auto_cpufreq`

Make sure to have `psutil` Python library installed before next step:

`sudo python3 -m pip install psutil`

Then disable the GNOME Power Profiles daemon:

`sudo python3 power_helper.py --gnome_power_disable`

### 2: `--force` governor override

By default, auto-cpufreq uses `balanced` mode which works best for many systems and situations.

However, you can override this behaviour by switching to `performance` or `powersave` mode manually. The `performance` mode results in higher default frequencies, but also higher energy use (battery consumption) and should only be used if maximum performance is needed. The `powersave` mode does the opposite and extends battery life to its maximum.

See [`--force` flag](#overriding-governor) for more info.

### 3: auto-cpufreq config file

You can configure separate profiles for the battery and power supply. These profiles will let you pick which governor to use, as well as how and when turbo boost is enabled. The possible values for turbo boost behavior are `always`, `auto`, and `never`. The default behavior is `auto`, which only activates turbo during high load.

By default, auto-cpufreq does not use the config file! If you wish to use it, the location where it needs to be placed to be read automatically is: `/etc/auto-cpufreq.conf`

#### Example config file contents
```python
# settings for when connected to a power source
[charger]
# see available governors by running: cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
# preferred governor
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

# turbo boost setting (always, auto, or never)
turbo = auto
```

## How to run auto-cpufreq
auto-cpufreq should be run with with one of the following options:

* [monitor](#monitor)
    - Monitor and see suggestions for CPU optimizations

* [live](#live)
    - Monitor and automatically make (temporary) CPU optimizations

* [install](#install---auto-cpufreq-daemon) / [remove](#remove---auto-cpufreq-daemon)
    - Install/remove daemon for (permanent) automatic CPU optimizations
 
* [install (GUI)](#install---auto-cpufreq-daemon)
    - Install daemon via GUI for (permanent) automatic CPU optimizations

* [update](#update---auto-cpufreq-update)
    - Update auto-cpufreq to the latest release

* [install_performance](#1-power_helperpy-script)
    - Install daemon in "performance" mode

* [stats](#stats)
    - View live stats of CPU optimizations made by daemon

* [force=TEXT](#overriding-governor)
    - Force use of either the "powersave" or "performance" governor, or set to "reset" to go back to normal mode

* config=TEXT
    - Use config file at designated path

* debug
    - Show debug info (include when submitting bugs)

* version
    - Show currently installed version

* [donate](#financial-donation)
    - To support the project

* help
    - Shows all of the above options

* completions=TEXT
    - To support shell completions (current options are "bash", "zsh", or "fish")

Running `auto-cpufreq --help` will print the same list of options as above. Read [auto-cpufreq modes and options](#auto-cpufreq-modes-and-options) for more details.

## auto-cpufreq modes and options

### Monitor

`sudo auto-cpufreq --monitor`

No changes are made to the system. This is solely to demonstrate what auto-cpufreq could do for your system.

### Live

`sudo auto-cpufreq --live`

Necessary changes are temporarily made to the system over time, but this process and its changes are lost at system reboot. This mode is provided to evaluate how the system would behave with auto-cpufreq permanently running on the system.

### Overriding governor

`sudo auto-cpufreq --force=governor`

Force use of either the "powersave" or "performance" governor, or set to "reset" to go back to normal mode.
Please note that any set override will persist even after reboot.

### Install - auto-cpufreq daemon

Necessary changes are made to the system over time and this process will continue across reboots. The daemon is deployed and started as a systemd service. Changes are made automatically and live stats are generated for monitoring purposes.

**Install the daemon using CLI ([after installing auto-cpufreq](#installing-auto-cpufreq)):**

Installing the auto-cpufreq daemon using CLI is as simple as running the following command:

`sudo auto-cpufreq --install`

After the daemon is installed, `auto-cpufreq` is available as a binary and runs in the background. Its stats can be viewed by running: `auto-cpufreq --stats`

*Please note:* if the daemon is installed within a desktop environment, then its stats and options can be accessed via CLI or GUI. See "Install the daemon using GUI" below for more details.

**Install the daemon using GUI**

Starting with >= v2.0 [after installing auto-cpufreq](#installing-auto-cpufreq), an auto-cpufreq desktop entry (icon) is available, i.e.:

<img src="https://foolcontrol.org/wp-content/uploads/2023/09/auto-cpufreq-desktop-entry-icon.png" width="640" alt="Example of auto-cpufreq desktop entry (icon)"/>

After selecting it to open the GUI, the auto-cpufreq daemon can be installed by clicking the "Install" button:

<img src="http://foolcontrol.org/wp-content/uploads/2023/09/auto-cpufreq-daemon-install-gui.png" width="480" alt="The auto-cpufreq GUI's 'Install' button"/>

After that, the full auto-cpufreq GUI is available:

<img src="http://foolcontrol.org/wp-content/uploads/2023/09/auto-cpufreq-v2-gui.png" width="640" alt="The full auto-cpufreq GUI"/>

*Please note:* after the daemon is installed (by any method), its stats and options are accessible via both CLI and GUI.

**auto-cpufreq daemon service**

Installing the auto-cpufreq daemon also enables the associated service (equivalent to `systemctl enable auto-cpufreq`), causing it to start on boot, and immediately starts it (equivalent to `systemctl start auto-cpufreq`).

Since the daemon is running as a systemd service, its status can be seen by running:

`systemctl status auto-cpufreq`

If installed via Snap package, daemon status can be viewed as follows:

`systemctl status snap.auto-cpufreq.service.service`

### Update - auto-cpufreq update

Update functionality works by cloning the auto-cpufreq repo, installing it via [auto-cpufreq-installer](#auto-cpufreq-installer), and performing a fresh [auto-cpufreq daemon install](#install---auto-cpufreq-daemon) to provide the [latest version's](https://github.com/AdnanHodzic/auto-cpufreq/releases) changes.

Update auto-cpufreq by running: `sudo auto-cpufreq --update`. By default, the latest revision is cloned to `/opt/auto-cpufreq/source`, thus maintaining existing directory structure.

Update and clone to a custom directory by running: `sudo auto-cpufreq --update=/path/to/directory`

### Remove - auto-cpufreq daemon

The auto-cpufreq daemon, its systemd service, and all its persistent changes can be removed by running:

`sudo auto-cpufreq --remove`

This does, in part, the equivalent of `systemctl stop auto-cpufreq && systemctl disable auto-cpufreq`, but the above command should be used instead of using `systemctl`.

*Please note:* after the daemon is removed, the auto-cpufreq GUI and desktop entry (icon) are also removed.

### Stats

If the daemon has been installed, live stats of CPU/system load monitoring and optimization can be seen by running:

`auto-cpufreq --stats`

## Troubleshooting

**Q:** If after installing auto-cpufreq you're (still) experiencing:
* high CPU temperatures
* CPU not scaling to minimum/maximum frequencies
* suboptimal CPU performance

**A:** If you're using the `intel_pstate/amd-pstate` CPU management driver, consider changing it to `acpi-cpufreq`.

This can be done by editing the `GRUB_CMDLINE_LINUX_DEFAULT` params in `/etc/default/grub`. For instance:

```
    sudo nano /etc/default/grub
    # make sure you have nano installed, or you can use your favorite text editor
```

For Intel users:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash intel_pstate=disable"
```

For AMD users:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash initcall_blacklist=amd_pstate_init amd_pstate.enable=0"
```

Once you have made the necessary changes to the GRUB configuration file, you can update GRUB by running `sudo update-grub` on Debian/Ubuntu, `sudo grub-mkconfig -o /boot/grub/grub.cfg` on Arch Linux, or one of the following on Fedora:

```
    sudo grub2-mkconfig -o /etc/grub2.cfg
```

```
    sudo grub2-mkconfig -o /etc/grub2-efi.cfg
```

```
    sudo grub2-mkconfig -o /boot/grub2/grub.cfg
    # legacy boot method
```

For systemd-boot users:

```
    sudo nano /etc/kernel/cmdline
    # make sure you have nano installed, or you can use your favorite text editor
```

For Intel users:

```
quiet splash intel_pstate=disable
```

For AMD users:

```
quiet splash initcall_blacklist=amd_pstate_init amd_pstate.enable=0
```

Once you have made the necessary changes to the `cmdline` file, you can update it by running `sudo reinstall-kernels`.

### AUR

* For AUR installs, the command `sudo auto-cpufreq --install` produces an error ([#471](https://github.com/AdnanHodzic/auto-cpufreq/issues/471)), so don't use that command.
    * The auto-cpufreq-installer script automates the enabling of auto-cpufreq.service, but since the AUR install process doesn't use that script, you need to open a terminal and run `sudo systemctl enable --now auto-cpufreq.service` to enable and start the service.
* The GNOME Power Profiles daemon is [automatically disabled by auto-cpufreq-installer](https://github.com/AdnanHodzic/auto-cpufreq#1-power_helperpy-script-snap-package-install-only) due to it's conflict with auto-cpufreq.service. However, this doesn't happen with AUR installs, which can lead to problems (e.g., [#463](https://github.com/AdnanHodzic/auto-cpufreq/issues/463)) if not masked manually.
    * Open a terminal and run `sudo systemctl mask power-profiles-daemon.service` (then `enable` and `start` the auto-cpufreq.service if you haven't already).

## Discussion:

* Blogpost: [auto-cpufreq - Automatic CPU speed & power optimizer for Linux](http://foolcontrol.org/?p=3124)

## Donate

Showing your support and appreciation for the auto-cpufreq project can be done in two ways:

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

Other ways of supporting the project consist of making a code or documentation contribution. If you have an idea for a new feature or you want to implement some of the existing feature requests or fix some of the [bugs & issues](https://github.com/AdnanHodzic/auto-cpufreq/issues), please make your changes and submit a [pull request](https://github.com/AdnanHodzic/auto-cpufreq/pulls). I'll be glad to review it and, if your changes are accepted, you'll be credited on the [releases page](https://github.com/AdnanHodzic/auto-cpufreq/releases).

**Please note: auto-cpufreq is looking for co-maintainers & open source developers to [help shape the future of the project!](https://github.com/AdnanHodzic/auto-cpufreq/discussions/312)**
