"""SSH/rsync reels sur loopback, compte jetable, aucun VPS/NAS ou service systeme utilise."""
import hashlib
import os
import pathlib
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if os.name == "posix":
    import pwd
AVAILABLE = os.name == "posix" and os.geteuid() == 0 and all(
    pathlib.Path(p).exists() for p in ("/usr/bin/rsync", "/usr/bin/rrsync", "/usr/sbin/sshd"))


@unittest.skipUnless(AVAILABLE, "Integration SSH root/rsync executee dans le job CI dedie")
class RestrictedRsync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="radio-rsync-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = pathlib.Path(cls.temp.name)
        cls.root.chmod(0o711)
        cls.user = "rvptest" + secrets.token_hex(4)
        password = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input=secrets.token_hex(32),
                                  text=True, capture_output=True, check=True).stdout.strip()
        result = subprocess.run(["useradd", "--system", "--user-group", "--no-create-home", "--home-dir", str(cls.root / "home"),
                                 "--shell", "/bin/sh", "--password", password, cls.user], capture_output=True)
        if result.returncode:
            raise RuntimeError("Creation du compte jetable de test impossible.")
        cls.addClassCleanup(lambda: subprocess.run(["userdel", cls.user], capture_output=True))
        uid, gid = pwd.getpwnam(cls.user).pw_uid, pwd.getpwnam(cls.user).pw_gid
        home = cls.root / "home"; home.mkdir(mode=0o755)
        cls.export = cls.root / "export"; cls.export.mkdir(mode=0o750)
        os.chown(cls.export, 0, gid)
        cls.id = "20261110T020000Z-aaaaaaaa"
        directory = cls.export / cls.id; directory.mkdir(mode=0o750); os.chown(directory, 0, gid)
        cls.payload = b"archive-test-no-production-secrets\n"
        (directory / "backup.tar.gz").write_bytes(cls.payload)
        digest = hashlib.sha256(cls.payload).hexdigest()
        (directory / "SHA256SUMS").write_text(digest + "  backup.tar.gz\n")
        for path in directory.iterdir():
            path.chmod(0o640); os.chown(path, 0, gid)
        cls.outside = cls.root / "outside-public"
        cls.outside.write_bytes(b"outside-export-must-not-be-readable-through-rsync\n")
        cls.outside.chmod(0o644)
        cls.secret = cls.root / "pki-secret"
        cls.secret.write_bytes(b"private-fixture-not-a-production-key"); cls.secret.chmod(0o600)
        cls.key = cls.root / "client-key"
        cls.hostkey = cls.root / "host-key"
        for key in (cls.key, cls.hostkey):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        # Seule la racine export est substituee ; le dispatch et rrsync sont ceux du projet/paquet.
        helper = cls.root / "export.sh"
        helper.write_text((ROOT / "scripts/export.sh").read_text().replace("ROOT=/var/lib/radio-vpn-export", "ROOT=" + str(cls.export)))
        helper.chmod(0o755)
        cls.trace = home / "commands"; cls.trace.touch(); os.chown(cls.trace, uid, gid); cls.trace.chmod(0o600)
        wrapper = cls.root / "record-command.sh"
        wrapper.write_text(f'#!/bin/sh\nprintf "%s\\n" "$SSH_ORIGINAL_COMMAND" >> "{cls.trace}"\nexec /bin/bash "{helper}"\n')
        wrapper.chmod(0o755)
        auth = home / "authorized_keys"
        auth.write_text(f'restrict,command="{wrapper}" ' + cls.key.with_suffix(".pub").read_text())
        auth.chmod(0o640); os.chown(auth, 0, gid)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); cls.port = sock.getsockname()[1]
        known = cls.root / "known_hosts"
        known.write_text(f"[127.0.0.1]:{cls.port} " + cls.hostkey.with_suffix(".pub").read_text())
        config = cls.root / "sshd_config"
        config.write_text(f'''Port {cls.port}
ListenAddress 127.0.0.1
HostKey {cls.hostkey}
PidFile {cls.root}/sshd.pid
AuthorizedKeysFile {auth}
AllowUsers {cls.user}
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes yes
LogLevel VERBOSE
''')
        pathlib.Path("/run/sshd").mkdir(mode=0o755, exist_ok=True)
        cls.log = cls.root / "sshd.log"
        cls.server = subprocess.Popen(["/usr/sbin/sshd", "-D", "-f", str(config), "-E", str(cls.log)])
        cls.addClassCleanup(cls.stop_server)
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2): break
            except OSError: time.sleep(0.1)
        else: raise RuntimeError("SSH loopback indisponible : " + cls.log.read_text())
        cls.ssh = ["ssh", "-T", "-p", str(cls.port), "-i", str(cls.key), "-o", "BatchMode=yes",
                   "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + str(known)]
        cls.remote = cls.user + "@127.0.0.1"

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try: cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired: cls.server.kill(); cls.server.wait()

    def ssh_command(self, command):
        return subprocess.run([*self.ssh, self.remote, command], capture_output=True, timeout=15)

    def transfer(self, source, destination, *options):
        import shlex
        return subprocess.run(["rsync", "-a", *options, "-e", shlex.join(self.ssh), source, str(destination)], capture_output=True, timeout=20)

    def test_real_pull_virtual_root_and_recorded_command(self):
        for index, options in enumerate(((), ("--rsync-path=/usr/bin/rsync",))):
            destination = self.root / ("download" + str(index)); destination.mkdir(exist_ok=True)
            result = self.transfer(self.remote + ":/", destination, *options)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            data = (destination / self.id / "backup.tar.gz").read_bytes()
            self.assertEqual(data, self.payload)
            self.assertEqual((destination / self.id / "SHA256SUMS").read_text().split()[0], hashlib.sha256(data).hexdigest())
        commands = self.trace.read_text()
        self.assertIn("rsync --server --sender", commands)
        print("Commande du client rsync reel : " + commands.splitlines()[-1])
        self.assertEqual(self.ssh_command("rsync --version").returncode, 0)
        self.assertEqual(self.ssh_command("/usr/bin/rsync --version").returncode, 0)

    def test_custom_export_protocol_still_works(self):
        self.assertIn(self.id.encode(), self.ssh_command("list").stdout)
        result = self.ssh_command("hash " + self.id)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.split()[0].decode(), hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(self.ssh_command("get " + self.id).stdout, self.payload)

    def test_push_remove_source_and_protected_args_refused(self):
        local = self.root / "local-file"; local.write_bytes(b"must-not-be-uploaded")
        self.assertNotEqual(self.transfer(str(local), self.remote + ":/uploaded").returncode, 0)
        for option in ("--remove-source-files", "--protect-args"):
            with self.subTest(option=option):
                result = self.transfer(self.remote + ":/", self.root / "negative", option)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.export / "uploaded").exists())
        self.assertEqual((self.export / self.id / "backup.tar.gz").read_bytes(), self.payload)

    def test_escape_symlink_and_arbitrary_commands_refused(self):
        link = self.export / "escape-link"
        link.symlink_to(self.outside)
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        for path in ("../outside-public", "/etc/passwd", "escape-link", "../pki-secret"):
            with self.subTest(path=path):
                self.assertNotEqual(self.transfer(self.remote + ":" + path, self.root / "escape").returncode, 0)
        self.assertNotEqual(self.transfer(self.remote + ":/", self.root / "escape", "-L").returncode, 0)
        for command in ("", "id", "uname -a", "cat /etc/passwd", "sh -c id", "rsync --version; id"):
            with self.subTest(command=command): self.assertNotEqual(self.ssh_command(command).returncode, 0)


if __name__ == "__main__": unittest.main()
