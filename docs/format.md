# Analyse de radio-vpn et format v1

Cette page est une référence technique. Pour une première utilisation, suivre le
[guide d'installation](installation.md). Le [chiffrement facultatif](encryption.md)
est décrit séparément ; il ne change pas le contenu interne de l'archive.

L'installateur `Radio/deploy-vps.sh` refuse un runtime, une configuration OpenVPN, une
PKI ou `/etc/radio-vpn-deployed` existants. `generate_ca_and_server_certs.sh init-pki`
refuse une CA existante. La restauration ne doit appeler ni cet installateur sur les
donnees restaurees, ni `-initialize-only`, ni une commande de generation de CA.
Aucune adaptation du depot radio-vpn n'est appliquee par ces deux outils.

## Compatibilité

La sauvegarde ne filtre pas les installations par numéro de version. Elle contrôle les
composants aux chemins ci-dessous. Une installation radio-v2.1 peut être sauvegardée
sans mettre à jour le VPN ni modifier son fichier de déploiement.

**Indispensables :** les quatre arborescences Easy-RSA, OpenVPN, runtime UI et scripts ;
la configuration serveur et le modèle client ; le dossier CCD ; la PKI avec CA et clés,
certificat serveur, index, compteur de série, vars, CRL, DH et clé tls-crypt ;
le binaire UI exécutable, sa configuration, sa base SQLite et ses ressources ; le fichier
d’environnement UI, les métadonnées de déploiement, l’unité UI et les deux unités ainsi
que le script de renouvellement CRL. Ces derniers sont nécessaires au mécanisme existant
de suspension du renouvellement pendant la copie.

**Facultatifs :** les fichiers de référence nftables, SSH et son helper, la désactivation
IPv6, logrotate et les limites journald. Ils sont copiés seulement s’ils existent ; leur
absence n’empêche pas la sauvegarde. Ne pas les créer artificiellement pour passer un contrôle.
Un élément facultatif présent sous un type incorrect est refusé.

Le compteur PKI `crlnumber` n'est pas indispensable : Easy-RSA peut générer une CRL
sans ce fichier. S'il existe, il est conservé avec toute l'arborescence PKI ; s'il est
absent, la sauvegarde ne le crée pas. `crl.pem` et `index.txt` restent obligatoires,
avec vérification de la signature de la CRL et des séries révoquées de l'index.

La copie SQLite est contrôlée, ainsi que les correspondances clés/certificats, les
révocations et les IP fixes. Le réseau déclaré dans les métadonnées doit correspondre à
la directive serveur OpenVPN. Une incohérence bloque la publication de l’archive.
Le contenu original de /etc/radio-vpn-deployed est conservé, avec la version et les commits
d’origine ; aucune valeur n’est remplacée par la version courante.

**La compatibilité de restauration est distincte.** Le projet radio-vpn-restore reste
inchangé et impose actuellement radio-v2.4 et sa liste complète de fichiers. La production
et la vérification d’une archive radio-v2.1 ne signifient donc pas que cet outil accepte
déjà sa restauration. Vérifier ce point avant toute bascule ou suppression du serveur source.

## Liste des elements

| Chemin | Role / restauration |
| --- | --- |
| `/usr/share/easy-rsa/` | Outils et PKI complete : `private/`, `issued/`, `reqs/`, `revoked/`, `renewed/`, index et anciennes copies, serial, crlnumber s'il existe, vars, CRL, DH, `ta.key` |
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
comptes sudo candidats et `files` indexe par chemin relatif.
Le champ `missing_optional` liste les fichiers facultatifs absents ; ils ne figurent
pas dans l’inventaire des fichiers copiés. La version source figure dans `deployment.release_tag`. Chaque entree indique
type, mode, UID/GID, SHA-256 pour un fichier, ou cible pour un lien. Le lecteur refuse
doublons, chemins absolus/traversants, fichiers speciaux, modes setuid/setgid/sticky,
liens hors contrat et fichiers non declares. Aucun ecrit au travers d'un lien n'est autorise.
Les deux lecteurs sont autonomes ; toute evolution du format doit rester testee dans les deux depots.

Publication VPS : un repertoire date `AAAAMMJJTHHMMSSZ-xxxxxxxx` contient l'archive
standard `backup.tar.gz` ou facultativement `backup.tar.gz.age`, et `SHA256SUMS`. Le repertoire est renomme atomiquement apres tous les controles.
Le protocole SSH ne publie que ces noms strictement formes.

En mode `ENCRYPT=true`, le meme tar.gz est chiffre au format natif age.
Le format interne est le même dans les deux modes. Le protocole SSH `hash IDENTIFIANT` retourne
`SHA256  backup.tar.gz` ou `SHA256  backup.tar.gz.age`, sans chemin arbitraire.
Le NAS conserve l'extension du fichier et applique la meme retention aux deux formats.

## Collecte ABB

Le chemin physique reste `/var/lib/radio-vpn-export`. En mode **module via SSH**,
`export.sh` accepte exactement `rsync --server --daemon .` (aussi avec `/usr/bin/rsync`)
et impose `/etc/radio-vpn-backup-rsyncd.conf` : seul le module `archives`, en lecture seule,
est exposé. Aucun service rsync permanent, port 873 ou privilège sudo n'est nécessaire.
Les options de suppression des sources et de déréférencement sont refusées.

Les demandes shell classiques restent déléguées à `rrsync -ro -no-del`, avec l'export
comme racine virtuelle et sans accepter `-s`. `rsync --version` et le protocole personnalisé
`list/hash/get` restent disponibles ; les commandes libres restent refusées.

ABB conserve les noms `backup.tar.gz` (ou `.age`) et `SHA256SUMS` dans les dossiers datés ;
le collecteur personnalisé les renomme avec l'identifiant daté et un fichier `.sha256`.
Le contenu du tar et le format v1 ne changent pas. Voir le [guide ABB](abb.md) pour les
limites de compatibilité, la rétention ABB et la récupération d'une archive pour restauration.
