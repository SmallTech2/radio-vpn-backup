# Sauvegarder avec Synology Active Backup for Business

Le **VPS** prépare une archive ; **ABB sur le NAS** la récupère en PULL par SSH.
Les deux tâches sont distinctes : cron produit les données, ABB planifie la collecte,
le stockage et la rétention. Le VPS ne contacte pas le NAS.

Pour un NAS sans ABB, utiliser le [collecteur personnalisé](installation.md).

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

**VPS — compte administrateur créé par radio-vpn, session SSH Bash :**

```bash
sudo apt update
sudo apt install -y git rsync
cd "$HOME"
git clone https://github.com/SmallTech2/radio-vpn-backup.git
cd "$HOME/radio-vpn-backup"
git rev-parse HEAD
read -r -p 'Coller la ligne PUBLIQUE SSH de collecte : ' ABB_PUBLIC_KEY
PUB="$HOME/radio-vpn-abb.pub"
printf '%s\n' "$ABB_PUBLIC_KEY" > "$PUB"
ssh-keygen -lf "$PUB"
```

Comparer cette empreinte avec celle du poste. Si le clone existe déjà, utiliser son
répertoire propre et `git pull --ff-only`, au lieu de le cloner à nouveau.

**Même session VPS, dans le clone :**

```bash
sudo bash install.sh "$PUB"
```

L’installateur demande l’heure quotidienne `HH:MM`, **02:17 par défaut, heure locale du
VPS**. Il installe Python 3, cron, util-linux et rsync, crée le compte et la clé restreinte,
les répertoires et `/etc/cron.d/radio-vpn-backup`. Sans terminal en entrée, l’heure par
défaut est conservée. Age n’est pas installé pour la sauvegarde standard.

Si le compte ou la configuration existe déjà, ne pas relancer l’installateur : suivre
la [maintenance](maintenance.md#installation-vps-déjà-présente-ou-partielle).

## 4. Produire une archive

**VPS — même administrateur :**

```bash
sudo /usr/local/sbin/radio-vpn-backup
LATEST=$(sudo find /var/lib/radio-vpn-export -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail -n 1)
printf 'Identifiant publié : %s\n' "$LATEST"
ARCHIVE_DIR="/var/lib/radio-vpn-export/$LATEST"
sudo ls -l "$ARCHIVE_DIR"
sudo sh -c 'cd "$1" && sha256sum -c SHA256SUMS && gzip -t backup.tar.gz' sh "$ARCHIVE_DIR"
```

Pour ce parcours standard, répondre Entrée ou `n` à la question de chiffrement. Le
répertoire daté contient `backup.tar.gz` et `SHA256SUMS`. Ne poursuivre qu’après `OK`.
La copie suspend brièvement l’UI et le renouvellement CRL ; OpenVPN reste actif.
Ne pas administrer la PKI pendant cette copie. Pour age, suivre le [guide séparé](encryption.md).

Le cron n’attend aucune saisie : `ENCRYPT=false` dans `/etc/radio-vpn-backup.conf` produit
une archive non chiffrée ; `ENCRYPT=true` nécessite age et ses destinataires publics.
`KEEP_VPS=3` conserve trois points locaux ; les valeurs acceptées vont de 2 à 30.
Les chemins, permissions et formats sont décrits dans la [référence](format.md).

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
