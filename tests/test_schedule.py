"""Horaire du cron genere sans installer de paquet ni modifier le systeme."""
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"


class Schedule(unittest.TestCase):
    def generate(self, answers=None):
        code = f'source "{(ROOT / "install.sh").as_posix()}"\nchoose_schedule\ncron_configuration\n'
        if answers is None:
            return subprocess.run([BASH, "-c", code], input="23:59\n", text=True, capture_output=True, timeout=10)
        import pty
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([BASH, "-c", code], stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            os.close(slave); slave = None
            os.write(master, answers.encode())
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate(); raise
            return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        finally:
            os.close(master)
            if slave is not None: os.close(slave)

    def assert_cron(self, result, minute, hour):
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2].split()[:6], [str(minute), str(hour), "*", "*", "*", "root"])
        self.assertTrue(lines[2].endswith("'/usr/local/sbin/radio-vpn-backup 2>&1 | /usr/bin/logger -t radio-vpn-backup'"))

    def test_noninteractive_install_keeps_default_without_prompt(self):
        result = self.generate()
        self.assert_cron(result, 17, 2)
        self.assertNotIn("Heure quotidienne", result.stderr)

    @unittest.skipIf(os.name == "nt", "Pseudo-terminal Linux")
    def test_interactive_default_and_valid_hours(self):
        for answer, minute, hour in (("\n", 17, 2), ("08:09\n", 9, 8), ("00:00\n", 0, 0), ("23:59\n", 59, 23)):
            with self.subTest(answer=answer):
                result = self.generate(answer)
                self.assert_cron(result, minute, hour)
                self.assertEqual(result.stderr.count("Heure quotidienne"), 1)

    @unittest.skipIf(os.name == "nt", "Pseudo-terminal Linux")
    def test_invalid_times_are_rejected_then_valid_time_is_used(self):
        for answer in ("24:00", "12:60", "2:17", "*/5", "03:45; id"):
            with self.subTest(answer=answer):
                result = self.generate(answer + "\n03:45\n")
                self.assert_cron(result, 45, 3)
                self.assertIn("Heure invalide", result.stderr)
                self.assertEqual(result.stderr.count("Heure quotidienne"), 2)


if __name__ == "__main__": unittest.main()
