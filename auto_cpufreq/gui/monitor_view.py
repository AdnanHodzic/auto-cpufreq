"""GTK Monitor view with read-only CPU recommendations.

All hardware sampling is delegated to SystemInfo. The view does not
execute a privileged command or own the shared report renderer.
"""
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from auto_cpufreq.gui.diagnostics import diagnostics
from auto_cpufreq.gui.refresh_bridge import GtkRefreshBridge
from auto_cpufreq.gui.refresh_timer import GtkRefreshTimer
from auto_cpufreq.modules.report_recommendations import RecommendationStatus
from auto_cpufreq.modules.system_info import system_info


class MonitorModeView(Gtk.Box):
    def __init__(
        self,
        parent,
        report_view,
        refresh_interval=5,
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.parent = parent
        self.report_view = report_view
        self.running = True
        self.refresh_interval = refresh_interval
        self.connect("destroy", self._on_destroy)
        self._refresh_bridge = GtkRefreshBridge(
            self._collect_report,
            component="GTK monitor",
            diagnostics=diagnostics,
            active=lambda: self.running,
            interval=lambda: self.refresh_interval,
            on_report=lambda payload: self._update_display(*payload),
            on_error=self._show_error,
            thread_name="gtk-monitor-refresh",
        )
        self._refresh_coordinator = self._refresh_bridge.coordinator
        self._refresh_timer = GtkRefreshTimer(
            coordinator=self._refresh_coordinator,
            request=self._refresh_coordinator.request_if_idle,
            active=lambda: self.running,
            diagnostics=diagnostics,
            component="GTK monitor",
            interval=self.refresh_interval,
        )

        self.header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.header.set_margin_bottom(2)

        self.title = Gtk.Label(
            label="Monitor Mode",
            name="bold",
        )
        self.title.set_halign(Gtk.Align.START)
        self.header.pack_start(
            self.title, True, True, 0
        )

        self.back_button = Gtk.Button.new_with_label(
            "Back"
        )
        self.back_button.connect(
            "clicked",
            self.on_back_clicked,
        )
        self.header.pack_end(
            self.back_button, False, False, 0
        )

        self.pack_start(
            self.header, False, False, 0
        )

        self.error_label = Gtk.Label(label="")
        self.error_label.set_halign(Gtk.Align.START)
        self.error_label.set_xalign(0)
        self.error_label.set_no_show_all(True)
        self.pack_start(
            self.error_label, False, False, 0
        )

        suggestions = Gtk.Frame()
        heading = Gtk.Label(
            label="Suggestions",
            name="bold",
        )
        heading.set_halign(Gtk.Align.START)
        suggestions.set_label_widget(heading)

        grid = Gtk.Grid()
        grid.set_column_spacing(18)
        grid.set_row_spacing(4)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        suggestions.add(grid)

        governor_name = Gtk.Label(label="Governor")
        governor_name.set_halign(Gtk.Align.START)
        governor_name.set_xalign(0)

        self.governor_suggestion = Gtk.Label(
            label="—"
        )
        self.governor_suggestion.set_halign(
            Gtk.Align.START
        )
        self.governor_suggestion.set_xalign(0)

        grid.attach(governor_name, 0, 0, 1, 1)
        grid.attach(
            self.governor_suggestion,
            1, 0, 1, 1,
        )

        self.turbo_name = Gtk.Label(
            label="Turbo Boost"
        )
        self.turbo_name.set_halign(Gtk.Align.START)
        self.turbo_name.set_xalign(0)
        self.turbo_name.set_no_show_all(True)

        self.turbo_suggestion = Gtk.Label(
            label="—"
        )
        self.turbo_suggestion.set_halign(
            Gtk.Align.START
        )
        self.turbo_suggestion.set_xalign(0)
        self.turbo_suggestion.set_no_show_all(True)

        grid.attach(self.turbo_name, 0, 1, 1, 1)
        grid.attach(
            self.turbo_suggestion,
            1, 1, 1, 1,
        )

        self.report_view.prepend_right(
            suggestions
        )

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        self.scrolled.set_can_focus(True)
        self.scrolled.add(self.report_view)

        self.pack_start(
            self.scrolled, True, True, 0
        )

        self.refresh_in_thread()
        self._refresh_timer.start()

    @property
    def refresh_id(self):
        return self._refresh_timer.source_id

    def refresh_in_thread(self):
        if self.running:
            try:
                self._refresh_coordinator.request()
            except RuntimeError as error:
                # Keep Monitor open and let the periodic timer retry.
                self._show_error(str(error))
        return False

    def _collect_report(self):
        report = system_info.generate_system_report()
        recommendations = system_info.monitor_recommendations(report)
        return report, recommendations

    def _show_error(self, message):
        if not self.running:
            return False

        self.error_label.set_text(
            "Unable to refresh system information: "
            f"{message}"
        )
        self.error_label.show()

        return False

    def _update_display(self, report, recommendations):
        started = time.monotonic()
        try:
            return self._render_display(report, recommendations)
        except Exception:
            diagnostics.exception("GTK monitor render failed")
            raise
        finally:
            try:
                diagnostics.record_duration(
                    "GTK monitor render",
                    time.monotonic() - started,
                    slow_after=1.0,
                )
            except Exception:
                pass

    def _render_display(self, report, recommendations):
        if not self.running:
            return False

        self.error_label.hide()
        self.title.set_text(
            "Monitor Mode - "
            f"{time.strftime('%H:%M:%S')}"
        )
        self.report_view.apply_report(report)

        governor = recommendations.governor
        if governor.status == RecommendationStatus.UNAVAILABLE:
            governor_text = "Unavailable"
        elif governor.status == RecommendationStatus.INDETERMINATE:
            governor_text = "Unable to determine"
        elif governor.status == RecommendationStatus.CHANGE:
            governor_text = f"Use {governor.suggested}"
        else:
            governor_text = "No change suggested"
        self.governor_suggestion.set_text(governor_text)

        turbo = recommendations.turbo
        if report.is_turbo_on[0] is not None:
            self.turbo_name.show()
            self.turbo_suggestion.show()
            if turbo.status == RecommendationStatus.INDETERMINATE:
                turbo_text = "Unable to determine"
            elif turbo.status == RecommendationStatus.UNAVAILABLE:
                turbo_text = "Unavailable"
            elif turbo.status == RecommendationStatus.CHANGE:
                turbo_text = "Turn on" if turbo.suggested else "Turn off"
            else:
                turbo_text = "No change suggested"
            self.turbo_suggestion.set_text(turbo_text)
        else:
            self.turbo_name.hide()
            self.turbo_suggestion.hide()
        return False

    def on_back_clicked(self, _button):
        self.cleanup()
        self.parent.remove(self)
        self.parent.daemon_not_running()
        self.parent.show_all()

    def _on_destroy(self, *_args):
        self.cleanup()

    def cleanup(self):
        # Both Back and Gtk.Widget.destroy() can reach here.
        if not self.running:
            return
        self.running = False
        self._refresh_coordinator.close()

        self._refresh_timer.stop()
        try:
            diagnostics.info("GTK monitor view closed")
        except Exception:
            pass


