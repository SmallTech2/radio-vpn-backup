# Méthode principale : Active Backup for Business, rsync sur SSH

Le VPS prépare son archive par cron. **ABB collecte et conserve les versions sur le NAS**.
Le projet de restauration reste inchangé. Le seul compte SSH VPS utilisé est
`radio-vpn-backup`, déjà créé par l'installateur ; aucun deuxième compte Linux n'est nécessaire.

## Statut de compatibilité : lire avant installation

Synology documente le mode **rsync shell via SSH**, rsync 3 ou supérieur et l'authentification
par clé, dont ED25519 sans phrase secrète. Il ne publie pas dans ce guide l'ensemble des
commandes de découverte exécutées par chaque version d'ABB.

Le projet conserve la commande forcée et délègue les demandes rsync à **`rrsync -ro -no-del`**,
fourni par le paquet Debian. Cette restriction interdit l'envoi de fichiers au VPS, la
suppression des sources et la lecture hors de l'export. Le client rsync standard peut
transférer les fichiers ; **cela ne prouve pas que l'assistant de votre ABB est compatible**.

**Limite bloquante possible : `rrsync` refuse `-s` / `--protect-args`**, car ces arguments
pourraient lui cacher les options et chemins à contrôler. Il refuse aussi les sondes shell
non autorisées (`uname`, `ls`, commandes composées...). Si votre ABB impose ces commandes,
son assistant ou la collecte échouera. Ne pas retirer ces contrôles, le préfixe `command=`,
ou remplacer la racine par `/` côté serveur pour contourner le refus.

Dans ce cas, conserver le message ABB et utiliser l'[alternative personnalisée](installation.md)
en attendant une analyse de la commande réellement demandée. Un shell général rendrait les
fichiers lisibles par le compte accessibles hors de l'export et violerait l'objectif de
confinement. La protection Unix de la PKI seule ne remplace pas cette restriction.

