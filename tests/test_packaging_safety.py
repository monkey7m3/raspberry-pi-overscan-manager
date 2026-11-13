"""Package-level safety checks for the recovery unit and maintainer script."""
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "build-deb.sh").read_text()


class PackagingSafetyTests(unittest.TestCase):
    def test_service_runs_before_multi_user_and_display_manager(self):
        self.assertIn("After=local-fs.target", BUILD)
        self.assertIn("Before=display-manager.service multi-user.target", BUILD)
        self.assertIn("WantedBy=multi-user.target", BUILD)
        self.assertIn("ConditionPathExists=/var/lib/raspberry-pi-overscan-manager/pending.json", BUILD)

    def test_install_enables_recovery(self):
        self.assertIn("systemctl enable raspberry-pi-overscan-rollback.service", BUILD)

    def test_recovery_script_is_packaged(self):
        self.assertIn("boot_audit.py boot_rollback.py", BUILD)
        self.assertIn("ExecStart=/usr/bin/python3 /usr/lib/raspberry-pi-overscan-manager/boot_rollback.py recover", BUILD)

    def test_boot_helper_requires_enabled_recovery(self):
        helper = (ROOT / "boot_helper.py").read_text()
        self.assertIn("rollback.service", helper)
        self.assertIn("refusing boot change", helper)

    def test_service_unit_has_no_network_dependency(self):
        unit = BUILD.split("<<'UNIT'\n", 1)[1].split("\nUNIT", 1)[0]
        self.assertNotIn("network-online.target", unit)


if __name__ == "__main__":
    unittest.main()
