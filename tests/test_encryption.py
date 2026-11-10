import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"


class Publication(unittest.TestCase):
    def publish(self, work, enabled, recipients=""):
        code = f'source "{(ROOT / "scripts/backup.sh").as_posix()}"\nWORK="$TEST_WORK"\nENCRYPT="$TEST_ENCRYPT"\nRECIPIENTS="$TEST_RECIPIENTS"\n'
        if not enabled:
            code += 'age(){ echo forbidden > "$WORK/age-called"; return 99; }\n'
        code += 'prepare_publication\n'
        return subprocess.run([BASH], input=code, text=True, capture_output=True,
                              env=dict(os.environ, TEST_WORK=work.as_posix(), TEST_ENCRYPT=str(enabled).lower(), TEST_RECIPIENTS=str(recipients)))

    def test_default_plain_without_age(self):
        with tempfile.TemporaryDirectory() as directory:
            work = pathlib.Path(directory)
            (work / "backup.tar.gz").write_bytes(b"gzip fixture")
            result = self.publish(work, False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((work / "age-called").exists())
            self.assertEqual((work / "publish/backup.tar.gz").read_bytes(), b"gzip fixture")
            self.assertIn("backup.tar.gz", (work / "publish/SHA256SUMS").read_text())
        self.assertIn("ENCRYPT=false", (ROOT / "install.sh").read_text())

    @unittest.skipUnless(shutil.which("age"), "Mode age teste dans le job CI avec age")
    def test_optional_encryption_reuses_initial_age_format(self):
        with tempfile.TemporaryDirectory() as directory:
            work = pathlib.Path(directory)
            identity, recipients = work / "identity", work / "recipients"
            subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
            with recipients.open("wb") as output:
                subprocess.run(["age-keygen", "-y", str(identity)], check=True, stdout=output)
            original = b"archive fixture"
            (work / "backup.tar.gz").write_bytes(original)
            result = self.publish(work, True, recipients)
            self.assertEqual(result.returncode, 0, result.stderr)
            archive = work / "publish/backup.tar.gz.age"
            self.assertTrue(archive.read_bytes().startswith(b"age-encryption.org/v1\n"))
            result = subprocess.run(["age", "-d", "-i", str(identity), str(archive)], capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, original)
            self.assertIn("backup.tar.gz.age", (work / "publish/SHA256SUMS").read_text())


if __name__ == "__main__": unittest.main()
