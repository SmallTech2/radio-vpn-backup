#!/usr/bin/env bash
# Commande forcee SSH : aucun shell arbitraire, aucun acces en ecriture.
set -Eeuo pipefail
ROOT=/var/lib/radio-vpn-export
request=${SSH_ORIGINAL_COMMAND:-}
# Le chemin de cette commande forcee reste identique pour les cles deja installees.
# Ne jamais interpreter SSH_ORIGINAL_COMMAND avec eval ou sh -c.
case "$request" in
  'rsync --version'|'/usr/bin/rsync --version') exec /usr/bin/rsync --version ;;
  'rsync --server '*|'/usr/bin/rsync --server '*)
    [[ -x /usr/bin/rrsync ]] || { echo 'rrsync manquant : installer le paquet rsync.' >&2; exit 1; }
    if [[ "$request" == /usr/bin/rsync\ * ]]; then
      export SSH_ORIGINAL_COMMAND="rsync ${request#/usr/bin/rsync }"
    fi
    # Les chemins clients sont relatifs a cette racine virtuelle, jamais au VPS entier.
    exec /usr/bin/rrsync -ro -no-del "$ROOT"
    ;;
esac
if [[ "$request" == list ]]; then
  find "$ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | grep -E '^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$' | sort
elif [[ "$request" =~ ^(get|hash)[[:space:]]([0-9]{8}T[0-9]{6}Z-[0-9a-f]{8})$ ]]; then
  action=${BASH_REMATCH[1]}; id=${BASH_REMATCH[2]}
  [[ -d "$ROOT/$id" && ! -L "$ROOT/$id" ]] || exit 1
  [[ -f "$ROOT/$id/SHA256SUMS" && ! -L "$ROOT/$id/SHA256SUMS" ]] || exit 1
  read -r hash name extra < "$ROOT/$id/SHA256SUMS"
  [[ "$hash" =~ ^[0-9a-f]{64}$ && ( "$name" == backup.tar.gz || "$name" == backup.tar.gz.age ) && -z "$extra" ]] || exit 1
  if [[ "$action" == get ]]; then
    [[ -f "$ROOT/$id/$name" && ! -L "$ROOT/$id/$name" ]] || exit 1
    exec cat -- "$ROOT/$id/$name"
  else
    printf '%s  %s\n' "$hash" "$name"
  fi
else
  logger -t radio-vpn-backup-ssh 'Commande SSH refusee (commande libre ou sonde non autorisee ; arguments non journalises).' || true
  echo 'Commande refusee : export list/hash/get ou rsync restreint en lecture seule uniquement.' >&2
  exit 1
fi
