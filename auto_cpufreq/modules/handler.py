from configparser import ConfigParser
import logging
from auto_cpufreq.config.config import config
from auto_cpufreq.modules.observer import observer
from auto_cpufreq.modules.controller import SystemController
from auto_cpufreq.modules.system_info import SystemInfo
from auto_cpufreq.types import CPULoadStates, PowerStates, TempStates
from threading import Timer
from typing import Callable


class CustomTimer:
    def __init__(self, timeout: int, callback: Callable[[], None]) -> None:
        """
        A timer that can be restarted.

        :param timeout: Time in seconds after which the callback is executed.
        :param callback: The function to call when the timer expires.
        """
        self.timeout: int = timeout
        self.callback: Callable[[], None] = callback
        self._timer = None

    def start(self) -> None:
        """
        Start the timer.

        Cancels any existing timer before starting a new one.
        """
        self.cancel()  # Ensure any existing timer is canceled
        self._timer = Timer(self.timeout, self.callback)
        self._timer.start()

    def restart(self) -> None:
        """
        Restart the timer.

        Equivalent to calling start(), which cancels any existing timer and starts a new one.
        """
        self.start()

    def cancel(self) -> None:
        """
        Cancel the timer.

        If the timer is running, it will be canceled.
        If the timer doesn't exist or is not running, nothing happens.
        """
        if self._timer and self._timer.is_alive():
            self._timer.cancel()

    def is_running(self) -> bool:
        """
        Check if the timer is currently running.

        :return: True if the timer exists and is running, False otherwise.
        """
        return self._timer.is_alive() if self._timer else False


class SystemEventHandler:
    """
    Handles system events related to power state, CPU load, and temperature.

    This class is responsible for monitoring system events and taking appropriate
    actions based on the current state of the system. It adjusts CPU governor settings,
    frequency limits, and turbo boost status based on power source, system load, and
    temperature conditions.
    """

    # Class variables to track system states
    last_power_state: PowerStates | None = None
    last_temp_states: TempStates | None = None
    last_cpu_load_state: CPULoadStates | None = None
    cpu_load_timer: CustomTimer | None = None

    def init(self) -> None:
        self.handle_power_source(observer.sys_power_source())
        self.handle_sys_load(observer.sys_load_state())
        self.handle_sys_temp(observer.sys_temp_state())

    def handle_power_source(
        self, value: PowerStates | CPULoadStates | TempStates
    ) -> None:
        """
        Handle changes in power source (AC or battery).

        Switches between performance and power saving modes based on whether
        the device is connected to AC power or running on battery.

        :param value: The current power state. Only PowerStates types are processed.
        """
        logging.debug("power source recevied event: %s", value)
        # Check if value is of PowerStates type first
        if not isinstance(value, PowerStates):
            return

        elif value == self.last_power_state:
            # No change in state, no action needed
            return

        elif value == PowerStates.AC:
            # Switched to AC power
            self.performance_mode()
            logging.info("AC connected, switched to performance mode")
        elif value == PowerStates.BATTERY:
            # Switched to battery power
            self.powersaving_mode()
            logging.info("AC disconnected, switched to powersaving mode")

        # Update the last known power state
        self.last_power_state = value

    def powersaving_mode(self) -> None:
        """
        Configure the system for power saving mode.

        Sets CPU governor to powersave, adjusts frequency limits,
        and configures energy performance bias and platform profile
        for optimal battery life.
        """
        conf: ConfigParser = config.get_config()
        SystemController.set_powersave_gov()
        SystemController.set_frequencies()
        SystemController.set_energy_perf_bias(conf, "battery")
        SystemController.set_platform_profile(conf, "battery")

    def performance_mode(self) -> None:
        """
        Configure the system for performance mode.

        Sets CPU governor to performance, adjusts frequency limits,
        and configures energy performance bias and platform profile
        for optimal system performance when connected to AC power.
        """
        conf: ConfigParser = config.get_config()
        SystemController.set_performance_gov()
        SystemController.set_frequencies()
        SystemController.set_energy_perf_bias(conf, "charger")
        SystemController.set_platform_profile(conf, "charger")

    def handle_sys_load(self, value: PowerStates | CPULoadStates | TempStates) -> None:
        """
        Handle changes in system CPU load.

        Enables or disables CPU turbo based on system load levels, with a delay
        to prevent responding to temporary load spikes.

        :param value: The current CPU load state. Only CPULoadStates types are processed.
        """
        logging.debug("sys load recevied event: %s", value)
        # Check if value is of CPULoadStates type first
        if not isinstance(value, CPULoadStates):
            return

        elif value == self.last_cpu_load_state:
            # No change in state, no action needed
            return

        def set_load(current: CPULoadStates) -> None:
            """
            Inner callback function to set CPU turbo state based on load.
            Called after the delay timer expires.
            """
            logging.debug("set_load recevied current:%s", current)
            if current == CPULoadStates.HIGH:
                SystemController.set_turbo(on=True)
                logging.info("set turbo on, high system load")
            elif SystemInfo.turbo_on()[0]:
                SystemController.set_turbo(on=False)
                logging.info("set turbo off, not high system load")

        # Avoiding changing turbo status for short load spikes by using a timer
        if self.cpu_load_timer is not None:
            self.cpu_load_timer.cancel()
            self.cpu_load_timer = None

        logging.debug("cpu load timer registered, event:%s", value)
        # Set a 10-second delay before applying the turbo state change
        self.cpu_load_timer = CustomTimer(timeout=10, callback=lambda: set_load(value))
        self.cpu_load_timer.start()

        # Update the last known CPU load state
        self.last_cpu_load_state = value

    def handle_sys_temp(self, value: PowerStates | CPULoadStates | TempStates) -> None:
        """
        Handle changes in system temperature.

        Disables CPU turbo when the system temperature is high to prevent
        thermal throttling and potential hardware damage.

        :param value: The current temperature state. Only TempStates types are processed.
        """
        logging.debug("sys temp recevied event: %s", value)
        # Check if value is of TempStates type first
        if not isinstance(value, TempStates):
            return

        elif value == self.last_cpu_load_state:
            # No change in state, no action needed
            return

        elif value == TempStates.HIGH and SystemInfo.turbo_on()[0]:
            # Temperature state changed to HIGH
            SystemController.set_turbo(on=False)
            logging.info("set turbo off, high system temp")

        # Update the last known temperature state
        self.last_temp_states = value


# Create a singleton instance of the SystemEventHandler
system_events_handler = SystemEventHandler()
