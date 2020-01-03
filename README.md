# auto-cpufreq

Automatic CPU speed & power optimizer for Linux based on active monitoring of laptop's battery state, CPU usage and system load. 

### Why do I need auto-cpufreq?

One of the problems with Linux today on laptops is that CPU will run in unoptimized manner which will negatively reflect on battery life. For example, CPU will run using "performance" governor with turbo boost enabled regardless if it's plugged in to power or not.

Issue can be mitigated by using tools like [indicator-cpufreq](https://itsfoss.com/cpufreq-ubuntu/) or [cpufreq](https://github.com/konkor/cpufreq), but these still require maual action from your side which can be daunting and cumbersome.

Using tools like [TLP](https://github.com/linrunner/TLP) will help in this situation with extending battery life (which is something I did for numerous years now), but it also might come with its own set of problems, like loosing turbo boost.

With that said, I needed a simple tool which would automatically make "cpufreq" related changes, save bettery like TLP, but let Linux kernel do most of the heavy lifting. That's how auto-cpufreq was born.

### Features

* Monitoring 
  * Basic system information
  * CPU frequency
  * CPU temperatures
  * Battery state
  * System load
* CPU frequency scaling, governor and [turbo boost](https://en.wikipedia.org/wiki/Intel_Turbo_Boost) management based on
  * battery state
  * CPU usage
  * System load
* Automatic CPU & power optimization (temporary and persistent)

### How to run auto-cpufreq?

##### Get auto-cpufreq source code

`git clone https://github.com/AdnanHodzic/auto-cpufreq.git`

#### Install requirements

##### Requirements installation for Debian/Ubuntu and their derivatives

All requirements can be installed by running:

`sudo apt install python3 python3-distro python3-psutil python3-click -y`

##### Requirements installation for all other Linux distributions

If you have python3 and pip3 installed simply run:

`sudo pip3 install psutil click distro`

Note: libraries must be installed using root user as tool will be run as root.

#### Run auto-cpufreq

auto-cpufreq can be run by simply running the `auto-cpufreq.py` and following on screen instructions, i.e:

`sudo python3 auto-cpufreq.py`

### auto-cpufreq modes and options

#### Monitor

`sudo python3 auto-cpufreq.py --monitor`

No changes are made to the system, and is solely made for demonstration purposes what auto-cpufreq could do differently for your system.

#### Live

`sudo python3 auto-cpufreq.py --live`

Necessary changes are temporarily made to the system, this mode is made to evaluate what the system would behave with auto-cpufreq permanently running on the system.

#### Install - auto-cpufreq daemon (systemd) service

`sudo python3 auto-cpufreq.py --install`

#### Remove - auto-cpufreq daemon (systemd) service

auto-cpufreq daemon and all persistent changes can be removed by running:

`sudo autocpu-freq --remove`
or
`sudo python3 auto-cpufreq.py --remove`

#### Log

If daemon has been setup live log of CPU/system load monitoring and optimizaiton can be seen by running:

`auto-cpufreq --log`
or `sudo python3 auto-cpufreq.py --log`

Necessary changes are made to the system for auto-cpufreq CPU optimizaton to persist across reboots. Daemon is deployed and then started by a systemd service. Changes are made automatically and live log is made for monitoring purposes.

# Discussion:

* Blogpost: [auto-cpufreq - Automatic CPU speed & power optimizer for Linux](http://foolcontrol.org/?p=3124)
