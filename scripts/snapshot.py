#!/usr/bin/env python3
"""Format de sauvegarde v1. Python standard : SQLite, inventaire et controles tar."""
import datetime as dt
import hashlib
import io
import ipaddress
import json
import os
import pathlib
import posixpath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile

TREES = ("usr/share/easy-rsa", "etc/openvpn", "opt/openvpn-ui-runtime", "opt/scripts")
REQUIRED_FILES = (
    "etc/openvpn-ui.env", "etc/radio-vpn-deployed",
    "etc/systemd/system/openvpn-ui.service",
    "etc/systemd/system/radio-renew-crl.service", "etc/systemd/system/radio-renew-crl.timer",
    "usr/local/sbin/radio-renew-crl",
)
OPTIONAL_FILES = (
    "usr/local/bin/radio-secure-ssh",
    "etc/nftables.conf", "etc/sysctl.d/99-radio-disable-ipv6.conf",
    "etc/logrotate.d/openvpn", "etc/systemd/journald.conf.d/99-radio-limits.conf",
    "etc/ssh/sshd_config", "etc/ssh/sshd_config.d/00-radio.conf",
)
FILES = REQUIRED_FILES + OPTIONAL_FILES
CORE_FILES = ("etc/openvpn/server.conf", "etc/openvpn/config/client.conf")
PKI_FILES = ("ca.crt", "private/ca.key", "private/server.key", "issued/server.crt", "ta.key",
             "dh.pem", "index.txt", "serial", "crlnumber", "vars", "crl.pem")
ALLOWED = TREES + FILES
ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")


def metadata(root):
    values = {}
    for line in (root / "etc/radio-vpn-deployed").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    # La version est une information d'origine, pas une liste de versions autorisees.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", values.get("release_tag", "")):
        raise ValueError("Nom de version absent ou invalide dans les metadonnees.")
    for key in ("release_source_commit", "binary_source_commit"):
        if not re.fullmatch(r"[a-f0-9]{40}", values.get(key, "")):
            raise ValueError("Metadonnees de version invalides.")
    ip = ipaddress.IPv4Address(values["public_ip"])
    if ip.is_unspecified or ip.is_loopback or ip.is_multicast:
        raise ValueError("Adresse publique invalide.")
    network = ipaddress.IPv4Network(values["network"], strict=True)
    private = [ipaddress.IPv4Network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    if not 16 <= network.prefixlen <= 29 or not any(network.subnet_of(n) for n in private):
        raise ValueError("Reseau VPN invalide.")
    return values


def preflight(root):
    metadata(root)
    for name in TREES + ("usr/share/easy-rsa/pki", "etc/openvpn/staticclients"):
        if not (root / name).is_dir():
            raise ValueError("Element radio-vpn manquant : " + name)
    for name in REQUIRED_FILES + CORE_FILES + tuple("usr/share/easy-rsa/pki/" + p for p in PKI_FILES):
        if not (root / name).is_file():
            raise ValueError("Fichier indispensable manquant : " + name)
    for name in OPTIONAL_FILES:
        path = root / name
        if (path.exists() or path.is_symlink()) and not path.is_file():
            raise ValueError("Fichier facultatif present mais invalide : " + name)
    runtime = root / "opt/openvpn-ui-runtime"
    for name in ("openvpn-ui", "conf/app.conf", "db/data.db"):
        if not (runtime / name).is_file() or (runtime / name).is_symlink():
            raise ValueError("Runtime incomplet : " + name)
    for name in ("static", "views", "swagger"):
        if not (runtime / name).is_dir() or (runtime / name).is_symlink():
            raise ValueError("Ressources UI absentes : " + name)
    if not os.access(runtime / "openvpn-ui", os.X_OK):
        raise ValueError("Binaire UI non executable.")
    link = root / "etc/openvpn/pki"
    if not link.is_symlink() or os.readlink(link) != "/usr/share/easy-rsa/pki":
        raise ValueError("Lien PKI radio-vpn inattendu.")


def record(path):
    info = path.lstat()
    item = dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
    if path.is_symlink():
        item.update(type="link", target=os.readlink(path))
    elif path.is_dir():
        item.update(type="dir")
    elif path.is_file():
        with path.open("rb") as stream:
            item.update(type="file", sha256=digest(stream))
    else:
        raise ValueError("Fichier special refuse.")
    return item


def inventory(payload):
    return {p.relative_to(payload).as_posix(): record(p) for p in sorted(payload.rglob("*"))}


def create(root, output):
    preflight(root)
    output.mkdir(mode=0o700)
    payload = output / "payload"
    payload.mkdir(mode=0o700)
    # cp -a preserve egalement les proprietaires et les attributs ; aucune dereference PKI.
    paths = [name for name in TREES if name != "opt/openvpn-ui-runtime"]
    paths += list(REQUIRED_FILES)
    paths += [name for name in OPTIONAL_FILES if (root / name).exists()]
    paths += [p.relative_to(root).as_posix() for p in (root / "opt/openvpn-ui-runtime").iterdir() if p.name != "logs"]
    size = sum(p.stat().st_size for name in paths for p in ([root / name] if (root / name).is_file() else (root / name).rglob("*")) if p.is_file() and not p.is_symlink())
    if shutil.disk_usage(output).free < size * 2 + 64 * 1024 * 1024:
        raise ValueError("Espace libre insuffisant pour preparer la sauvegarde.")
    subprocess.run(["cp", "-a", "--parents", *paths, str(payload)], cwd=root, check=True)
    db = payload / "opt/openvpn-ui-runtime/db/data.db"
    db_mode = stat.S_IMODE(db.stat().st_mode)
    db_uid, db_gid = db.stat().st_uid, db.stat().st_gid
    db.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        pathlib.Path(str(db) + suffix).unlink(missing_ok=True)
    with sqlite3.connect(f"file:{root / 'opt/openvpn-ui-runtime/db/data.db'}?mode=ro", uri=True) as source:
        with sqlite3.connect(db) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite incoherente.")
    os.chmod(db, db_mode)
    os.chown(db, db_uid, db_gid)
    # Exclure les journaux eventuellement places dans le repertoire applicatif.
    for path in (payload / "opt/openvpn-ui-runtime/logs", payload / "etc/openvpn/openvpn-status.log"):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
    validate_configuration(payload)
    validate_pki(payload)
    data = inventory(payload)
    details = dict(format=1, created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                   deployment=metadata(root), files=data)
    details["missing_optional"] = [name for name in OPTIONAL_FILES if not (payload / name).exists()]
    details["packages"] = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}=${Version}\n"]).decode().splitlines()
    details["admin_candidates"] = []
    import grp
    import pwd
    sudo = grp.getgrnam("sudo")
    for user in pwd.getpwall():
        if user.pw_uid >= 1000 and user.pw_uid != 65534 and (user.pw_name in sudo.gr_mem or user.pw_gid == sudo.gr_gid):
            details["admin_candidates"].append(user.pw_name)
    (output / "manifest.json").write_text(json.dumps(details, indent=2) + "\n")
    lines = [f"{v['type']} {v['mode']:04o} {v['uid']}:{v['gid']} {k}" +
             (" -> " + v["target"] if v["type"] == "link" else "") for k, v in data.items()]
    (output / "INVENTORY.txt").write_text("\n".join(lines) + "\n")


