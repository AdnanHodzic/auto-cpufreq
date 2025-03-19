from typing import Callable, Dict, List, Optional
import asyncio
import threading
import logging
from auto_cpufreq.modules.system_info import BatteryInfo, SystemInfo
from auto_cpufreq.globals import (
    LOW_TEMP_THRESHOLD,
    HIGH_TEMP_THRESHOLD,
    LOW_LOAD_THRESHOLD,
    HIGH_LOAD_THRESHOLD,
)
from auto_cpufreq.types import CPULoadStates, ObserverEvent, PowerStates, TempStates


class EventObserver:
    """
    Monitors system events and notifies registered listeners when changes occur.

    This class implements the observer pattern to monitor system events like power source changes,
    CPU load changes, and temperature changes. It runs asynchronous monitoring tasks and notifies
    registered callback functions when specific events are detected.

    Events are monitored at regular intervals defined by CHECK_INTERVAL.
    """

    # Class variables for global state
    __listeners: Dict[
        ObserverEvent, List[Callable[[PowerStates | CPULoadStates | TempStates], None]]
    ] = {}
    __running_tasks: List[asyncio.Task] = []
    __stop_event = asyncio.Event()

    # Interval in seconds between checks for all observers
    CHECK_INTERVAL = 0.5

    def sys_power_source(self) -> PowerStates:
        """
        Determines the current power source state of the system.

        Checks whether the system is connected to AC power or running on battery.

        :return: PowerStates.AC if the system is connected to AC power,
                PowerStates.BATTERY if running on battery
        """
        battery_info: BatteryInfo = SystemInfo.battery_info()
        value: Optional[bool] = battery_info.is_ac_plugged
        return PowerStates.AC if value else PowerStates.BATTERY

    def sys_load_state(self) -> CPULoadStates:
        """
        Determines the current CPU load state of the system.

        Evaluates both system load and CPU usage percentages to categorize
        the current load state as LOW, NORMAL, or HIGH based on defined thresholds.

        :return: The current CPU load state (LOW, NORMAL, or HIGH)
        """
        load: float = SystemInfo.system_load()
        usage: float = SystemInfo.cpu_usage()

        # Determine the current load state based on CPU usage and system load
        if usage < 10.0 and load <= LOW_LOAD_THRESHOLD:
            return CPULoadStates.LOW
        if usage >= 20.0 or load >= HIGH_LOAD_THRESHOLD:
            return CPULoadStates.HIGH
        return CPULoadStates.NORMAL

    def sys_temp_state(self) -> TempStates:
        """
        Determines the current temperature state of the system.

        Reads the average CPU temperature and categorizes it as LOW, NORMAL, or HIGH
        based on the defined temperature thresholds.

        :return: The current temperature state (LOW, NORMAL, or HIGH)
        """
        temp: int = SystemInfo.avg_temp()

        # Determine the current temperature state based on thresholds
        if temp < LOW_TEMP_THRESHOLD:
            return TempStates.LOW
        if temp < HIGH_TEMP_THRESHOLD:
            return TempStates.NORMAL
        return TempStates.HIGH

    async def __observe_ac(self) -> None:
        """
        Monitors changes in power source (AC/battery).

        Periodically checks if the system is connected to AC power or running on battery,
        and notifies registered listeners when the state changes.
        """
        old_state: PowerStates | None = None
        while not self.__stop_event.is_set():
            try:
                state: PowerStates = self.sys_power_source()
                if state is not None and old_state != state:
                    old_state = state
                    await self.__notify_listeners(ObserverEvent.POWER_SOURCE, state)
            except Exception as e:
                logging.error(f"Error in AC power observation: {e}")
            await asyncio.sleep(self.CHECK_INTERVAL)

    async def __observe_sys_load(self) -> None:
        """
        Monitors changes in system CPU load.

        Periodically checks the system load and CPU usage, determines the load state
        (LOW, NORMAL, HIGH), and notifies registered listeners when the state changes.
        """
        old_state: CPULoadStates | None = None
        while not self.__stop_event.is_set():
            try:
                state: CPULoadStates = self.sys_load_state()

                # Only notify listeners if the state value changes
                if state != old_state:
                    old_state = state
                    await self.__notify_listeners(ObserverEvent.SYS_LOAD, state)
            except Exception as e:
                logging.error(f"Error in system load observation: {e}")
            await asyncio.sleep(self.CHECK_INTERVAL)

    async def __observe_sys_temp(self) -> None:
        """
        Monitors changes in system temperature.

        Periodically checks the average CPU temperature, determines the temperature state
        (LOW, NORMAL, HIGH), and notifies registered listeners when the state changes.
        """
        old_state: Optional[TempStates] = None
        while not self.__stop_event.is_set():
            try:
                state: TempStates = self.sys_temp_state()

                # Only notify listeners if the state value changes
                if state != old_state:
                    old_state = state
                    await self.__notify_listeners(ObserverEvent.SYS_TEMP, state)
            except Exception as e:
                logging.error(f"Error in temperature observation: {e}")
            await asyncio.sleep(self.CHECK_INTERVAL)

    async def __notify_listeners(
        self, event: ObserverEvent, state: PowerStates | CPULoadStates | TempStates
    ) -> None:
        """
        Notify all listeners registered for the given event type.

        Calls each callback function registered for the event, handling both
        synchronous and asynchronous callbacks.

        :param event: The event type that occurred
        :param state: The current state value to pass to listener callbacks
        """
        for cb in self.__listeners.get(event, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(state)
                else:
                    cb(state)
            except Exception as e:
                logging.error(f"Error in event listener callback: {cb.__name__} {e}")

    def listen(
        self,
        event: ObserverEvent,
        callback: Callable[[PowerStates | CPULoadStates | TempStates], None],
    ) -> bool:
        """
        Register a callback for a specific event type.

        Adds the callback function to the list of listeners for the specified event.
        The callback will be invoked when the event occurs.

        :param event: The event type to listen for
        :param callback: The callback function to execute when event occurs
        :return: True if registration was successful
        """
        if event not in self.__listeners:
            self.__listeners[event] = []
        self.__listeners[event].append(callback)
        return True

    def unlisten(
        self,
        event: ObserverEvent,
        callback: Callable[[PowerStates | CPULoadStates | TempStates], None],
    ) -> bool:
        """
        Unregister a callback for a specific event type.

        Removes the callback function from the list of listeners for the specified event.

        :param event: The event type the callback was registered for
        :param callback: The callback function to remove
        :return: True if callback was found and removed, False otherwise
        """
        if event in self.__listeners and callback in self.__listeners[event]:
            self.__listeners[event].remove(callback)
            return True
        return False

    async def start_observing(self) -> None:
        """
        Start observing all system events asynchronously.

        Creates tasks for monitoring power source, system load, and temperature,
        and waits until the stop event is set.
        """
        self.__stop_event.clear()
        self.__running_tasks = [
            asyncio.create_task(self.__observe_ac()),
            asyncio.create_task(self.__observe_sys_load()),
            asyncio.create_task(self.__observe_sys_temp()),
        ]
        # Wait until stop_event is set
        await self.__stop_event.wait()

    async def stop_observing(self) -> None:
        """
        Stop observing all system events asynchronously.

        Sets the stop event, cancels all running tasks, and waits for them to complete.
        """
        self.__stop_event.set()
        # Cancel all running tasks
        for task in self.__running_tasks:
            task.cancel()
        # Wait for all tasks to be cancelled
        if self.__running_tasks:
            await asyncio.wait(self.__running_tasks)
        self.__running_tasks = []

    def start(self) -> threading.Thread:
        """
        Start observing in a separate thread to avoid blocking.

        Creates a new thread with its own event loop to run the observation tasks.

        :return: A thread object running the event loop
        """

        def run_async_loop() -> None:
            """
            Inner function to set up and run the asyncio event loop.
            Runs in a separate thread to avoid blocking the main thread.
            """
            loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start_observing())
            finally:
                loop.close()

        thread = threading.Thread(target=run_async_loop, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        """
        Stop the observer.

        Stops all observation tasks, either by creating a new task in the
        running event loop or by running the stop_observing coroutine directly.
        """
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.stop_observing())
        else:
            loop.run_until_complete(self.stop_observing())


# Create a singleton instance of the EventObserver
observer = EventObserver()
