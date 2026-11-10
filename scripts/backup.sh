#!/usr/bin/env bash
# Copie privee coherente, puis publication d'un repertoire prive par renommage.
set -Eeuo pipefail
umask 077
BASE=/usr/local/lib/radio-vpn-backup
STATE=/var/lib/radio-vpn-backup
EXPORT=/var/lib/radio-vpn-export
WORK=''
UI=false
TIMER=false
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
die(){ log "ERREUR : $*" >&2; exit 1; }
prepare_publication(){
  local name=backup.tar.gz
  mkdir "$WORK/publish"
  if $ENCRYPT; then
    name=backup.tar.gz.age
    age -R "$RECIPIENTS" -o "$WORK/publish/$name" "$WORK/backup.tar.gz"
  else
    mv -- "$WORK/backup.tar.gz" "$WORK/publish/$name"
  fi
  (cd "$WORK/publish"; sha256sum "$name" > SHA256SUMS; sha256sum -c SHA256SUMS >/dev/null)
}
wait_crl(){
  local state n
  for ((n=0; n<120; n++)); do
    state=$(systemctl show --property=ActiveState --value radio-renew-crl.service) || return 1
    case "$state" in
      inactive|failed) return 0 ;;
      active|activating|reloading|deactivating) sleep 1 ;;
      *) return 1 ;;
    esac
  done
  return 1
}
resume(){
  local failed=0
  if $UI; then systemctl start openvpn-ui.service || failed=1; UI=false; fi
  if $TIMER; then systemctl start radio-renew-crl.timer || failed=1; TIMER=false; fi
  return "$failed"
}
cleanup(){
  local result=$?
  trap - EXIT
  resume || { log 'ERREUR : reprise UI/CRL a verifier.' >&2; result=1; }
  [[ -z "$WORK" ]] || rm -rf -- "$WORK"
  (( result == 0 )) || log 'Preparation ou nettoyage en echec ; verifier la derniere archive complete publiee.' >&2
  exit "$result"
}
main(){
  [[ $EUID -eq 0 ]] || die 'Executer en root.'
  [[ $# == 0 ]] || die 'Usage : sudo radio-vpn-backup'
  [[ $(stat -c %u /etc/radio-vpn-backup.conf) == 0 ]] || die 'Configuration non detenue par root.'
  [[ -z $(find /etc/radio-vpn-backup.conf -perm /022 -print) ]] || die 'Configuration modifiable par un autre compte.'
  # Fichier local d'administration, installe root:root 0600 ; jamais fourni par le NAS.
  source /etc/radio-vpn-backup.conf
  [[ "$KEEP_VPS" =~ ^[0-9]+$ ]] && (( KEEP_VPS >= 2 && KEEP_VPS <= 30 )) || die 'KEEP_VPS attendu entre 2 et 30.'
  ENCRYPT=${ENCRYPT:-false}
  [[ "$ENCRYPT" == true || "$ENCRYPT" == false ]] || die 'ENCRYPT doit valoir true ou false.'
  if $ENCRYPT; then
    command -v age >/dev/null || die 'Installer age pour activer le chiffrement.'
    RECIPIENTS=${RECIPIENTS:-/etc/radio-vpn-backup.recipients}
    [[ -s "$RECIPIENTS" ]] || die 'Cle publique age absente.'
  fi
  install -d -m 700 "$STATE"
  exec 9>"$STATE/backup.lock"
  flock -n 9 || die 'Une sauvegarde est deja en cours.'
  trap cleanup EXIT
  trap 'exit 1' HUP INT TERM
  WORK=$(mktemp -d "$STATE/.work.XXXXXXXX")
  log 'Debut de sauvegarde ; OpenVPN reste actif.'
  python3 "$BASE/snapshot.py" preflight /
  local state
  state=$(systemctl show --property=ActiveState --value radio-renew-crl.timer)
  case "$state" in active|activating|reloading) TIMER=true ;; inactive|failed) : ;; *) die 'Etat du timer CRL inattendu.' ;; esac
  systemctl stop radio-renew-crl.timer
  # Arreter le timer ne tue pas un renouvellement deja lance.
  wait_crl || die 'Renouvellement CRL encore actif ou etat inaccessible.'
  # Refuser une operation Easy-RSA deja engagee ; aucune operation manuelle pendant cette fenetre.
  ! pgrep -f '[/]easyrsa( |$)|[/]opt/scripts/(genclient|revoke|renew|rmcert|generate_ca)' >/dev/null || die 'Operation PKI en cours ; reessayer plus tard.'
  state=$(systemctl show --property=ActiveState --value openvpn-ui.service)
  case "$state" in active|activating|reloading) UI=true ;; inactive|failed) : ;; *) die 'Etat UI inattendu.' ;; esac
  # Stop inconditionnel : annule aussi un demarrage/redemarrage en attente.
  systemctl stop openvpn-ui.service
  python3 "$BASE/snapshot.py" create / "$WORK/snapshot"
  resume || die 'Impossible de relancer UI/CRL.'
  log 'Copie terminee ; administration disponible. Verification de l archive.'
  python3 "$BASE/snapshot.py" pack "$WORK/snapshot" "$WORK/backup.tar.gz"
  gzip -t "$WORK/backup.tar.gz"
  python3 "$BASE/snapshot.py" check "$WORK/backup.tar.gz"
  local id
  id="$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
  prepare_publication
  chown -R root:radio-vpn-backup "$WORK/publish"
  chmod 750 "$WORK/publish"
  chmod 640 "$WORK/publish/"*
  # Meme systeme de fichiers : la publication du repertoire est atomique.
  [[ $(stat -c %d "$STATE") == $(stat -c %d "$EXPORT") ]] || die 'STATE et EXPORT doivent etre sur le meme systeme de fichiers.'
  mv -T -- "$WORK/publish" "$EXPORT/$id"
  python3 "$BASE/snapshot.py" prune "$EXPORT" "$KEEP_VPS"
  log "Sauvegarde publiee : $id (ENCRYPT=$ENCRYPT)."
}
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
