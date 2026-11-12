# Radio VPN Backup

[Installation](#installation) · [Guides utilisateur](#guides-utilisateur) · [Écosystème Radio VPN](#écosystème-radio-vpn)

## Présentation

radio-vpn-backup prépare les sauvegardes d’un serveur **Debian 13 AMD64 installé avec
radio-vpn** : PKI, certificats, révocations, IP fixes, profils et données OpenVPN UI.
Le VPS prépare une archive par cron ; le NAS la récupère en PULL par SSH avec ABB
ou le collecteur personnalisé. OpenVPN reste actif ; l’UI est brièvement suspendue.

La compatibilité dépend des composants présents, pas du seul numéro de version.
Les versions et commits d’origine restent dans l’archive. Une installation OpenVPN
provenant d’un autre outil n’est pas garantie compatible ; voir le [périmètre](docs/format.md#compatibilité).

Solution validée le 12 novembre 2026 sur Debian 13.7.

## Installation

**[Ouvrir la procédure d’installation de radio-vpn-backup sur le VPS](docs/vps-installation.md).**

Commencer par cette procédure, y compris après une restauration avec radio-vpn-restore.
Elle explique la préparation de la clé publique de collecte, Git, le clonage, l’installation,
le choix de l’heure du cron et la première sauvegarde contrôlée. Elle indique sur quelle
machine préparer la clé selon la méthode de collecte choisie.

Configurer ensuite **une seule** des deux méthodes de collecte présentées ci-dessous.
Ne pas relancer l’installateur sur une installation existante ; suivre la [maintenance](docs/maintenance.md#installation-vps-déjà-présente-ou-partielle).

## Guides utilisateur

- [Synology ABB — méthode principale](docs/abb.md) : préparation de la clé, configuration du module rsync via SSH, planification et rétention ABB.
- [Collecteur Synology personnalisé — alternative sans ABB](docs/installation.md) : compte NAS, clé SSH, `nas-pull.sh` et tâche planifiée DSM.
- [Sauvegarde manuelle et contrôles](docs/vps-installation.md#5-produire-une-première-sauvegarde) : première archive et vérification SHA-256.
- [Chiffrement facultatif avec age](docs/encryption.md) : mode manuel ou automatique ; le mode standard reste sans chiffrement.

## Sauvegarde et restauration

- [Préparer les archives sur le VPS](docs/vps-installation.md#5-produire-une-première-sauvegarde), puis les [collecter avec ABB](docs/abb.md#5-configurer-abb) ou le [collecteur personnalisé](docs/installation.md).
- Récupérer une archive depuis [ABB](docs/abb.md#6-contrôler-la-collecte-et-récupérer-les-fichiers) ou [File Station avec le collecteur](docs/installation.md#récupérer-manuellement-une-archive).
- [Reconstruire et restaurer avec radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md).

Après restauration, réinstaller radio-vpn-backup sur le VPS et vérifier la collecte NAS :
le programme, le compte de collecte et le cron ne sont pas recréés par la restauration.

## Sécurité et maintenance

**Les archives non chiffrées contiennent la clé privée de la CA et les clés clients.**
Les conserver dans un emplacement protégé. Ne pas administrer la PKI pendant la copie.

- [Chiffrement et conservation des clés age](docs/encryption.md) : la clé privée reste hors du VPS source.
- [Contrôles et dépannage](docs/maintenance.md) : cron, SSH, collecte DSM, intégrité et rétention.
- [Changer l’heure du cron](docs/maintenance.md#changer-lheure-dune-installation-existante).
- [Mettre à jour les fichiers installés](docs/maintenance.md#mettre-à-jour-les-fichiers-installés).

## Références techniques

- [Format, fichiers inclus, permissions et compatibilité](docs/format.md).
- [Installateur VPS](install.sh), [préparation des archives](scripts/backup.sh) et [contrôles des données](scripts/snapshot.py).
- [Accès SSH restreint](scripts/export.sh) et [module rsync en lecture seule](config/rsyncd.conf).
- [Collecteur NAS](nas-pull.sh), [configuration](nas.conf.example) et [rétention](scripts/retention.py).
- [Suivi technique](docs/validation.md).

### Licence et crédits

[MIT](LICENSE). Outil compagnon de Radio Bonheur pour radio-vpn, dérivé de
[d3vilh/openvpn-ui](https://github.com/d3vilh/openvpn-ui), avec les attributions conservées.

## Écosystème Radio VPN

- [radio-vpn](https://github.com/SmallTech2/radio-vpn) : [installer un serveur VPN](https://github.com/SmallTech2/radio-vpn/blob/main/docs/installation.md).
- [radio-vpn-backup](https://github.com/SmallTech2/radio-vpn-backup) : [sauvegarder ce serveur](docs/vps-installation.md).
- [radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore) : [reconstruire et restaurer](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md).

La [présentation de l’écosystème](https://github.com/SmallTech2/radio-vpn/blob/main/docs/ecosystem.md)
explique les rôles et dépendances des trois projets.
