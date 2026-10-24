import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from importlib.metadata import PackageNotFoundError, version as package_version
from os.path import isdir
from subprocess import PIPE, run
from threading import Thread
import time

from auto_cpufreq.gui.diagnostics import diagnostics
from auto_cpufreq.gui.refresh_bridge import GtkRefreshBridge
from auto_cpufreq.gui.refresh_timer import GtkRefreshTimer
from auto_cpufreq.gui.report_view import SystemReportView

from auto_cpufreq.config.config import config
from auto_cpufreq.core import check_for_update, daemon_is_running
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.gui.desktop import open_containing_folder
from auto_cpufreq.gui.monitor_view import MonitorModeView
from auto_cpufreq.gui.objects import (
    BluetoothBootControl, CPUTurboOverride, DaemonNotRunningView,
    DropDownMenu, RadioButtonView, UpdateDialog,
)
from auto_cpufreq.modules.report_presentation import configuration_file_text
from auto_cpufreq.modules.system_info import system_info
from auto_cpufreq.power_helper import bluetoothctl_exists

if IS_INSTALLED_WITH_SNAP:
    CSS_FILE = "/snap/auto-cpufreq/current/style.css"
    ICON_FILE = "/snap/auto-cpufreq/current/icon.png"
elif isdir("/opt/auto-cpufreq/current/share"):
    CSS_FILE = "/opt/auto-cpufreq/current/share/scripts/style.css"
    ICON_FILE = "/opt/auto-cpufreq/current/share/images/icon.png"
else:
    CSS_FILE = "/usr/local/share/auto-cpufreq/scripts/style.css"
    ICON_FILE = "/usr/local/share/auto-cpufreq/images/icon.png"

CONTROL_OPTION_MARGIN = 8

DEFAULT_REFRESH_INTERVAL = 2
REFRESH_INTERVALS = (1, 2, 5)

# The daemon normally applies overrides on its next ~2 second cycle.
# Keep the affected state hidden until a later, fresh report is collected.
CONTROL_APPLY_DELAY_SECONDS = 3


def _configuration_label_text():
    return configuration_file_text(config.path, config.has_config())


class ToolWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="auto-cpufreq")
        self.set_default_size(920, 680)
        self.set_border_width(10)
        self.set_resizable(True)
        self.refresh_pending = False
        self.refresh_interval = DEFAULT_REFRESH_INTERVAL
        self.pending_power_updates = set()
        self.pending_power_release = set()
        self.power_apply_sources = {}
        self.destroyed = False
        self._update_check_pending = False
        self._refresh_bridge = GtkRefreshBridge(
            self._collect_report,
            component="GTK dashboard",
            diagnostics=diagnostics,
            active=lambda: not self.destroyed,
            interval=lambda: self.refresh_interval,
            on_report=self._apply_refresh,
            on_error=self._finish_refresh_error,
            before_ack=self._run_pending_refresh,
            thread_name="gtk-dashboard-refresh",
        )
        self._refresh_coordinator = self._refresh_bridge.coordinator
        self._refresh_timer = GtkRefreshTimer(
            coordinator=self._refresh_coordinator,
            request=self._refresh_coordinator.request_if_idle,
            active=lambda: not self.destroyed,
            diagnostics=diagnostics,
            component="GTK dashboard",
            interval=self.refresh_interval,
        )
        self.connect("destroy", self._cleanup_refresh)
        diagnostics.info("GTK window created")
        self.load_css()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename=ICON_FILE,
            width=500,
            height=500,
            preserve_aspect_ratio=True,
        )
        self.set_icon(pixbuf)
        self.build()

    def main(self):
        self.report_view = SystemReportView()

        controls_frame = Gtk.Frame()
        controls_heading = Gtk.Label(label="Controls", name="bold")
        controls_heading.set_halign(Gtk.Align.START)
        controls_frame.set_label_widget(controls_heading)

        controls_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )
        controls_box.set_margin_top(8)
        controls_box.set_margin_bottom(8)
        controls_box.set_margin_start(10)
        controls_box.set_margin_end(10)
        controls_frame.add(controls_box)

        controls_actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        controls_actions.set_halign(Gtk.Align.END)
        controls_box.pack_start(controls_actions, False, False, 0)

        self.menu = DropDownMenu(self)
        self._add_refresh_interval_menu()
        controls_actions.pack_end(self.menu, False, False, 0)

        self.governor_control = RadioButtonView()
        self.governor_control.label.set_xalign(0.0)
        self.governor_control.default.set_margin_start(CONTROL_OPTION_MARGIN)
        controls_box.pack_start(self.governor_control, False, False, 0)

        self.control_label_group = Gtk.SizeGroup(
            mode=Gtk.SizeGroupMode.HORIZONTAL
        )
        self.control_label_group.add_widget(self.governor_control.label)
        self.control_option_groups = [
            Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
            for _ in range(3)
        ]
        for group, button in zip(
            self.control_option_groups,
            (
                self.governor_control.default,
                self.governor_control.powersave,
                self.governor_control.performance,
            ),
        ):
            group.add_widget(button)
            button.set_halign(Gtk.Align.START)

        turbo_state, _ = system_info.turbo_on()
        if turbo_state is not None:
            self.turbo_control = CPUTurboOverride()
            self.turbo_control.label.set_xalign(0.0)
            self.turbo_control.auto.set_margin_start(CONTROL_OPTION_MARGIN)
            controls_box.pack_start(self.turbo_control, False, False, 0)
            self.control_label_group.add_widget(self.turbo_control.label)
            for group, button in zip(
                self.control_option_groups,
                (
                    self.turbo_control.auto,
                    self.turbo_control.never,
                    self.turbo_control.always,
                ),
            ):
                group.add_widget(button)
                button.set_halign(Gtk.Align.START)

        if bluetoothctl_exists:
            self.bluetooth_control = BluetoothBootControl(
                show_advanced_button=False
            )
            controls_actions.pack_end(
                self.bluetooth_control.advanced_btn,
                False,
                False,
                0,
            )
            self.bluetooth_control.label.set_xalign(0.0)
            self.bluetooth_control.on_btn.set_margin_start(
                CONTROL_OPTION_MARGIN
            )
            self.control_label_group.add_widget(
                self.bluetooth_control.label
            )
            self.control_option_groups[0].add_widget(
                self.bluetooth_control.on_btn
            )
            self.control_option_groups[1].add_widget(
                self.bluetooth_control.off_btn
            )
            self.bluetooth_control.on_btn.set_halign(Gtk.Align.START)
            self.bluetooth_control.off_btn.set_halign(Gtk.Align.START)
            spacer = Gtk.Label()
            self.control_option_groups[2].add_widget(spacer)
            self.bluetooth_control.inner_box.pack_start(
                spacer, True, True, 0
            )
            controls_box.pack_start(
                self.bluetooth_control, False, False, 0
            )

        config_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        self.config_label = Gtk.Label(
            label=_configuration_label_text()
        )
        self.config_label.set_halign(Gtk.Align.START)
        self.config_label.set_xalign(0)
        self.config_label.set_line_wrap(True)
        config_row.pack_start(self.config_label, True, True, 0)

        self.config_folder_button = Gtk.Button.new_from_icon_name(
            "folder-open-symbolic", Gtk.IconSize.BUTTON
        )
        self.config_folder_button.set_relief(Gtk.ReliefStyle.NONE)
        self.config_folder_button.set_tooltip_text(
            "Open configuration folder"
        )
        self.config_folder_button.connect(
            "clicked", self._open_config_folder
        )
        config_row.pack_start(
            self.config_folder_button, False, False, 0
        )
        controls_box.pack_start(config_row, False, False, 0)

        self.report_view.prepend_right(controls_frame)

        # Applying… continues to address the shared
        # observed governor/Turbo rows directly.
        self.power_values = self.report_view.power_values

        self.refresh_error_label = Gtk.Label(label="")
        self.refresh_error_label.set_halign(Gtk.Align.START)
        self.refresh_error_label.set_xalign(0)
        self.refresh_error_label.set_no_show_all(True)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        self.scrolled.set_can_focus(True)
        self.scrolled.add(self.report_view)

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        main_box.pack_start(
            self.refresh_error_label, False, False, 0
        )
        main_box.pack_start(self.scrolled, True, True, 0)
        self.add(main_box)

        self.refresh_in_thread()
        self._schedule_refresh()

    def begin_power_state_apply(self, key):
        if (
            self.destroyed
            or key not in getattr(self, "power_values", {})
        ):
            return False

        source_id = self.power_apply_sources.pop(key, None)
        if source_id is not None:
            GLib.source_remove(source_id)

        # A newer action for this field supersedes any older
        # release that was waiting behind an in-flight refresh.
        self.pending_power_release.discard(key)
        self.pending_power_updates.add(key)
        self.power_values[key].set_text("Applying…")
        return True

    def finish_power_state_apply(self, key, success):
        if (
            self.destroyed
            or key not in self.pending_power_updates
        ):
            return False

        if not success:
            self.pending_power_updates.discard(key)
            self.pending_power_release.discard(key)
            self.request_refresh()
            return True

        source_id = GLib.timeout_add_seconds(
            CONTROL_APPLY_DELAY_SECONDS,
            self._release_power_state_apply,
            key,
        )
        self.power_apply_sources[key] = source_id
        return True

    def _release_power_state_apply(self, key):
        self.power_apply_sources.pop(key, None)

        if (
            self.destroyed
            or key not in self.pending_power_updates
        ):
            return False

        # Never let a report that started before this point replace
        # "Applying…". If one is already running, queue a fresh one.
        if self.refresh_in_progress:
            self.pending_power_release.add(key)
            self.refresh_pending = True
            return False

        self.pending_power_updates.discard(key)
        self.refresh_in_thread()
        return False

    def _open_config_folder(self, _button):
        open_containing_folder(self, config.path)

    def _add_refresh_interval_menu(self):
        refresh_item = Gtk.MenuItem(
            label="Refresh interval"
        )
        refresh_menu = Gtk.Menu()
        group = None

        for seconds in REFRESH_INTERVALS:
            label = (
                f"{seconds} second"
                if seconds == 1
                else f"{seconds} seconds"
            )

            item = Gtk.RadioMenuItem.new_with_label(
                group,
                label,
            )

            if group is None:
                group = item.get_group()

            item.set_active(
                seconds == self.refresh_interval
            )

            item.connect(
                "toggled",
                self._on_refresh_interval_selected,
                seconds,
            )

            refresh_menu.append(item)

        refresh_item.set_submenu(refresh_menu)

        self.menu.menu.prepend(
            Gtk.SeparatorMenuItem()
        )
        self.menu.menu.prepend(refresh_item)
        self.menu.menu.show_all()

    def _on_refresh_interval_selected(
        self,
        item,
        seconds,
    ):
        if item.get_active():
            self.set_refresh_interval(seconds)

    def set_refresh_interval(self, seconds):
        if seconds not in REFRESH_INTERVALS:
            return

        if seconds == self.refresh_interval:
            return

        self.refresh_interval = seconds
        self._refresh_timer.set_interval(seconds)
        diagnostics.info("GTK refresh interval set to %ds", seconds)
        self._schedule_refresh()
        self.request_refresh()

    @property
    def refresh_in_progress(self):
        """Single authoritative collection/delivery state."""
        return self._refresh_coordinator.in_progress

    @property
    def refresh_id(self):
        """Active periodic timer source, exposed for legacy UI inspection."""
        return self._refresh_timer.source_id

    def _schedule_refresh(self):
        self._refresh_timer.start()

    def request_refresh(self):
        return self.refresh_in_thread()

    def _run_pending_refresh(self):
        if (
            not self.refresh_pending
            or self.destroyed
        ):
            return

        self.refresh_pending = False

        # These fields waited for an older report to finish.
        # The refresh started below is therefore the first report
        # collected after their apply delay elapsed.
        for key in self.pending_power_release:
            self.pending_power_updates.discard(key)
        self.pending_power_release.clear()

        self._refresh_coordinator.request()

    def _cleanup_refresh(self, *_args):
        if self.destroyed:
            return
        self.destroyed = True
        # Free UI resources before optional diagnostic I/O. The destroy
        # signal and explicit teardown may both call this method.
        self._refresh_coordinator.close()
        self.refresh_pending = False

        self._refresh_timer.stop()

        for source_id in self.power_apply_sources.values():
            GLib.source_remove(source_id)
        self.power_apply_sources.clear()
        self.pending_power_updates.clear()
        self.pending_power_release.clear()
        try:
            diagnostics.set_error_callback(None)
            diagnostics.info("GTK window closing")
        except Exception:
            pass  # Broken diagnostics must never prevent GTK shutdown.

    def show_debug_log_error(self, message):
        if self.destroyed:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.CLOSE,
            text="GUI debug logging error",
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda widget, response: widget.destroy())
        dialog.show_all()

    def snap(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        # reference: https://forum.snapcraft.io/t/pkexec-not-found-python-gtk-gnome-app/36579
        label = Gtk.Label(label="GUI not available due to Snap package confinement limitations.\nPlease install auto-cpufreq using auto-cpufreq-installer\nVisit the GitHub repo for more info")
        label.set_justify(Gtk.Justification.CENTER)
        button = Gtk.LinkButton.new_with_label(
            uri=GITHUB,
            label="GitHub Repo"
        )
        
        box.pack_start(label, False, False, 0)
        box.pack_start(button, False, False, 0)
        self.add(box)

    def handle_update(self):
        """Check for updates without blocking the GTK event loop."""
        if self.destroyed or self._update_check_pending:
            return False
        self._update_check_pending = True
        try:
            Thread(
                target=self._check_update_async,
                daemon=True, name="gtk-update-check",
            ).start()
        except RuntimeError:
            self._update_check_pending = False
            raise
        return False

    def _check_update_async(self):
        # No redirect_stdout here: stdout is process-global and redirecting
        # it from a thread could interfere with concurrent debug output.
        try:
            available_tag = check_for_update()
            error = None
        except Exception as exc:
            available_tag, error = None, exc
        try:
            GLib.idle_add(self._finish_update_check, available_tag, error)
        except Exception as exc:
            diagnostics.warning("Cannot deliver GTK update result: %s", exc)

    def _finish_update_check(self, available_tag, error):
        self._update_check_pending = False
        if self.destroyed:
            return False
        if error is not None:
            diagnostics.warning("Update check failed: %s", error)
            return False
        if not available_tag:
            return False

        try:
            installed_version = package_version("auto-cpufreq")
        except (PackageNotFoundError, ValueError):
            installed_version = "unknown"

        dialog = UpdateDialog(
            self,
            f"Current version: {installed_version}",
            f"Latest version: {available_tag}",
        )
        response = dialog.run()
        dialog.destroy()
        if self.destroyed or response != Gtk.ResponseType.YES:
            return False
        self.set_sensitive(False)
        Thread(target=self._run_update, daemon=True).start()
        return False

    def _run_update(self):
        try:
            updater = run(
                ["pkexec", "auto-cpufreq", "--update"],
                input="y\n",
                text=True,
                stderr=PIPE,
            )
            error = None
        except OSError as exc:
            updater = None
            error = exc

        if not self.destroyed:
            GLib.idle_add(
                self._finish_update,
                updater,
                error,
            )

    def _finish_update(self, updater, error):
        self.set_sensitive(True)

        if error is not None:
            message = str(error)
        elif updater is None:
            message = "Update command failed to start"
        elif updater.returncode == 0:
            message = None
        elif updater.returncode == 126:
            message = "Authorization was cancelled"
        elif updater.returncode == 127:
            message = "Authorization failed"
        else:
            message = (updater.stderr or "").strip() or (
                "Update failed with exit status "
                f"{updater.returncode}"
            )

        if message is not None:
            dialog = Gtk.MessageDialog(
                self,
                0,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                "Error updating",
            )
            dialog.format_secondary_text(message)
            dialog.run()
            dialog.destroy()
            return False

        success = Gtk.MessageDialog(
            self,
            0,
            Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK,
            "Update successful",
        )
        success.format_secondary_text(
            "The app will now close. Please reopen to apply changes"
        )
        success.run()
        success.destroy()
        self.destroy()
        return False

    def daemon_not_running(self):
        self.box = DaemonNotRunningView(self)
        self.add(self.box)

    def monitor_mode(self):
        self.monitor_view = MonitorModeView(
            self,
            SystemReportView(),
            refresh_interval=self.refresh_interval,
        )
        self.add(self.monitor_view)

    def build(self):
        if IS_INSTALLED_WITH_SNAP: self.snap()
        elif daemon_is_running(): self.main()
        else: self.daemon_not_running()

    def load_css(self):
        screen = Gdk.Screen.get_default()
        self.gtk_provider = Gtk.CssProvider()
        self.gtk_context = Gtk.StyleContext()
        self.gtk_context.add_provider_for_screen(screen, self.gtk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.gtk_provider.load_from_file(Gio.File.new_for_path(CSS_FILE))

    def refresh_in_thread(self):
        """Explicit refresh requests may queue one successor if busy.

        Periodic ticks use GtkRefreshTimer and skip occupied collections.
        """
        if self.destroyed:
            return False
        if self._refresh_coordinator.in_progress:
            self.refresh_pending = True
            diagnostics.debug("GTK refresh requested during active collection")
            return True
        self._refresh_coordinator.request()
        return True

    def _collect_report(self):
        return system_info.generate_system_report()

    def _apply_refresh(self, report):
        if self.destroyed:
            return False

        started = time.monotonic()
        try:
            self.report_view.apply_report(
                report,
                self.pending_power_updates,
            )
            self.config_label.set_text(
                _configuration_label_text()
            )
            self.refresh_error_label.hide()
        except Exception as error:
            diagnostics.exception("GTK dashboard render failed")
            self.refresh_error_label.set_text(
                "Unable to refresh system information: "
                f"{error}"
            )
            self.refresh_error_label.show()
        finally:
            try:
                diagnostics.record_duration(
                    "GTK dashboard render",
                    time.monotonic() - started,
                    slow_after=1.0,
                )
            except Exception:
                pass
        return False

    def _finish_refresh_error(self, message):
        if self.destroyed:
            return False

        diagnostics.warning("GTK dashboard collection error: %s", message)
        self.refresh_error_label.set_text(
            "Unable to refresh system information: "
            f"{message}"
        )
        self.refresh_error_label.show()
        return False
