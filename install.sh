#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 && $# == 1 ]] || { echo 'Usage : sudo bash install.sh CLE_PUBLIQUE_SSH_NAS' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || exit 1
[[ -f "$1" ]] || exit 1
[[ $(grep -c '^ssh-ed25519 ' "$1") == 1 && $(wc -l < "$1") == 1 ]] || { echo 'Une seule cle publique ED25519 attendue.' >&2; exit 1; }
ssh-keygen -lf "$1" >/dev/null
! getent passwd radio-vpn-backup >/dev/null || { echo 'Compte radio-vpn-backup existant : installation refusee.' >&2; exit 1; }
[[ ! -e /etc/radio-vpn-backup.conf ]] || exit 1
apt-get update
apt-get install -y --no-install-recommends python3 cron util-linux rsync
[[ -x /usr/bin/rrsync ]] || { echo 'rrsync fourni par rsync est requis.' >&2; exit 1; }
python3 "$ROOT/scripts/snapshot.py" preflight /
install -d -m 755 /usr/local/lib/radio-vpn-backup
install -m 755 "$ROOT/scripts/backup.sh" "$ROOT/scripts/export.sh" "$ROOT/scripts/snapshot.py" /usr/local/lib/radio-vpn-backup/
ln -s /usr/local/lib/radio-vpn-backup/backup.sh /usr/local/sbin/radio-vpn-backup
useradd --system --user-group --home-dir /var/lib/radio-vpn-backup-user --shell /bin/sh radio-vpn-backup
install -d -m 700 /var/lib/radio-vpn-backup
install -d -m 750 -o root -g radio-vpn-backup /var/lib/radio-vpn-export
install -d -m 755 -o root -g root /var/lib/radio-vpn-backup-user
install -d -m 750 -o root -g radio-vpn-backup /var/lib/radio-vpn-backup-user/.ssh
{ printf 'restrict,command="/usr/local/lib/radio-vpn-backup/export.sh" '; cat -- "$1"; } > /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
chown root:radio-vpn-backup /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
chmod 640 /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
printf 'KEEP_VPS=3\nENCRYPT=false\n' > /etc/radio-vpn-backup.conf
chmod 600 /etc/radio-vpn-backup.conf
# logger collecte les messages sans creer un nouveau journal non gere par logrotate.
printf 'SHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n17 2 * * * root /bin/bash -o pipefail -c '\''/usr/local/sbin/radio-vpn-backup 2>&1 | /usr/bin/logger -t radio-vpn-backup'\''\n' > /etc/cron.d/radio-vpn-backup
chmod 644 /etc/cron.d/radio-vpn-backup
systemctl enable --now cron
echo 'Installe. Configurer le NAS et tester une sauvegarde manuelle avant de compter sur cron.'
echo 'Aucune configuration SSH globale modifiee ; verifier AllowUsers/AllowGroups si personnalises.'
