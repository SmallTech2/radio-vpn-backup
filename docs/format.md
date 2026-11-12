# Format des sauvegardes et compatibilité

[Accueil sauvegarde](../README.md) · [Installer sur le VPS](vps-installation.md) · [Collecte ABB](abb.md) · [Collecteur personnalisé](installation.md)

Référence des fichiers produits par radio-vpn-backup. Commencer par
[l’installation sur le VPS](vps-installation.md), puis configurer la collecte
[ABB](abb.md#5-configurer-abb) ou le [collecteur personnalisé](installation.md).

## Compatibilité

La sauvegarde vise un serveur Debian 13 AMD64 préparé avec radio-vpn. Elle vérifie les
composants aux chemins ci-dessous, pas une égalité de version. Les versions et commits
d’origine restent dans `/etc/radio-vpn-deployed` et dans le manifeste.

**Indispensables :** arborescences Easy-RSA, OpenVPN, runtime UI et scripts ; CA et clés,
certificat serveur, `index.txt`, `serial`, `vars`, CRL, DH et clé tls-crypt ; configuration
serveur, modèle client et répertoire CCD ; binaire UI exécutable, ressources, configuration
et SQLite ; environnement UI, métadonnées, unité UI et composants de renouvellement CRL.

**Facultatifs :** références SSH et helper, nftables, désactivation IPv6 et configurations
de logs. Ils sont copiés s’ils existent. Le compteur PKI `crlnumber` est également facultatif :
la sauvegarde le conserve s’il existe et ne le crée pas sinon. `crl.pem` et `index.txt`
restent obligatoires. Ne pas fabriquer de fichier pour contourner un contrôle.

Le script de restauration contrôle le format, les fichiers, SQLite, la PKI et les
configurations sur une destination déjà préparée avec radio-vpn et le même réseau VPN.
Un serveur préparé autrement, une archive d’un autre outil ou un schéma personnalisé
n’est pas garanti compatible ; cela ne signifie pas qu’une adaptation soit impossible.

## Fichiers inclus et rôle à la restauration

| Chemin | Contenu et traitement |
| --- | --- |
| `/usr/share/easy-rsa/` | Outils et PKI complète, clés, certificats, requêtes et historiques, index, compteurs présents, vars, CRL, DH, `ta.key` |
| `/etc/openvpn/` | Configuration serveur et client, profils, secrets éventuels et CCD ; lien `pki` vers `/usr/share/easy-rsa/pki` |
| `/opt/openvpn-ui-runtime/` | Binaire, configuration, `db/data.db` et ressources UI ; journaux applicatifs exclus |
| `/opt/scripts/` | Scripts de l’interface ; lien `qrencode` vers `/usr/bin/qrencode` |
| `/etc/openvpn-ui.env` | Environnement initial UI, accès confidentiel |
| `/etc/radio-vpn-deployed` | Version, commits, IP publique et réseau du serveur sauvegardé |
| `/etc/systemd/system/openvpn-ui.service` | Unité de l’interface |
| `/etc/systemd/system/radio-renew-crl.service` et `.timer` | Service et planification CRL |
| `/usr/local/sbin/radio-renew-crl` | Renouvellement de la CRL, sans recréer les certificats |
| `/etc/logrotate.d/openvpn` | Facultatif ; restauré si présent, sinon celui de destination est conservé |
| `/etc/systemd/journald.conf.d/99-radio-limits.conf` | Même traitement pour les limites journald |
| `/etc/nftables.conf` | Référence archivée, non appliquée à la destination |
| `/etc/sysctl.d/99-radio-disable-ipv6.conf` | Référence archivée, réglages de destination conservés |
| `/etc/ssh/sshd_config`, `/etc/ssh/sshd_config.d/00-radio.conf` | Références archivées, non appliquées à la destination |
| `/usr/local/bin/radio-secure-ssh` | Référence archivée, helper de destination conservé |

Les propriétaires numériques et les modes sont enregistrés. Le dépôt et ses Releases
ne contiennent pas les données d’exploitation. La sauvegarde n’est pas une image du
système : elle n’inclut ni les mots de passe Linux, ni `/etc/passwd` ou `/etc/shadow`,
ni les clés SSH privées ou clés d’hôte. Le compte de collecte NAS et son cron ne sont
pas réinstallés par radio-vpn-restore.

## Conteneur d’archive

Le tar gzip contient :

```text
manifest.json
INVENTORY.txt
payload/etc/...
payload/opt/...
payload/usr/...
```

Le manifeste indique `format: 1`, la date UTC, `deployment`, les versions de paquets,
les comptes sudo candidats et `files`, indexé par chemin relatif. Chaque entrée contient
le type, le mode, UID/GID et le SHA-256 du fichier, ou la cible d’un lien. Le champ
`missing_optional` liste les fichiers système facultatifs absents.

La préparation utilise la copie SQLite, contrôle son intégrité et vérifie les éléments
PKI/CRL/CCD requis. La lecture contrôle les empreintes, les chemins autorisés, les liens
et les permissions ; les chemins traversants, doublons tar et fichiers spéciaux sont refusés.
Les données temporaires sont dans des dossiers root privés. Aucun accès à la PKI d’origine
n’est donné au compte de collecte.

## Publication et noms des fichiers

Sur le VPS, chaque dossier `/var/lib/radio-vpn-export/AAAAMMJJTHHMMSSZ-xxxxxxxx/` contient :

- `backup.tar.gz`, ou `backup.tar.gz.age` pour le mode chiffré ;
- `SHA256SUMS`, avec l’empreinte du fichier publié.

La date du nom est en UTC ; l’horaire du cron est, lui, en heure locale du VPS.
Le dossier est publié par renommage après les contrôles, puis la rétention locale est
appliquée. Le chiffrement age enveloppe le même tar gzip ; il ne change pas son format interne.

## Collecte ABB

Le module `archives` conserve ces noms et dossiers dans les points ABB. La commande
forcée accepte `rsync --server --daemon .` et impose `/etc/radio-vpn-backup-rsyncd.conf`.
Le processus ne dure que pendant la connexion SSH : aucun service rsync permanent ni
port 873. Le module est en lecture seule ; les suppressions des sources et options de
déréférencement sont refusées. Voir la [procédure ABB](abb.md).

## Collecteur personnalisé

Le protocole SSH `list/hash/get` ne donne accès qu’aux identifiants d’archives exportées.
Le collecteur renomme le fichier en `AAAAMMJJTHHMMSSZ-xxxxxxxx.tar.gz` ou `.tar.gz.age`,
et écrit un fichier de même nom suivi de `.sha256`. Il contrôle le transfert avant
publication locale et applique sa rétention aux deux formats. Les requêtes shell rsync
sans `-s` restent déléguées à `rrsync` en lecture seule ; aucune commande shell libre
n’est autorisée. Ce mécanisme est indépendant de la planification et de la rétention ABB.