def command(*args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise ValueError("Controle echoue : " + args[0] + " " + args[1])
    return result.stdout


def validate_pki(payload):
    pki = payload / "usr/share/easy-rsa/pki"
    for name in PKI_FILES:
        if not (pki / name).is_file():
            raise ValueError("PKI incomplete : " + name)
    for name in ("ca", "server"):
        cert = pki / ("ca.crt" if name == "ca" else "issued/server.crt")
        public = command("openssl", "x509", "-in", str(cert), "-pubkey", "-noout")
        private = command("openssl", "pkey", "-in", str(pki / f"private/{name}.key"), "-passin", "pass:", "-pubout")
        if public != private:
            raise ValueError("Cle et certificat incompatibles.")
    command("openssl", "verify", "-no_check_time", "-CAfile", str(pki / "ca.crt"), str(pki / "issued/server.crt"))
    command("openssl", "crl", "-in", str(pki / "crl.pem"), "-verify", "-CAfile", str(pki / "ca.crt"), "-noout")
    crl = command("openssl", "crl", "-in", str(pki / "crl.pem"), "-text", "-noout").decode()
    revoked = {int(s.replace(":", ""), 16) for s in re.findall(r"Serial Number:\s*([0-9a-fA-F:]+)", crl)}
    records = []
    for line in (pki / "index.txt").read_text().splitlines():
        fields = line.split("\t")
        if len(fields) != 6 or fields[0] not in ("V", "R", "E"):
            raise ValueError("Index PKI incomplet ou invalide.")
        if fields[0] == "R" and int(fields[3], 16) not in revoked:
            raise ValueError("Une revocation de l index manque dans la CRL.")
        if fields[0] == "V":
            match = re.search(r"/CN=([^/]+)", fields[5])
            if not match or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", match[1]):
                raise ValueError("Nom de certificat invalide.")
            name = match[1]
            cert = pki / f"issued/{name}.crt"
            serial = command("openssl", "x509", "-in", str(cert), "-serial", "-noout").decode().strip().partition("=")[2]
            if int(serial, 16) != int(fields[3], 16) or not (pki / f"private/{name}.key").is_file():
                raise ValueError("Certificat valide incomplet ou serie incoherente.")
            if name != "server":
                ccd = payload / f"etc/openvpn/staticclients/{name}"
                ip = re.search(r"/LocalIP=([^/]+)", fields[5])
                if not ip or not ccd.is_file() or not re.search(r"^ifconfig-push\s+" + re.escape(ip[1]) + r"\s", ccd.read_text(), re.M):
                    raise ValueError("Certificat et IP fixe incoherents.")
        records.append(fields[3].upper())
    if len(records) != len(set(records)):
        raise ValueError("Serie dupliquee dans l index.")


def validate_configuration(payload):
    import shlex
    networks = []
    for line in (payload / "etc/openvpn/server.conf").read_text().splitlines():
        fields = shlex.split(line, comments=True)
        if fields and fields[0] == "server":
            if len(fields) < 3:
                raise ValueError("Directive server OpenVPN incomplete.")
            networks.append(ipaddress.IPv4Network(fields[1] + "/" + fields[2], strict=True))
    expected = ipaddress.IPv4Network(metadata(payload)["network"], strict=True)
    if networks != [expected]:
        raise ValueError("Reseau OpenVPN incoherent avec les metadonnees de deploiement.")


def pack(folder, archive):
    with tarfile.open(archive, "w:gz", dereference=False) as tar:
        for path in sorted(folder.rglob("*")):
            info = tar.gettarinfo(str(path), path.relative_to(folder).as_posix())
            # Eviter la conversion implicite de fichiers en hardlinks.
            if path.is_file() and not path.is_symlink():
                info.type = tarfile.REGTYPE
                info.linkname = ""
                info.size = path.stat().st_size
                with path.open("rb") as stream:
                    tar.addfile(info, stream)
            else:
                tar.addfile(info)


def allowed(name):
    return any(name == top or name.startswith(top + "/") for top in TREES) or name in FILES


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
    return value.hexdigest()


def check(archive):
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise ValueError("Entrees tar dupliquees.")
        for member in members:
            p = pathlib.PurePosixPath(member.name)
            if p.is_absolute() or ".." in p.parts or str(p) != member.name or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError("Chemin ou type tar dangereux.")
            if member.mode & 0o7000:
                raise ValueError("Permissions privilegiees refusees.")
        manifest = json.load(tar.extractfile("manifest.json"))
        if manifest.get("format") != 1:
            raise ValueError("Format non pris en charge.")
        expected = manifest["files"]
        actual = {m.name.removeprefix("payload/"): m for m in members if m.name.startswith("payload/")}
        if set(actual) != set(expected) or set(names) != {"manifest.json", "INVENTORY.txt", "payload"} | {"payload/" + n for n in expected}:
            raise ValueError("Inventaire incomplet.")
        links = {n for n, v in expected.items() if v["type"] == "link"}
        for name, member in actual.items():
            # Les repertoires parents de la liste explicite sont necessaires au tar.
            if not allowed(name) and not any(top.startswith(name + "/") for top in ALLOWED):
                raise ValueError("Chemin hors perimetre.")
            if any(str(parent) in links for parent in pathlib.PurePosixPath(name).parents):
                raise ValueError("Ecriture au travers d un lien refusee.")
            entry = expected[name]
            kind = "link" if member.issym() else "dir" if member.isdir() else "file"
            if (kind, member.mode, member.uid, member.gid) != (entry["type"], entry["mode"], entry["uid"], entry["gid"]):
                raise ValueError("Metadonnees incompatibles.")
            if member.isfile() and digest(tar.extractfile(member)) != entry["sha256"]:
                raise ValueError("Empreinte interne invalide.")
            if member.issym():
                permitted = {"etc/openvpn/pki": "/usr/share/easy-rsa/pki", "opt/scripts/qrencode": "/usr/bin/qrencode"}
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname)) if not member.linkname.startswith("/") else member.linkname.lstrip("/")
                safe = (not member.linkname.startswith("/") and name.startswith("usr/share/easy-rsa/") and target.startswith("usr/share/easy-rsa/")) or permitted.get(name) == member.linkname
                if member.linkname != entry["target"] or not safe:
                    raise ValueError("Lien symbolique non pris en charge.")
        return manifest


def prune(folder, count):
    paths = sorted(p for p in folder.iterdir() if ID.fullmatch(p.name) and p.is_dir() and not p.is_symlink())
    for path in paths[:-count]:
        shutil.rmtree(path)


def main():
    action, *args = sys.argv[1:]
    if action == "preflight": preflight(pathlib.Path(args[0]))
    elif action == "create": create(*map(pathlib.Path, args))
    elif action == "pack": pack(*map(pathlib.Path, args))
    elif action == "check": check(pathlib.Path(args[0]))
    elif action == "prune": prune(pathlib.Path(args[0]), int(args[1]))
    else: raise ValueError("Action inconnue.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Aucun contenu de certificat, de base ou de cle dans les logs.
        print("ERREUR sauvegarde : " + str(error), file=sys.stderr)
        sys.exit(1)
