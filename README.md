# radio-vpn-backup

🌐 **Translate to English** — Pour consulter cette page en anglais, utilisez la fonction
de traduction intégrée de votre navigateur. Copiez les commandes depuis l’original français.

Prépare des sauvegardes confidentielles d’un serveur **Debian 13 AMD64 installé avec
radio-vpn** : PKI, certificats, révocations, IP fixes, profils et données OpenVPN UI.
Le VPS prépare l’archive ; le NAS Synology la récupère par SSH, en PULL. Le VPS ne se
connecte jamais au NAS. OpenVPN reste actif pendant la copie ; l’UI est brièvement suspendue.

Solution validée le 12 novembre 2026 sur Debian 13.7.

## Écosystème Radio VPN

- [radio-vpn](https://github.com/SmallTech2/radio-vpn) : socle serveur ; [installation](https://github.com/SmallTech2/radio-vpn/blob/main/docs/installation.md).
- **radio-vpn-backup** : préparation et collecte ; [guide ABB](docs/abb.md).
- [radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore) : réinjection sur un serveur reconstruit avec radio-vpn ; [procédure](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md).

La chaîne complète et ses dépendances sont décrites dans la
[présentation générale](https://github.com/SmallTech2/radio-vpn/blob/main/docs/ecosystem.md).
Une installation OpenVPN d’un autre outil n’est pas garantie compatible. Ce périmètre
ne signifie pas qu’une adaptation soit techniquement impossible.

## Installer et collecter

**Commencer par installer radio-vpn-backup sur le VPS**, y compris après une restauration
avec radio-vpn-restore. Configurer ensuite **une seule** des deux méthodes de collecte NAS :

1. **Installation sur le VPS** : [procédure commune](docs/vps-installation.md), avec préparation de la clé publique, clonage, installation et première sauvegarde.
2. **Collecte avec Synology ABB — méthode principale** : [configurer ABB en mode module rsync via SSH](docs/abb.md#5-configurer-abb).
3. **Collecte sans ABB — alternative** : [guide du collecteur Synology personnalisé](docs/installation.md).

La préparation de la clé SSH de collecte est un prérequis de l’installation VPS ; le
guide commun indique où la préparer selon la méthode choisie. La collecte NAS et la
préparation des archives sur le VPS sont deux opérations distinctes.

Le compte VPS `radio-vpn-backup` est créé par l’installateur, sans sudo ni shell libre.
Le module ABB `archives` expose seulement `/var/lib/radio-vpn-export` en lecture seule.
Aucun port 873 ni service rsync permanent n’est nécessaire. ABB gère son stockage et
sa rétention ; les comptes et dossiers DSM du collecteur personnalisé ne sont pas requis.

L’installation demande l’heure quotidienne au format `HH:MM`, **02:17 par défaut en
heure locale du VPS**, et l’écrit dans `/etc/cron.d/radio-vpn-backup`.

## Sauvegarde manuelle et chiffrement

Sur le **VPS, compte administrateur avec sudo** :

```bash
sudo /usr/local/sbin/radio-vpn-backup
```

Dans un terminal, répondre Entrée à la proposition de chiffrement pour produire une
`.tar.gz`. Répondre `o` pour age ; les destinataires publics configurés sont réutilisés,
ou leur fichier est demandé. Le choix ne modifie pas la configuration du cron.
Sans terminal, cron utilise `ENCRYPT=false` par défaut, ou `ENCRYPT=true` et `RECIPIENTS`
pour chiffrer sans interaction. Age n’est requis que pour une exécution chiffrée.

**L’archive non chiffrée contient la clé privée de la CA et les clés clients.** Ce choix
est volontaire ; stocker ces données dans un emplacement protégé. Pour age, conserver
la clé privée de déchiffrement hors du VPS, indépendamment de la clé SSH de collecte.

## Guides

[Installation VPS](docs/vps-installation.md) · [Collecte ABB](docs/abb.md) ·
[Collecteur personnalisé](docs/installation.md) ·
[Chiffrement age](docs/encryption.md) · [Maintenance](docs/maintenance.md) ·
[Format et fichiers sauvegardés](docs/format.md).

La compatibilité dépend des composants présents, pas du seul numéro de version. Les
versions et commits d’origine restent dans l’archive. Ne pas administrer la PKI pendant
la préparation ; une archive ne contient pas les opérations effectuées après sa création.

## Licence

[MIT](LICENSE). Outil compagnon de Radio Bonheur pour radio-vpn, dérivé de
[d3vilh/openvpn-ui](https://github.com/d3vilh/openvpn-ui), avec les attributions conservées.
