"""Platform profile reads against a fake sysfs tree, not real hardware."""

import errno
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auto_cpufreq.modules.platform_profile import PlatformProfileManager


class PlatformProfileReadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        device = Path(tmp.name) / "platform-profile-0"
        device.mkdir()
        (device / "name").write_text("hp-wmi\n")
        (device / "choices").write_text("cool quiet balanced performance\n")
        self.profile = device / "profile"
        self.profile.write_text("balanced\n")

        # Like hp-wmi on some HP boards: every profile read fails with EINVAL.
        self.failing = True
        self.reads = 0
        read_text = Path.read_text

        def fake_read_text(path, *args, **kwargs):
            if path == self.profile:
                self.reads += 1
                if self.failing:
                    raise OSError(errno.EINVAL, "Invalid argument")
            return read_text(path, *args, **kwargs)

        for patcher in (
            patch.object(Path, "read_text", fake_read_text),
            patch.object(
                PlatformProfileManager, "_modern_paths", return_value=(device,)
            ),
            patch("psutil.cpu_percent", return_value=[]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        # A fresh import per test, so the report's state and the Python 3.9
        # import test are not affected.
        with patch.dict(sys.modules):
            from auto_cpufreq.modules.system_info import SystemInfo
        self.report = SystemInfo().generate_system_report

    def test_report_reads_unreadable_profile_once(self):
        for _ in range(3):
            report = self.report()

        self.assertEqual(self.reads, 1)
        self.assertEqual(report.platform_profile.status, "partial")

    def test_report_still_follows_readable_profile(self):
        self.failing = False
        self.assertEqual(
            self.report().platform_profile.current,
            "balanced",
        )
        self.profile.write_text("quiet\n")
        self.assertEqual(
            self.report().platform_profile.current,
            "quiet",
        )

    def test_default_manager_retries_unreadable_profile(self):
        manager = PlatformProfileManager()

        self.assertIsNone(manager.snapshot().current)
        self.failing = False
        self.assertEqual(manager.snapshot().current, "balanced")


if __name__ == "__main__":
    unittest.main()
