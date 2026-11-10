#!/usr/bin/env bash
# A lancer par le planificateur Synology ; aucune connexion initiee par le VPS.
set -Eeuo pipefail
umask 077
[[ $# == 1 ]] || { echo 'Usage : bash nas-pull.sh CONFIGURATION' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Ce fichier est du code d'administration local : acces reserve au compte de la tache.
source "$1"
[[ "$VPS_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ && "$HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || exit 1
[[ "$PORT" =~ ^[0-9]+$ && "$DAILY" =~ ^[0-9]+$ && "$WEEKLY" =~ ^[0-9]+$ ]] || exit 1
(( PORT > 0 && PORT <= 65535 && DAILY > 0 && WEEKLY > 0 )) || exit 1
[[ "$DESTINATION" == /* && -f "$SSH_KEY" && -f "$KNOWN_HOSTS" ]] || exit 1
DEST="$DESTINATION/$VPS_NAME"
mkdir -p "$DEST"
chmod 700 "$DEST"
# mkdir fournit un verrou compatible avec les outils DSM sans util-linux/flock.
mkdir "$DEST/.pull.lock" 2>/dev/null || { echo 'Recuperation deja en cours, ou verrou residuel a verifier.' >&2; exit 1; }
PART=''
cleanup(){
  local code=$?
  [[ -z "$PART" ]] || rm -f -- "$PART"
  rmdir "$DEST/.pull.lock"
  (( code == 0 )) || echo "ERREUR : recuperation $VPS_NAME incomplete ; anciennes sauvegardes conservees." >&2
  exit "$code"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
SSH=(ssh -T -p "$PORT" -i "$SSH_KEY" -o BatchMode=yes -o IdentitiesOnly=yes
     -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=15
     -o ServerAliveInterval=15 -o ServerAliveCountMax=3 "radio-vpn-backup@$HOST")
listing=$("${SSH[@]}" list)
[[ -n "$listing" ]] || { echo 'Aucune archive disponible.' >&2; exit 1; }
while IFS= read -r id; do
  [[ "$id" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || { echo 'Identifiant distant invalide.' >&2; exit 1; }
  checksum=$("${SSH[@]}" "hash $id")
  read -r hash name extra <<< "$checksum"
  [[ "$hash" =~ ^[0-9a-f]{64}$ && ( "$name" == backup.tar.gz || "$name" == backup.tar.gz.age ) && -z "$extra" ]] || exit 1
  file="$DEST/$id.${name#backup.}"
  if [[ ! -f "$file" ]]; then
    PART="$DEST/.$id.partial"
    "${SSH[@]}" "get $id" > "$PART"
    [[ $(sha256sum "$PART" | cut -d ' ' -f 1) == "$hash" ]] || { echo 'SHA-256 invalide apres transfert.' >&2; exit 1; }
    mv -- "$PART" "$file"
    PART=''
    printf '%s  %s\n' "$hash" "$(basename "$file")" > "$file.sha256"
  else
    [[ $(sha256sum "$file" | cut -d ' ' -f 1) == "$hash" ]] || { echo 'Archive locale corrompue.' >&2; exit 1; }
    printf '%s  %s\n' "$hash" "$(basename "$file")" > "$file.sha256"
  fi
  printf '%s Sauvegarde verifiee : %s/%s\n' "$(date -u +%FT%TZ)" "$VPS_NAME" "$id"
done <<< "$listing"
# Ne purger qu'apres une recuperation entierement reussie.
python3 "$ROOT/scripts/retention.py" "$DEST" "$DAILY" "$WEEKLY"
