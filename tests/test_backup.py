import datetime as dt
import io
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import snapshot
from retention import retained, prune
from fixtures import installation


class Retention(unittest.TestCase):
    def test_daily_weekly_and_duplicates(self):
        names = []
        for offset in range(50):
            day = dt.datetime(2026, 11, 10) - dt.timedelta(days=offset)
            names.extend(day.strftime("%Y%m%dT%H%M%SZ") + f"-{n:08x}.tar.gz" for n in (1, 2))
        keep = retained(names)
        self.assertEqual(len(keep), 9)  # Deux des quatre semaines sont deja dans les sept jours.
        self.assertTrue(all("-00000002." in n for n in keep))

    def test_prune_plain_archives_and_sidecars_only(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = pathlib.Path(directory)
            names = []
            for offset in range(30):
                day = dt.datetime(2026, 11, 10) - dt.timedelta(days=offset)
                name = day.strftime("%Y%m%dT%H%M%SZ") + "-aaaaaaaa.tar.gz" + (".age" if offset % 2 else "")
                names.append(name)
                (folder / name).write_bytes(b"fixture")
                (folder / (name + ".sha256")).write_text("fixture\n")
            (folder / "notes.txt").write_text("keep\n")
            prune(folder, 3, 2)
            keep = retained(names, 3, 2)
            self.assertEqual({p.name for p in folder.iterdir() if p.name.endswith((".tar.gz", ".tar.gz.age"))}, keep)
            self.assertEqual({p.name.removesuffix(".sha256") for p in folder.glob("*.sha256")}, keep)
            self.assertEqual((folder / "notes.txt").read_text(), "keep\n")


class DeploymentMetadata(unittest.TestCase):
    def test_version_is_preserved_without_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "etc").mkdir()
            path = root / "etc/radio-vpn-deployed"
            for version in ("radio-v2.1", "radio-v2.4", "radio-v9.7", "custom-build"):
                with self.subTest(version=version):
                    content = (f"release_tag={version}\nrelease_source_commit=" + "a" * 40 +
                               "\nbinary_source_commit=" + "b" * 40 +
                               "\npublic_ip=198.51.100.10\nnetwork=10.3.0.0/16\n")
                    path.write_text(content)
                    self.assertEqual(snapshot.metadata(root)["release_tag"], version)
                    self.assertEqual(path.read_text(), content)
            path.write_text(content.replace("release_tag=custom-build", "release_tag="))
            with self.assertRaises(ValueError):
                snapshot.metadata(root)


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
        counter = "usr/share/easy-rsa/pki/crlnumber"
        (self.root / counter).write_bytes(b"42\n")
        archive = self.archive()
        manifest = snapshot.check(archive)
        self.assertIn(counter, manifest["files"])
        with tarfile.open(archive) as tar:
            self.assertEqual(tar.extractfile("payload/" + counter).read(), b"42\n")
        self.assertEqual(manifest["format"], 1)
        self.assertEqual(manifest["files"]["usr/share/easy-rsa/pki/private/ca.key"]["mode"], 0o600)
        self.assertEqual(manifest["files"]["etc/openvpn/pki"]["target"], "/usr/share/easy-rsa/pki")
        self.assertEqual(manifest["deployment"]["network"], "10.3.0.0/16")
        self.assertEqual(manifest["missing_optional"], [])
        self.assertTrue(set(snapshot.OPTIONAL_FILES).issubset(manifest["files"]))
        # Une archive classique peut etre lue directement et gzip detecte une troncature.
        self.assertEqual(subprocess.run(["gzip", "-t", str(archive)], capture_output=True).returncode, 0)
        archive.write_bytes(archive.read_bytes()[:-8])
        self.assertNotEqual(subprocess.run(["gzip", "-t", str(archive)], capture_output=True).returncode, 0)

    def test_v21_archive_without_optional_files_preserves_origin(self):
        metadata = self.root / "etc/radio-vpn-deployed"
        metadata.write_text(metadata.read_text().replace("radio-v2.4", "radio-v2.1"))
        original = metadata.read_bytes()
        for name in snapshot.OPTIONAL_FILES:
            (self.root / name).unlink()
        pki = self.root / "usr/share/easy-rsa/pki"
        self.assertFalse((pki / "crlnumber").exists())
        crl = (pki / "crl.pem").read_bytes()
        index = (pki / "index.txt").read_bytes()
        crl_text = snapshot.command("openssl", "crl", "-in", str(pki / "crl.pem"), "-text", "-noout")
        self.assertNotIn(b"CRL Number", crl_text)
        snapshot.preflight(self.root)
        manifest = snapshot.check(self.archive())
        self.assertNotIn("usr/share/easy-rsa/pki/crlnumber", manifest["files"])
        self.assertFalse((pki / "crlnumber").exists())
        for name, original_content in (("crl.pem", crl), ("index.txt", index)):
            self.assertEqual((pki / name).read_bytes(), original_content)
            self.assertEqual((self.folder / "snapshot/payload/usr/share/easy-rsa/pki" / name).read_bytes(), original_content)
        self.assertEqual(manifest["deployment"]["release_tag"], "radio-v2.1")
        self.assertEqual(manifest["missing_optional"], list(snapshot.OPTIONAL_FILES))
        self.assertTrue(set(snapshot.REQUIRED_FILES).issubset(manifest["files"]))
        self.assertFalse(set(snapshot.OPTIONAL_FILES).intersection(manifest["files"]))
        self.assertEqual(metadata.read_bytes(), original)
        self.assertEqual((self.folder / "snapshot/payload/etc/radio-vpn-deployed").read_bytes(), original)

    def test_required_components_remain_required(self):
        names = ("etc/openvpn/server.conf", "etc/openvpn/config/client.conf",
                 "usr/share/easy-rsa/pki/private/ca.key",
                 "usr/share/easy-rsa/pki/crl.pem",
                 "usr/share/easy-rsa/pki/index.txt",
                 "usr/share/easy-rsa/pki/serial",
                 "etc/systemd/system/radio-renew-crl.timer",
                 "opt/openvpn-ui-runtime/db/data.db")
        for name in names:
            with self.subTest(name=name):
                path = self.root / name
                content = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "manquant|incomplet"):
                    snapshot.preflight(self.root)
                path.write_bytes(content)

    def test_network_mismatch_refused_without_rewriting_metadata(self):
        metadata = self.root / "etc/radio-vpn-deployed"
        original = metadata.read_bytes()
        server = self.root / "etc/openvpn/server.conf"
        server.write_text(server.read_text().replace("server 10.3.0.0", "server 10.9.0.0"))
        with self.assertRaisesRegex(ValueError, "Reseau OpenVPN incoherent"):
            self.archive()
        self.assertEqual(metadata.read_bytes(), original)

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
