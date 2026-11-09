"""Battery thresholds against a fake power_supply tree, not real hardware."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auto_cpufreq.battery_scripts import shared


class BatteryThresholdTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.power_supply = Path(tmp.name)
        (self.power_supply / "BAT0").mkdir()
        patcher = patch.object(shared, "POWER_SUPPLY_DIR", str(self.power_supply))
        patcher.start()
        self.addCleanup(patcher.stop)
        sleep = patch.object(shared.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def attribute(self, name, value=None):
        path = self.power_supply / "BAT0" / name
        if value is not None:
            path.write_text(value)
        return path

    def test_both_thresholds_are_written(self):
        start = self.attribute("charge_control_start_threshold", "0")
        end = self.attribute("charge_control_end_threshold", "100")

        device = shared.BatteryDevice()

        self.assertTrue(device.set_battery_thresholds("BAT0", 50, 60))
        self.assertEqual(start.read_text(), "50")
        self.assertEqual(end.read_text(), "60")

    def test_end_threshold_only_is_written(self):
        end = self.attribute("charge_control_end_threshold", "100")

        device = shared.BatteryDevice()

        self.assertTrue(device.set_battery_thresholds("BAT0", 50, 60))
        self.assertEqual(end.read_text(), "60")

    def test_end_threshold_only_is_applied_from_config(self):
        end = self.attribute("charge_control_end_threshold", "100")
        config = {
            "enable_thresholds": "true",
            "start_threshold": "50",
            "stop_threshold": "60",
        }

        device = shared.BatteryDevice()
        with patch.object(device, "_get_config", return_value=config):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                device.apply_threshold_settings()

        self.assertEqual(end.read_text(), "60")
        self.assertNotIn("ERROR", output.getvalue())

    def test_end_threshold_only_is_reported(self):
        self.attribute("charge_control_end_threshold", "60")

        device = shared.BatteryDevice()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            device.print_thresholds()

        self.assertEqual(device.get_current_threshold("BAT0"), (None, 60))
        self.assertIn("BAT0 stop threshold = 60", output.getvalue())
        self.assertNotIn("ERROR", output.getvalue())

    def test_start_threshold_without_end_threshold_is_unsupported(self):
        start = self.attribute("charge_control_start_threshold", "0")

        device = shared.BatteryDevice()

        self.assertFalse(device.set_battery_thresholds("BAT0", 50, 60))
        self.assertEqual(start.read_text(), "0")


if __name__ == "__main__":
    unittest.main()
