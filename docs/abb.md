# Sauvegarder avec Synology Active Backup for Business

[Accueil sauvegarde](../README.md) · [Installer sur le VPS](vps-installation.md) · [Collecteur personnalisé](installation.md)

Le **VPS** prépare une archive ; **ABB sur le NAS** la récupère en PULL par SSH.
Les deux tâches sont distinctes : cron produit les données, ABB planifie la collecte,
le stockage et la rétention. Le VPS ne contacte pas le NAS.

Commencer par l’[installation du programme sur le VPS](vps-installation.md),
y compris après une restauration, puis poursuivre à la [configuration ABB](#5-configurer-abb).
Le présent guide fournit aussi la préparation de la clé nécessaire à cette installation.
Pour un NAS sans ABB, utiliser le [collecteur personnalisé](installation.md).

**Dans cette page**

- [1. Prérequis et comptes](#1-prérequis-et-comptes)
- [2. Préparer la clé SSH de collecte](#2-préparer-la-clé-ssh-de-collecte)
- [3. Installer sur le VPS](#3-installer-sur-le-vps)
- [4. Produire une archive](#4-produire-une-archive)
- [5. Configurer ABB](#5-configurer-abb)
- [6. Contrôler la collecte et récupérer les fichiers](#6-contrôler-la-collecte-et-récupérer-les-fichiers)

## 1. Prérequis et comptes

- **VPS** : Debian 13 AMD64 installé avec [radio-vpn](https://github.com/SmallTech2/radio-vpn/blob/main/docs/installation.md), compte Linux administrateur avec sudo et SSH par clé, accès HTTPS à Debian/GitHub et espace pour les copies et archives.
- **NAS** : DSM, stockage et paquet ABB pris en charge par Synology, accès au port SSH public du VPS.
- **Poste d’administration** : accès au VPS, navigateur DSM et clé de collecte à importer dans ABB.

Le compte **Linux VPS** `radio-vpn-backup` sera créé par l’installateur. Il n’a ni sudo
ni shell libre. ABB utilise son unique module `archives`, en lecture seule, limité à
`/var/lib/radio-vpn-export`. La PKI d’origine n’est pas exposée par cet accès.

Dans DSM, installer et ouvrir ABB avec un compte autorisé à gérer les tâches. ABB gère
sa destination ; un compte DSM nommé `vpn-backup` ou un partage `VPN-Backup` n’est pas
requis par le script et n’est pas automatiquement utilisé par ABB. Ces noms, comme les
noms de tâches ci-dessous, sont des exemples. Aucun second compte SSH VPS n’est nécessaire.

## 2. Préparer la clé SSH de collecte

La clé **privée** est importée dans ABB ; la clé **publique** est copiée au VPS. Elles
sont différentes de la paire de clés age. Une clé de collecte existante peut être
réutilisée si elle est dédiée à cet usage et si son fichier privé est disponible.
Ne jamais écraser une clé existante ni afficher son contenu privé.

**Poste Windows — PowerShell, compte habituel :**

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
$AbbKey = Join-Path $env:USERPROFILE '.ssh\radio-vpn-abb-vps1'
ssh-keygen -t ed25519 -f $AbbKey -C 'abb-vps1'
ssh-keygen -lf ($AbbKey + '.pub')
Get-Content -LiteralPath ($AbbKey + '.pub')
Write-Output "Fichier prive a importer dans ABB : $AbbKey"
```

L’exemple crée les fichiers dans votre vrai dossier personnel. Répondre Entrée aux
questions de phrase secrète pour cette clé automatisée ; protéger son fichier privé.
Conserver l’empreinte publique et copier seulement la ligne `ssh-ed25519 ...`.

**Alternative poste Linux/macOS — Bash :**

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/radio-vpn-abb-vps1" -C 'abb-vps1'
ssh-keygen -lf "$HOME/.ssh/radio-vpn-abb-vps1.pub"
cat "$HOME/.ssh/radio-vpn-abb-vps1.pub"
```

Le fichier sans `.pub` est celui à importer dans ABB depuis le poste de confiance.

## 3. Installer sur le VPS

Suivre la [procédure commune d’installation VPS](vps-installation.md#3-préparer-git-et-le-fichier-de-clé-publique-sur-le-vps)
avec la clé publique préparée à l’étape 2. Elle explique Git, le clonage, l’appel à
`install.sh`, le compte créé, la configuration et le choix de l’horaire cron.
Si le programme est déjà installé, utiliser la [maintenance](maintenance.md#installation-vps-déjà-présente-ou-partielle).

## 4. Produire une archive

Effectuer la [première sauvegarde et ses contrôles](vps-installation.md#5-produire-une-première-sauvegarde)
sur le VPS avant de créer la tâche ABB. Le mode standard produit `backup.tar.gz` et
`SHA256SUMS` ; le [guide age](encryption.md) décrit le chiffrement facultatif.

## 5. Configurer ABB

**VPS — administrateur, session reconnue comme fiable :**

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
sudo cat /etc/cron.d/radio-vpn-backup
timedatectl
```

Noter cette empreinte d’hôte, le port SSH réellement utilisé et l’IPv4 publique fournie
par l’hébergeur. La clé d’hôte n’est pas la clé de collecte.

**NAS — navigateur DSM, opérateur ABB :** dans **Serveur de fichiers**, ajouter un
serveur rsync. Les libellés DSM peuvent varier ; renseigner :

| Champ | Valeur |
| --- | --- |
| Adresse | IPv4 publique réelle du VPS |
| Mode | **rsync module via SSH** |
| Port | **22**, ou le port SSH réel si personnalisé |
| Compte | **radio-vpn-backup** |
| Authentification | Clé SSH : importer le fichier privé de l’étape 2 |
| Élévation / sudo | Aucune |
| Source | Module **archives**, avec tous ses dossiers datés |

Vérifier l’empreinte présentée avec celle relevée sur le VPS. Le module correspond à
l’export, pas à la racine du serveur. Ne pas saisir `/var/lib/radio-vpn-export` comme
sous-chemin du module. Aucun mot de passe rsync distinct n’est configuré.
Le mode ne demande ni agent Linux ni service rsync permanent ni ouverture du port 873.

Créer une tâche, choisir son stockage ABB et le mode **multi-versionné** pour conserver
plusieurs points. Programmer la collecte après l’heure du cron, avec une marge suffisante.
Vérifier le fuseau du VPS et celui de DSM. Définir la rétention ABB selon votre besoin,
par exemple 7 points quotidiens et 4 hebdomadaires ; ces valeurs ne sont pas imposées
par le projet. Les paramètres `DAILY`/`WEEKLY` du collecteur personnalisé n’agissent pas sur ABB.

## 6. Contrôler la collecte et récupérer les fichiers

**NAS — opérateur ABB :** lancer la tâche, consulter son résultat et ouvrir le point
collecté dans le navigateur de restauration/ABB Portal. Le dossier daté doit contenir
l’archive et `SHA256SUMS`. Contrôler également les prochaines exécutions planifiées et
la présence de points anciens après purge locale du VPS.

Pour récupérer une sauvegarde, télécharger le point choisi ou son dossier daté vers
le poste d’administration. S’il est fourni en ZIP, l’extraire avant d’utiliser les fichiers.
Ne pas demander une restauration vers le serveur source : le compte est en lecture seule.
Ne pas manipuler directement les fichiers internes du stockage ABB.

Pour reconstruire, suivre la [procédure radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md),
qui décrit le transfert, le fichier SHA-256, `--check` et la restauration.
Les archives contiennent les clés privées : limiter leur accès au NAS et au poste.

Les opérations courantes et les erreurs de connexion sont traitées dans la
[maintenance](maintenance.md). Les descriptions du [module rsync](format.md#collecte-abb)
et du [format d’archive](format.md#conteneur-darchive) sont séparées du parcours d’installation.