Références primaires : [guide Synology des serveurs de fichiers](https://kb.synology.com/en-my/UG/Synology_ABB_admin_guide_File_Servers/4),
[restrictions rrsync](https://raw.githubusercontent.com/RsyncProject/rsync/v3.4.1/support/rrsync.1.md),
[contenu du paquet Debian 13](https://packages.debian.org/trixie/amd64/rsync/filelist).

## 1. Prérequis et rôles

- **VPS** : Debian 13 AMD64, radio-vpn radio-v2.4 complètement installé, SSH par clé
  administrateur vérifié, espace libre et accès sortant aux dépôts Debian/GitHub.
- **NAS** : modèle/DSM et stockage pris en charge par ABB, paquet ABB installé et activé,
  espace disponible et accès réseau au port SSH public du VPS, même sans OpenVPN.
- **Poste d'administration** : accès SSH administrateur au VPS et navigateur DSM pour ABB.

Dans le Centre de paquets DSM, installer/ouvrir ABB avec un compte autorisé à gérer les
tâches. Vérifier ses prérequis de volume et de capacité dans l'assistant du paquet.
Le compte DSM `vpn-backup` et le partage `VPN-Backup` que vous avez éventuellement créés
**ne sont pas automatiquement utilisés par ABB**. ABB gère l'exécution et le stockage de
ses tâches. Choisir la destination qu'il propose ; ne pas lui attribuer arbitrairement un
chemin interne. Ne pas créer de tâche DSM du collecteur personnalisé pour la même collecte.

SSH utilise le port **22 si votre VPS écoute bien sur 22**. Garder le port réellement
utilisé si vous l'avez personnalisé ; ne pas modifier SSH pour revenir à 22.
Ce mode ne demande ni agent ABB Linux, ni démon rsync, ni port TCP 873.

## 2. Choisir la clé SSH pour ABB

**Poste d'administration :** vous pouvez importer dans ABB la clé privée de collecte déjà
autorisée pour `radio-vpn-backup`, si vous en maîtrisez l'emplacement et l'accès. Sinon,
générer une clé dédiée ABB ; elle donnera accès au **même compte Linux**.

**Poste Windows — PowerShell**, exemple de création sans écrasement volontaire :

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
$AbbKey = Join-Path $env:USERPROFILE '.ssh\radio-vpn-abb-vps1'
ssh-keygen -t ed25519 -f $AbbKey -C 'abb-vps1'
ssh-keygen -lf ($AbbKey + '.pub')
Get-Content -LiteralPath ($AbbKey + '.pub')
Write-Output "Fichier prive a importer dans ABB : $AbbKey"
```

Aux deux questions de phrase secrète de `ssh-keygen`, appuyer sur Entrée : le guide Synology
exclut les clés avec phrase secrète pour cette authentification. Si le fichier existe,
répondre **non** à l'écrasement et vérifier son usage. Ne jamais afficher la clé privée.

**Poste Linux/macOS — Bash**, alternative :

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/radio-vpn-abb-vps1" -C 'abb-vps1'
ssh-keygen -lf "$HOME/.ssh/radio-vpn-abb-vps1.pub"
cat "$HOME/.ssh/radio-vpn-abb-vps1.pub"
```

Le fichier sans `.pub` est privé, à importer dans ABB depuis le poste de confiance.
Seule la ligne `.pub` est transmise au VPS. Protéger la clé privée et limiter l'accès aux
administrateurs de la tâche ABB : une archive standard contient les secrets de la CA.

## 3. Installer les prérequis et récupérer le projet sur le VPS

**VPS — compte administrateur Linux choisi dans radio-vpn, session SSH Bash :**

```bash
sudo apt update
sudo apt install -y git rsync
command -v rsync
command -v rrsync
cd "$HOME"
git clone https://github.com/SmallTech2/radio-vpn-backup.git
cd "$HOME/radio-vpn-backup"
git rev-parse HEAD
```

Si le dépôt existe déjà : vérifier `git status`, puis utiliser `git pull --ff-only` dans
ce dossier propre, au lieu de le cloner à nouveau. Le paquet `rsync` doit fournir
`/usr/bin/rsync` et `/usr/bin/rrsync` ; aucun téléchargement de script rrsync tiers n'est requis.

**VPS — même compte :** copier la seule ligne publique affichée à l'étape 2 :

```bash
read -r -p 'Coller la ligne PUBLIQUE SSH pour ABB : ' ABB_PUBLIC_KEY
PUB="$HOME/radio-vpn-abb-vps1.pub"
printf '%s\n' "$ABB_PUBLIC_KEY" > "$PUB"
ssh-keygen -lf "$PUB"
```

Comparer cette empreinte avec celle du poste. Le fichier `PUB` est maintenant un chemin
réel créé sur le VPS, avec la fin de ligne attendue par l'installateur.

## 4. Nouvelle installation OU adaptation du compte existant

### Si radio-vpn-backup n'est pas encore installé

**VPS — même compte, dans le dépôt :**

```bash
sudo bash install.sh "$PUB"
```

L'installateur crée `radio-vpn-backup`, installe les scripts et la clé restreinte, les
paquets Python/cron/util-linux/rsync et le cron. Il n'installe pas age et n'arrête pas OpenVPN.

### Si le compte et l'installation existent déjà

**Ne pas relancer l'installateur ni créer un deuxième compte.** Mettre à jour seulement
la commande forcée au chemin déjà utilisé par les clés existantes :

**VPS — administrateur, dépôt à jour :**

```bash
id radio-vpn-backup
sudo test -f /etc/radio-vpn-backup.conf
sudo install -o root -g root -m 755 scripts/export.sh /usr/local/lib/radio-vpn-backup/export.sh
sudo ssh-keygen -lf /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
```

Le paquet rsync a été installé à l'étape 3. Les clés existantes gardent exactement leur
commande forcée `export.sh`, qui sait maintenant appeler rrsync en lecture seule.
Si la clé ABB est déjà dans la liste d'empreintes, ne rien ajouter. Sinon, **même compte VPS** :

```bash
{ printf 'restrict,command="/usr/local/lib/radio-vpn-backup/export.sh" '; cat "$PUB"; } \
  | sudo tee -a /var/lib/radio-vpn-backup-user/.ssh/authorized_keys >/dev/null
sudo chown root:radio-vpn-backup /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
sudo chmod 640 /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
sudo /usr/sbin/sshd -t
```

Conserver les anciennes lignes, notamment celle du collecteur personnalisé. Ne pas ajouter
de clé sans le préfixe restrictif. Ne pas activer de mot de passe SSH, sudo ou shell libre
pour ce compte. Aucun rechargement SSH ni redémarrage OpenVPN n'est nécessaire.

## 5. Produire une première archive et vérifier les accès

**VPS — administrateur :**

```bash
sudo cat /etc/radio-vpn-backup.conf
sudo /usr/local/sbin/radio-vpn-backup
sudo ls -lt /var/lib/radio-vpn-export
sudo ls -ld /var/lib/radio-vpn-backup /var/lib/radio-vpn-export /var/lib/radio-vpn-backup-user
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Pour la première recette standard, la configuration doit indiquer `ENCRYPT=false` et
`KEEP_VPS=3`. Le dernier répertoire daté doit contenir `backup.tar.gz` et `SHA256SUMS`.
Les [contrôles complets d'archive](installation.md#7-faire-et-vérifier-la-première-sauvegarde-sans-chiffrement)
se font avant de configurer la collecte. Ne pas administrer la PKI pendant la copie.

Le stockage interne `/var/lib/radio-vpn-backup` reste root 0700. L'export est
root:`radio-vpn-backup` 0750, ses fichiers 0640. La PKI et ses permissions ne sont pas changées.
Noter l'empreinte d'hôte affichée pour comparer toute clé présentée par ABB ; ne pas
accepter aveuglément une clé différente ou désactiver sa vérification.

## 6. Configurer ABB

**NAS — interface ABB, compte DSM autorisé à gérer ABB :** dans **Serveur de fichiers >
Serveurs de fichiers > Ajouter un serveur**, choisir rsync. Les libellés exacts varient
selon la version ; les valeurs à renseigner sont les suivantes :

| Champ | Valeur |
| --- | --- |
| Type de source | Serveur de fichiers rsync, sans agent |
| Adresse du serveur | IPv4 publique réelle du VPS, relevée chez l'hébergeur |
| Mode de connexion | **rsync shell via SSH**, pas module/daemon |
| Port | **22** si SSH écoute sur 22, sinon son port réel |
| Compte | **`radio-vpn-backup`** |
| Authentification | Clé SSH, importer le fichier **privé** sans `.pub` de l'étape 2 |
| Élévation / sudo | Aucune |

Tester la connexion et vérifier l'empreinte d'hôte si l'interface la présente. L'import
effectif du fichier de clé et les sondes de connexion restent à valider dans votre ABB.
Ne pas remplacer la clé par le mot de passe de l'administrateur pour faire passer un test.

Créer ensuite la tâche du serveur :

| Champ | Choix |
| --- | --- |
| Mode de sauvegarde | **Multi-versionné** pour utiliser la rétention ABB |
| Sélection distante | Racine virtuelle **`/`** et ses sous-dossiers, si l'assistant permet ce choix |
| Répertoire physique correspondant | **`/var/lib/radio-vpn-export`** sur le VPS |
| Destination locale | Stockage proposé/géré par ABB ; relever le choix réel dans l'assistant |
| Planification | Après la préparation cron du VPS, avec marge et fuseaux horaires vérifiés |
| Rétention | Configurer dans ABB, par exemple 7 points quotidiens et 4 hebdomadaires |

**La `/` affichée à rsync est une racine virtuelle limitée par rrsync à l'export. Elle ne
donne pas accès à la racine réelle du VPS.** Ne pas saisir `/var/lib/radio-vpn-export` comme
chemin virtuel : il serait recherché à l'intérieur de l'export. Si ABB exige de parcourir
la vraie racine, échoue avec `-s`, ou ne propose pas ce choix, arrêter la recette : la
compatibilité de cette version d'ABB n'est pas établie avec ces restrictions.

Cron prépare à **02:17 heure du VPS** ; ABB a l'heure du NAS. Vérifier `timedatectl` sur
le VPS et l'heure DSM, puis choisir l'horaire en conséquence. ABB assure sa rétention ;
`DAILY`/`WEEKLY` du collecteur alternatif n'ont aucun effet sur ABB. Le VPS garde toujours
ses 3 archives par défaut, même si ABB ne collecte plus : surveiller les deux tâches.

## 7. Vérifier la première collecte

**ABB — même opérateur DSM :** lancer une collecte manuelle et examiner le résultat et les
journaux de tâche. La réussite du simple test de connexion ne suffit pas. Dans la version
collectée, vérifier la présence d'un répertoire daté complet et de ses deux fichiers.
Télécharger `backup.tar.gz` **et** `SHA256SUMS`, sans restaurer vers le serveur source.

**VPS — administrateur :** après transfert des deux fichiers dans un dossier personnel
privé, se placer dans ce dossier réel et exécuter :

```bash
sha256sum -c SHA256SUMS
gzip -t backup.tar.gz
sudo python3 /usr/local/lib/radio-vpn-backup/snapshot.py check "$PWD/backup.tar.gz"
```

Le premier contrôle doit donner `OK`, les suivants réussir. Pour un `.age`, vérifier
SHA-256 puis utiliser le [guide de chiffrement](encryption.md), pas gzip directement.
Attendre ensuite un cycle automatique et vérifier qu'une nouvelle archive préparée a été
collectée. Observer la conservation des anciennes versions malgré la purge locale du VPS.

## 8. Récupérer une archive pour reconstruire un VPS

**NAS — opérateur ABB :** dans le navigateur de restauration/ABB Portal proposé par votre
version, choisir la tâche et le point voulu. Télécharger le dossier daté ou ses fichiers
archive + `SHA256SUMS` sur le poste d'administration. Si l'interface propose seulement
une restauration vers le serveur source, ne pas l'utiliser : les écritures SSH sont
volontairement refusées. Vérifier l'option de téléchargement/restauration locale disponible
dans votre ABB ; les chemins internes du stockage ABB ne sont pas des fichiers à manipuler.

Pour suivre le guide `radio-vpn-restore` sans le modifier, conserver le nom original de
l'archive et créer une copie du fichier de sommes avec le nom attendu. **Nouveau VPS —
administrateur, dans le dossier privé contenant les fichiers transférés :**

```bash
sha256sum -c SHA256SUMS
cp SHA256SUMS backup.tar.gz.sha256
```

Pour une archive chiffrée, le nom correspondant est `backup.tar.gz.age.sha256`.
Cette copie ne change ni l'empreinte ni le contenu de l'archive. Suivre ensuite le
[guide de restauration existant](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md).

## Diagnostic et limites

Sur le **VPS, administrateur**, ces commandes lisent la configuration et les logs :

```bash
sudo /usr/sbin/sshd -t
sudo journalctl -u ssh -n 80 --no-pager
sudo journalctl -t radio-vpn-backup-ssh --since today --no-pager
sudo systemctl is-active openvpn@server.service openvpn-ui.service cron
```

Le journal des refus ne stocke pas les arguments SSH complets, afin de ne pas enregistrer
des valeurs imprévues sensibles. Les erreurs natives de rrsync sont renvoyées au client ;
conserver le message de tâche ABB, les versions de DSM/ABB et `rsync --version` du VPS.
Ne pas assouplir les restrictions pour une sonde inconnue sans examiner son besoin précis.

Éléments vérifiables automatiquement : transferts SSH/rsync natifs en loopback, confinement,
lecture seule et protocole personnalisé. Éléments **non vérifiés sur votre Synology** :
sondes exactes, import de clé, navigation de sélection, première collecte, rétention et
téléchargement via ABB. La recette doit confirmer chacun d'eux avant utilisation régulière.
