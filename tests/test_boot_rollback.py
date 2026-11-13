"""Isolated tests: no root, no reboot, no real boot file writes."""
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import boot_rollback as rollback


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.state = root / "pending.json"
        self.cmdline = root / "cmdline.txt"
        self.old = b"console=tty1 video=HDMI-A-1:margin_left=76\n"
        self.new = b"console=tty1 video=HDMI-A-1:margin_left=77\n"
        self.cmdline.write_bytes(self.old)
        self.boot = "boot-0"
        patcher = patch.object(rollback, "current_boot_id", side_effect=lambda: self.boot)
        patcher.start()
        self.addCleanup(patcher.stop)

    def arm(self):
        rollback.arm(self.old, self.new, self.state)

    def test_full_recovery_after_two_reboots(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.assertIn("Waiting", rollback.recover(self.state, self.cmdline))
        self.boot = "boot-1"
        self.assertIn("First test boot", rollback.recover(self.state, self.cmdline))
        self.assertEqual(self.cmdline.read_bytes(), self.new)
        self.assertIn("Awaiting", rollback.recover(self.state, self.cmdline))
        self.boot = "boot-2"
        with patch("subprocess.run") as run:
            self.assertIn("restored", rollback.recover(self.state, self.cmdline))
            run.assert_called_once_with(["/usr/bin/systemctl", "--no-block", "reboot"], check=True)
        self.assertEqual(self.cmdline.read_bytes(), self.old)
        self.assertFalse(self.state.exists())

    def test_confirmation_keeps_settings(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        with self.assertRaises(RuntimeError):
            rollback.confirm(self.state, self.cmdline)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        rollback.confirm(self.state, self.cmdline)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.cmdline.read_bytes(), self.new)

    def test_confirm_rejects_unregistered_test_boot(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        with self.assertRaisesRegex(RuntimeError, "not registered"):
            rollback.confirm(self.state, self.cmdline)
        self.assertTrue(self.state.exists())

    def test_confirm_rejects_subsequent_boot_without_recovery(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        self.boot = "boot-2"
        with self.assertRaisesRegex(RuntimeError, "not registered"):
            rollback.confirm(self.state, self.cmdline)

    def test_crash_before_boot_file_write(self):
        self.arm()
        self.boot = "boot-1"
        self.assertIn("Original configuration present", rollback.recover(self.state, self.cmdline))
        self.assertFalse(self.state.exists())
        self.assertEqual(self.cmdline.read_bytes(), self.old)

    def test_external_change_not_overwritten(self):
        self.arm()
        self.cmdline.write_bytes(b"unexpected change\n")
        self.boot = "boot-1"
        with self.assertRaises(RuntimeError):
            rollback.recover(self.state, self.cmdline)
        self.assertTrue(self.state.exists())

    def test_state_file_is_private(self):
        self.arm()
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)

    def test_restore_preserves_boot_file_permissions(self):
        self.cmdline.chmod(0o640)
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        self.boot = "boot-2"
        with patch("subprocess.run"):
            rollback.recover(self.state, self.cmdline)
        self.assertEqual(stat.S_IMODE(self.cmdline.stat().st_mode), 0o640)

    def test_timeout_restores_and_requests_reboot(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        with patch("subprocess.run") as run:
            self.assertIn("reboot requested", rollback.expire(self.state, self.cmdline))
            run.assert_called_once_with(
                ["/usr/bin/systemctl", "--no-block", "reboot"], check=True
            )
        self.assertEqual(self.cmdline.read_bytes(), self.old)
        self.assertFalse(self.state.exists())

    def test_failed_reboot_request_preserves_recovery_record(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        with patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(1, "systemctl")):
            with self.assertRaises(__import__("subprocess").CalledProcessError):
                rollback.expire(self.state, self.cmdline)
        self.assertEqual(self.cmdline.read_bytes(), self.old)
        self.assertTrue(self.state.exists())
        self.boot = "boot-2"
        self.assertIn("never completed", rollback.recover(self.state, self.cmdline))
        self.assertFalse(self.state.exists())

    def test_timeout_does_not_reboot_staging_boot(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        with patch("subprocess.run") as run:
            self.assertIn("No active", rollback.expire(self.state, self.cmdline))
            run.assert_not_called()

    def test_timeout_after_confirmation_is_noop(self):
        self.arm()
        self.cmdline.write_bytes(self.new)
        self.boot = "boot-1"
        rollback.recover(self.state, self.cmdline)
        rollback.confirm(self.state, self.cmdline)
        with patch("subprocess.run") as run:
            self.assertIn("No active", rollback.expire(self.state, self.cmdline))
            run.assert_not_called()

    def test_second_transaction_rejected(self):
        self.arm()
        with self.assertRaises(RuntimeError):
            self.arm()

    def test_confirm_requires_expected_cmdline(self):
        self.arm()
        self.boot = "boot-1"
        self.cmdline.write_bytes(b"modified\n")
        with self.assertRaises(RuntimeError):
            rollback.confirm(self.state, self.cmdline)


if __name__ == "__main__":
    unittest.main()
