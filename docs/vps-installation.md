# Installer radio-vpn-backup sur le VPS

Cette installation est **commune aux deux méthodes de collecte NAS** : ABB et collecteur
personnalisé. Elle prépare les archives sur le VPS ; elle ne configure pas leur récupération
sur le NAS. La configuration de la collecte vient ensuite.

## 1. Préparer le serveur

Le VPS doit utiliser **Debian 13 AMD64**, avec [radio-vpn](https://github.com/SmallTech2/radio-vpn/blob/main/docs/installation.md)
complètement installé, un compte administrateur avec sudo et un accès SSH par clé.
Prévoir l’accès HTTPS aux dépôts Debian/GitHub et l’espace nécessaire aux copies et archives.

**Après une reconstruction et une restauration avec radio-vpn-restore**, effectuer aussi
cette installation : la restauration ne recrée ni le programme radio-vpn-backup, ni son
compte de collecte, ni sa configuration ou son cron. Si radio-vpn-backup est déjà installé,
ne pas relancer l’installateur : suivre la [maintenance](maintenance.md#installation-vps-déjà-présente-ou-partielle).

## 2. Disposer de la clé publique de collecte

L’installateur exige un fichier contenant **une seule clé publique SSH ED25519** de la
future collecte. La clé privée reste du côté qui se connectera au VPS, jamais sur ce VPS :

- **ABB** : [préparer la clé sur le poste d’administration](abb.md#2-préparer-la-clé-ssh-de-collecte), puis importer sa partie privée dans ABB lors de la configuration de la collecte.
- **Sans ABB** : suivre les [étapes 1 à 4 du guide personnalisé](installation.md#1-identifier-les-trois-machines-et-les-comptes), pour préparer le compte NAS et y générer sa clé sous le compte qui exécutera la tâche DSM.

Si une collecte existe déjà après reconstruction du VPS, réutiliser sa clé publique
correspondant à la clé privée conservée dans ABB ou sur le NAS. Il n’est pas nécessaire
de générer une nouvelle paire. Garder la ligne publique et son empreinte pour l’étape suivante.

## 3. Préparer Git et le fichier de clé publique sur le VPS

**VPS — compte administrateur Linux, session SSH Bash :**

```bash
sudo apt update
sudo apt install -y git
cd "$HOME"
git clone https://github.com/SmallTech2/radio-vpn-backup.git
cd "$HOME/radio-vpn-backup"
git rev-parse HEAD
read -r -p 'Coller la ligne PUBLIQUE SSH de collecte : ' COLLECT_PUBLIC_KEY
PUB="$HOME/radio-vpn-collecte.pub"
printf '%s\n' "$COLLECT_PUBLIC_KEY" > "$PUB"
ssh-keygen -lf "$PUB"
```

Comparer l’empreinte affichée avec celle de la clé préparée sur le poste ou le NAS.
`PUB` désigne le fichier réellement créé sur le VPS, pas la clé privée. Noter le commit
pour identifier la révision installée.

Si le clone existe déjà, utiliser son dossier propre et `git pull --ff-only` au lieu de
le cloner à nouveau. Conserver la même session pour les commandes utilisant `PUB`.

## 4. Installer le programme et le cron

**VPS — même administrateur, dans le clone :**

```bash
sudo bash install.sh "$PUB"
```

L’installateur demande l’heure quotidienne au format `HH:MM`, en **heure locale du VPS**.
Entrée conserve **02:17**. Sans terminal en entrée, l’heure par défaut est conservée.

Il installe les paquets Python 3, cron, util-linux et rsync nécessaires ; les scripts et
la commande `/usr/local/sbin/radio-vpn-backup` ; le compte `radio-vpn-backup` et sa clé
restreinte ; la configuration et `/etc/cron.d/radio-vpn-backup`. Il crée le stockage interne
root `/var/lib/radio-vpn-backup` et l’export `/var/lib/radio-vpn-export`, accessible en lecture
seule au compte de collecte. Ce compte n’a ni sudo ni shell libre. La PKI n’est pas modifiée.

Si SSH utilise des règles `AllowUsers` ou `AllowGroups` personnalisées, le compte de
collecte doit y être autorisé sans retirer l’administrateur. L’installateur ne modifie
pas ces règles SSH globales.

La configuration initiale `/etc/radio-vpn-backup.conf` contient `KEEP_VPS=3` et
`ENCRYPT=false`. Age n’est pas installé pour le mode standard. L’installateur refuse
un compte ou une configuration de sauvegarde déjà présents ; il ne répare pas une
installation partielle. Les [fichiers et permissions](format.md) sont décrits séparément.

## 5. Produire une première sauvegarde

**VPS — même administrateur :**

```bash
sudo cat /etc/radio-vpn-backup.conf
sudo cat /etc/cron.d/radio-vpn-backup
sudo systemctl is-active cron
sudo /usr/local/sbin/radio-vpn-backup
```

Répondre **Entrée** ou **n** à la question de chiffrement pour ce parcours standard.
Ce choix vaut pour cette exécution ; cron utilise la configuration sans poser de question.
La sauvegarde suspend brièvement l’UI et le renouvellement CRL, mais ne redémarre pas
OpenVPN. Ne pas administrer la PKI pendant sa préparation.

**Après réussite de la sauvegarde, même session VPS :**

```bash
LATEST=$(sudo find /var/lib/radio-vpn-export -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail -n 1)
printf 'Identifiant publié : %s\n' "$LATEST"
ARCHIVE_DIR="/var/lib/radio-vpn-export/$LATEST"
sudo ls -l "$ARCHIVE_DIR/backup.tar.gz" "$ARCHIVE_DIR/SHA256SUMS"
sudo sh -c 'cd "$1" && sha256sum -c SHA256SUMS && gzip -t backup.tar.gz' sh "$ARCHIVE_DIR"
sudo python3 /usr/local/lib/radio-vpn-backup/snapshot.py check "$ARCHIVE_DIR/backup.tar.gz"
```

Le dossier publié appartient à `root:radio-vpn-backup` (mode 750), ses fichiers sont
en mode 640. L’identifiant doit être non vide et SHA-256 doit afficher `OK` ; gzip et le contrôle
interne sont silencieux en cas de réussite. L’archive contient notamment la clé privée
de la CA : réserver son accès aux personnes chargées de la sauvegarde. Le
[chiffrement age](encryption.md) est une option séparée.

## 6. Configurer la récupération sur le NAS

Une fois le programme installé et l’archive produite, choisir **une seule** collecte :

- [ABB : configuration de la tâche et de la rétention](abb.md#5-configurer-abb).
- [Sans ABB : installation des outils NAS et configuration du collecteur](installation.md#8-mettre-les-outils-sur-le-nas-et-vérifier-lidentité-ssh-du-vps), après la préparation NAS de l’étape 2 ci-dessus.

Programmer la collecte après l’heure de préparation du VPS, avec une marge et les fuseaux
horaires appropriés. Après reconstruction, vérifier la nouvelle empreinte d’hôte du VPS
avant de rétablir la connexion du NAS. Installer le programme sur le VPS ne reconfigure
pas automatiquement une tâche ABB ou DSM existante.
