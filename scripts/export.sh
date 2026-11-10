#!/usr/bin/env bash
# Commande forcee SSH : aucun shell arbitraire, aucun acces en ecriture.
set -Eeuo pipefail
ROOT=/var/lib/radio-vpn-export
request=${SSH_ORIGINAL_COMMAND:-}
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
  echo 'Commande refusee. Commandes permises : list, hash IDENTIFIANT, get IDENTIFIANT.' >&2
  exit 1
fi
