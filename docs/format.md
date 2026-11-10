# Analyse de radio-vpn et format v1

Reference examinee : radio-v2.4, commit `298667782ea9be0e024ad9b634232e6ce2c8db39`.
L'installateur `Radio/deploy-vps.sh` refuse un runtime, une configuration OpenVPN, une
PKI ou `/etc/radio-vpn-deployed` existants. `generate_ca_and_server_certs.sh init-pki`
refuse une CA existante. La restauration ne doit appeler ni cet installateur sur les
donnees restaurees, ni `-initialize-only`, ni une commande de generation de CA.
Aucune adaptation du depot radio-vpn n'est appliquee par ces deux outils.

## Liste des elements

| Chemin | Role / restauration |
| --- | --- |
| `/usr/share/easy-rsa/` | Outils et PKI complete : `private/`, `issued/`, `reqs/`, `revoked/`, `renewed/`, index et anciennes copies, serial, crlnumber, vars, CRL, DH, `ta.key` |
| `/etc/openvpn/` | Serveur, modele client, profils, secrets MFA, CCD ; lien `pki` vers `/usr/share/easy-rsa/pki` |
| `/opt/openvpn-ui-runtime/` | Binaire, `conf`, SQLite `db/data.db`, ressources UI, licence ; exclut `logs/` |
| `/opt/scripts/` | Scripts applicatifs ; lien `qrencode` vers `/usr/bin/qrencode` |
| `/etc/openvpn-ui.env` | Secret initial UI ; restaure, permissions conservees |
| `/etc/radio-vpn-deployed` | Release, commits, ancienne IP publique et CIDR |
| `/etc/systemd/system/openvpn-ui.service` | Runtime root, port 8080, dependance nftables |
| `/etc/systemd/system/radio-renew-crl.service` et `.timer` | Service oneshot et timer hebdomadaire persistant |
| `/usr/local/sbin/radio-renew-crl` | Renouvellement CRL ; aucun renouvellement des certificats |
| `/etc/logrotate.d/openvpn` | Rotation OpenVPN, sans fichier d'etat |
| `/etc/systemd/journald.conf.d/99-radio-limits.conf` | Limites journald |
| `/etc/nftables.conf` | Reference archivee, non injectee : conserver le pare-feu du nouveau VPS prepare |
| `/etc/sysctl.d/99-radio-disable-ipv6.conf` | Reference archivee, configuration du nouveau VPS conservee |
| `/etc/ssh/sshd_config`, `/etc/ssh/sshd_config.d/00-radio.conf` | References archivees, jamais appliquees automatiquement au nouveau VPS |
| `/usr/local/bin/radio-secure-ssh` | Reference archivee ; helper du nouveau VPS conserve |

Les proprietaires sont numeriques. La reference utilise root pour l'UI/PKI et nobody
pour OpenVPN apres ouverture des cles ; les comptes Linux administrateurs ne possedent
pas ces donnees. Les mots de passe Linux, `/etc/passwd`, `/etc/shadow`, cles SSH privees
et cles d'hote ne sont pas copies. Les profils clients contiennent leurs cles privees :
la sauvegarde non chiffree doit rester dans un dossier prive sur le NAS. Ce choix est volontaire et le risque est accepte.

Services : `openvpn@server.service`, `openvpn-ui.service`, `ssh.service`, `nftables.service`,
`radio-renew-crl.service`, `radio-renew-crl.timer`, `logrotate.timer`, `systemd-journald.service`.
Le service Debian OpenVPN et logrotate sont fournis par les paquets du nouveau VPS.
Le reseau VPN de la sauvegarde doit etre conserve ; le compte Linux et l'IPv4 publique peuvent changer.

## Conteneur d'archive

Une archive `backup.tar.gz` directement exploitable contient (mode standard) :

```text
manifest.json
INVENTORY.txt
payload/etc/...
payload/opt/...
payload/usr/...
```

`manifest.json` : `format: 1`, date UTC, metadonnees de deploiement, versions des paquets,
comptes sudo candidats et `files` indexe par chemin relatif. Chaque entree indique
type, mode, UID/GID, SHA-256 pour un fichier, ou cible pour un lien. Le lecteur refuse
doublons, chemins absolus/traversants, fichiers speciaux, modes setuid/setgid/sticky,
liens hors contrat et fichiers non declares. Aucun ecrit au travers d'un lien n'est autorise.
Les deux lecteurs sont autonomes ; toute evolution du format doit rester testee dans les deux depots.

Publication VPS : un repertoire date `AAAAMMJJTHHMMSSZ-xxxxxxxx` contient l'archive
standard `backup.tar.gz` ou facultativement `backup.tar.gz.age`, et `SHA256SUMS`. Le repertoire est renomme atomiquement apres tous les controles.
Le protocole SSH ne publie que ces noms strictement formes.

En mode `ENCRYPT=true`, le meme tar.gz est chiffre par age au format natif initial.
Le format interne v1 ne change pas. Le protocole SSH `hash IDENTIFIANT` retourne
`SHA256  backup.tar.gz` ou `SHA256  backup.tar.gz.age`, sans chemin arbitraire.
Le NAS conserve l'extension du fichier et applique la meme retention aux deux formats.
