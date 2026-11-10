import copy
import datetime as dt
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import snapshot
from retention import retained
from fixtures import installation


class Retention(unittest.TestCase):
    def test_daily_weekly_and_duplicates(self):
        names = []
        for offset in range(50):
            day = dt.datetime(2026, 11, 10) - dt.timedelta(days=offset)
            names.extend(day.strftime("%Y%m%dT%H%M%SZ") + f"-{n:08x}.tar.gz.age" for n in (1, 2))
        keep = retained(names)
        self.assertEqual(len(keep), 9)  # Deux des quatre semaines sont deja dans les sept jours.
        self.assertTrue(all("-00000002." in n for n in keep))


@unittest.skipIf(os.name == "nt", "Integration Linux (cp, uid/gid et OpenSSL)")
class Snapshot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = pathlib.Path(self.temp.name)
        self.root = self.folder / "root"
        self.root.mkdir()
        installation(self.root, snapshot)

    def archive(self):
        snapshot.create(self.root, self.folder / "snapshot")
        path = self.folder / "backup.tar.gz"
        snapshot.pack(self.folder / "snapshot", path)
        return path

    def test_full_archive_inventory_modes_links_sqlite(self):
        archive = self.archive()
        manifest = snapshot.check(archive)
        self.assertEqual(manifest["format"], 1)
        self.assertEqual(manifest["files"]["usr/share/easy-rsa/pki/private/ca.key"]["mode"], 0o600)
        self.assertEqual(manifest["files"]["etc/openvpn/pki"]["target"], "/usr/share/easy-rsa/pki")
        self.assertEqual(manifest["deployment"]["network"], "10.3.0.0/16")

    def test_refuse_incomplete_ccd_and_missing_revocation(self):
        (self.root / "etc/openvpn/staticclients/client").unlink()
        with self.assertRaises(ValueError): snapshot.validate_pki(self.root)
        (self.root / "etc/openvpn/staticclients/client").write_text("ifconfig-push 10.3.0.10 255.255.0.0\n")
        index = self.root / "usr/share/easy-rsa/pki/index.txt"
        index.write_text(index.read_text().replace("\t03\t", "\t09\t"))
        with self.assertRaises(ValueError): snapshot.validate_pki(self.root)

    def test_tamper_traversal_and_duplicate_rejected(self):
        original = self.archive()
        for case in ("tamper", "traversal", "duplicate", "absolute", "device"):
            with self.subTest(case=case):
                dest = self.folder / (case + ".tar.gz")
                with tarfile.open(original) as source, tarfile.open(dest, "w:gz") as target:
                    for item in source.getmembers():
                        data = source.extractfile(item).read() if item.isfile() else None
                        if case == "tamper" and item.name.endswith("/ta.key"):
                            data = b"invalid\n"; item.size = len(data)
                        target.addfile(item, io.BytesIO(data) if data is not None else None)
                    extra = tarfile.TarInfo({"traversal": "../escape", "absolute": "/etc/passwd"}.get(case, "manifest.json" if case == "duplicate" else "device"))
                    if case == "device": extra.type = tarfile.CHRTYPE
                    if case != "tamper": target.addfile(extra)
                with self.assertRaises((ValueError, KeyError)): snapshot.check(dest)

    def test_age_roundtrip_and_ciphertext_corruption(self):
        if not shutil.which("age"): self.skipTest("age requis")
        archive = self.archive()
        identity, recipient = self.folder / "identity", self.folder / "recipient"
        subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
        with recipient.open("wb") as out:
            subprocess.run(["age-keygen", "-y", str(identity)], check=True, stdout=out)
        encrypted, decrypted = self.folder / "backup.age", self.folder / "decrypted.tar.gz"
        subprocess.run(["age", "-R", str(recipient), "-o", str(encrypted), str(archive)], check=True)
        subprocess.run(["age", "-d", "-i", str(identity), "-o", str(decrypted), str(encrypted)], check=True)
        self.assertEqual(archive.read_bytes(), decrypted.read_bytes())
        data = bytearray(encrypted.read_bytes()); data[-1] ^= 1; encrypted.write_bytes(data)
        failed = subprocess.run(["age", "-d", "-i", str(identity), str(encrypted)], capture_output=True)
        self.assertNotEqual(failed.returncode, 0)


class AccessPolicy(unittest.TestCase):
    def test_export_rejects_arbitrary_commands(self):
        bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"
        for command in ("", "sh", "get ../../etc/shadow", "get 20261110T120000Z-aaaaaaaa;id", "hash /etc/passwd", "scp -f /etc/shadow"):
            result = subprocess.run([bash, str(ROOT / "scripts/export.sh")], env=dict(os.environ, SSH_ORIGINAL_COMMAND=command), capture_output=True)
            self.assertNotEqual(result.returncode, 0, command)
        source = (ROOT / "scripts/backup.sh").read_text()
        self.assertNotIn("stop openvpn@", source)
        self.assertNotIn("restart openvpn@", source)
        self.assertLess(source.index('mv -T -- "$WORK/publish"'), source.index('"$BASE/snapshot.py" prune'))


if __name__ == "__main__": unittest.main()
