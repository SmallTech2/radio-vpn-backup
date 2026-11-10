import hashlib
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Simulation du NAS avec les outils Linux")
class Pull(unittest.TestCase):
    def test_pull_integrity_idempotency_and_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "bin").mkdir()
            (root / "remote").mkdir()
            ids = [f"202611{day:02d}T020000Z-aaaaaaaa" for day in (8, 9, 10)]
            for name in ids:
                (root / "remote" / name).write_bytes((name + "-archive-fixture").encode())
            script = root / "bin/ssh"
            script.write_text('''#!/usr/bin/env python3
import hashlib,os,pathlib,sys
root=pathlib.Path(os.environ['FAKE_REMOTE'])
command=sys.argv[-1]
if command=='list':
 print('\\n'.join(p.name for p in sorted(root.iterdir())))
elif command.startswith('hash '):
 print(hashlib.sha256((root/command[5:]).read_bytes()).hexdigest())
elif command.startswith('get '):
 data=(root/command[4:]).read_bytes()
 if os.environ.get('FAKE_FAIL')=='yes':
  sys.stdout.buffer.write(data[:3]);sys.exit(1)
 sys.stdout.buffer.write(data)
else: sys.exit(1)
''')
            script.chmod(0o700)
            for name in ("key", "hosts"): (root / name).write_text("fixture\n")
            config = root / "nas.conf"
            config.write_text(f"VPS_NAME=fixture\nHOST=192.0.2.1\nPORT=22\nSSH_KEY={root}/key\nKNOWN_HOSTS={root}/hosts\nDESTINATION={root}/backups\nDAILY=7\nWEEKLY=4\n")
            env = dict(os.environ, PATH=str(root / "bin") + os.pathsep + os.environ["PATH"], FAKE_REMOTE=str(root / "remote"))

            def run(fail="no"):
                return subprocess.run(["bash", str(ROOT / "nas-pull.sh"), str(config)], env=dict(env, FAKE_FAIL=fail), capture_output=True)

            self.assertEqual(run().returncode, 0)
            self.assertEqual(run().returncode, 0)  # Fichiers existants reverifies.
            dest = root / "backups/fixture"
            self.assertEqual(len(list(dest.glob("*.tar.gz"))), 3)
            new = "20261111T020000Z-aaaaaaaa"
            (root / "remote" / new).write_bytes(b"new fixture")
            self.assertNotEqual(run("yes").returncode, 0)
            self.assertFalse((dest / (new + ".tar.gz")).exists())
            self.assertEqual(len(list(dest.glob("*.tar.gz"))), 3)
            self.assertFalse((dest / ".pull.lock").exists())
            self.assertFalse(list(dest.glob("*.partial")))
            self.assertEqual(run().returncode, 0)
            corrupt = dest / (new + ".tar.gz")
            corrupt.write_bytes(b"corrupt")
            self.assertNotEqual(run().returncode, 0)
