import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"


class Lifecycle(unittest.TestCase):
    def test_oneshot_activating_wait_error_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = pathlib.Path(directory) / "state"
            for mode, expected in (("normal", 0), ("error", 1), ("unknown", 1), ("timeout", 1)):
                with self.subTest(mode=mode):
                    trace.write_text("0")
                    script = f'source "{(ROOT / "scripts/backup.sh").as_posix()}"\n' + r'''
systemctl(){
 [[ "$MODE" != error ]] || return 1
 if [[ "$MODE" == unknown ]]; then echo mystery; return; fi
 local n; read -r n < "$TRACE" || true
 printf '%s\n' "$((n+1))" > "$TRACE"
 if [[ "$MODE" == timeout || "$n" == 0 ]]; then echo activating
 elif [[ "$n" == 1 ]]; then echo active
 else echo inactive; fi
}
sleep(){ :; }
wait_crl
'''
                    result = subprocess.run([BASH], input=script, text=True, capture_output=True,
                                            env=dict(os.environ, MODE=mode, TRACE=trace.as_posix()))
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if mode == "normal": self.assertEqual(trace.read_text().strip(), "3")

    def test_failure_resumes_ui_and_crl_but_never_vpn(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = pathlib.Path(directory) / "trace"
            work = pathlib.Path(directory) / "work"; work.mkdir()
            script = f'source "{(ROOT / "scripts/backup.sh").as_posix()}"\n' + r'''
systemctl(){ printf '%s\n' "$*" >> "$TRACE"; }
WORK="$TEST_WORK"; UI=true; TIMER=true
trap cleanup EXIT
false
'''
            result = subprocess.run([BASH], input=script, text=True, capture_output=True,
                                    env=dict(os.environ, TRACE=trace.as_posix(), TEST_WORK=work.as_posix()))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(trace.read_text().splitlines(), ["start openvpn-ui.service", "start radio-renew-crl.timer"])
            self.assertFalse(work.exists())


if __name__ == "__main__": unittest.main()
