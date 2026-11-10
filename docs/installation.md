# Méthode alternative : collecteur Synology personnalisé

Cette procédure conserve le collecteur `nas-pull.sh`, pour les utilisateurs sans ABB.
Pour **Active Backup for Business**, suivre uniquement le [guide ABB](abb.md) : son
authentification, sa tâche et sa rétention ne dépendent pas de ce compte DSM ni de ce planificateur.

Suivre les étapes dans l'ordre. Chaque bloc indique la machine et le compte concernés.
Les commandes sont à saisir dans Bash, sauf indication contraire. Conserver les sessions
ouvertes : les variables définies dans un bloc servent aux suivants. Après reconnexion,
redéfinir les variables indiquées avant de poursuivre.

## 1. Identifier les trois machines et les comptes

| Machine | Compte | Rôle |
| --- | --- | --- |
| Poste d'administration | Votre compte habituel | Navigateur DSM/GitHub et connexions SSH |
| VPS Debian 13 AMD64 | Administrateur Linux créé par radio-vpn, avec sudo | Installation et préparation des archives |
| NAS Synology | Administrateur DSM | Création du compte et préparation initiale seulement |
| NAS Synology | `vpnbackup`, compte local non administrateur à créer | Clé SSH, collecte et tâche planifiée |
| VPS | `radio-vpn-backup`, créé automatiquement par l'installateur | Lecture distante des archives par commande SSH restreinte |

`vpnbackup` et `radio-vpn-backup` sont deux comptes différents, sur deux machines différentes.
`vps1` sera le nom local choisi ici pour identifier votre premier VPS ; ce n'est ni une
adresse ni un compte. Pour un autre VPS, utiliser un autre nom et une autre clé dédiée.
Pour un deuxième serveur, remplacer `vps1` dans les noms de clé, configuration, tâche et
dossier, sans écraser ceux du premier serveur.

**Prérequis VPS :** installation radio-vpn **terminée**, accès SSH en IPv4 et
clé administrateur fonctionnels, sudo, accès HTTPS sortant à Debian et GitHub, espace
libre pour la copie de travail et les archives. Le numéro de version ne bloque pas la
sauvegarde : les composants sont contrôlés, notamment sur une installation radio-v2.1.
Voir les [éléments indispensables et facultatifs](format.md#compatibilité). Une
installation OpenVPN personnalisée avec d’autres chemins n’est pas automatiquement prise en charge.

**Prérequis NAS :** DSM avec Planificateur de tâches et File Station, Bash, client
OpenSSH (`ssh`, `ssh-keygen`, `ssh-keyscan`), `sha256sum` et Python 3.8 ou ultérieur.
Le NAS doit pouvoir joindre l'IPv4 publique et le port SSH du VPS même sans VPN.
Il n'a pas besoin de Git, de sudo pour la collecte, ni d'`age` en mode standard.

**Confidentialité :** les `.tar.gz` contiennent notamment la clé privée de la CA et les
clés clients, sans chiffrement. Ce choix volontaire simplifie la restauration ; son risque
est accepté. Réserver leurs dossiers au compte de sauvegarde et aux administrateurs.
Ne pas les publier, les partager publiquement ou les joindre à un ticket de dépannage.

## 2. Créer le compte sur le Synology

**Poste d'administration — navigateur connecté à DSM avec un administrateur.**

1. Dans **Panneau de configuration > Utilisateur et groupe**, créer l'utilisateur local
   `vpnbackup`, avec un mot de passe fort conservé dans votre coffre.
2. Le laisser dans le groupe normal `users`, sans l'ajouter à `administrators`.
3. Dans les paramètres avancés des utilisateurs, activer le **service d'accueil utilisateur**
   s'il ne l'est pas déjà. Chaque utilisateur obtient son dossier personnel `home`.
4. Autoriser à `vpnbackup` la connexion DSM et File Station nécessaires à ces opérations.
   Ne lui accorder ni autres applications inutiles, ni lecture/écriture sur les partages métiers.
5. Conserver les autorisations par défaut du dossier partagé `homes`. **Ne pas ajouter un
   refus global à `users` ou à `vpnbackup` sur `homes`** : cela peut bloquer son propre dossier.
6. Se connecter à DSM dans une autre fenêtre avec `vpnbackup` : vérifier qu'il peut écrire
   dans `home`, mais pas consulter les dossiers des autres utilisateurs.

Les ACL DSM et les permissions Linux se cumulent. Dans File Station, **Propriétés >
Permission > Options avancées > Inspecteur de permissions**, vérifier les accès effectifs
au dossier de sauvegarde. Les administrateurs du NAS restent capables d'y accéder.
Les libellés peuvent varier avec DSM ; voir les [références Synology](#références-dsm).

## 3. Ouvrir un terminal sous le bon compte NAS

**DSM — administrateur :** dans **Panneau de configuration > Terminal et SNMP**, activer
temporairement SSH et noter son port. Limiter l'accès au réseau d'administration ; ne pas
ouvrir le SSH du NAS sur Internet pour cette procédure.

**Poste d'administration :** avec votre client SSH habituel, se connecter au NAS avec
son adresse LAN réelle, le port relevé et le compte administrateur DSM. Le compte
`vpnbackup` n'a pas besoin d'une connexion SSH entrante : la préparation se fait par sudo
depuis cette session administrateur, la collecte utilisera ensuite une connexion sortante.

**NAS — session administrateur, puis changement de compte :**

```bash
sudo -u vpnbackup -H /bin/bash
id -un
printf 'Dossier personnel : %s\n' "$HOME"
```

Le premier résultat doit être `vpnbackup`. Le mot de passe demandé par sudo est celui de
l'administrateur DSM. Ne pas utiliser le mot de passe du VPS. Ne pas lancer la suite en root.

**NAS — compte `vpnbackup`, dans ce Bash :**

```bash
umask 077
mkdir -p "$HOME/radio-vpn/keys" "$HOME/radio-vpn/config" \
  "$HOME/radio-vpn/archives" "$HOME/radio-vpn/logs" "$HOME/radio-vpn/tools"
cd "$HOME/radio-vpn"
NAS_BASE=$(pwd -P)
chmod 700 "$NAS_BASE" "$NAS_BASE/keys" "$NAS_BASE/config" \
  "$NAS_BASE/archives" "$NAS_BASE/logs" "$NAS_BASE/tools"
printf 'Chemin réel à conserver : %s\n' "$NAS_BASE"
for outil in bash ssh ssh-keygen ssh-keyscan sha256sum python3; do
  command -v "$outil" || printf 'MANQUANT : %s\n' "$outil"
done
python3 --version
```

Ne pas poursuivre si un outil manque. Pour Python, l'administrateur peut installer le
paquet Python3 disponible dans le **Centre de paquets**, puis rouvrir le terminal et refaire
ces contrôles. Si le binaire n'est pas dans le PATH, l'administrateur peut rechercher son
chemin réel avec `find /var/packages -name python3 2>/dev/null`. Revenir sous `vpnbackup`
et utiliser le chemin réellement trouvé, pas un exemple :

```bash
read -r -p 'Chemin absolu du binaire python3 trouvé : ' PYTHON_BIN
"$PYTHON_BIN" --version
export PATH="$(dirname "$PYTHON_BIN"):$PATH"
command -v python3
```

Ne pas utiliser `apt` sur DSM ni inventer un chemin `/volume1` ou un chemin de paquet.
Si Bash/OpenSSH sont absents, faire vérifier la compatibilité du modèle/DSM avant de continuer.

Après une nouvelle connexion sous `vpnbackup`, retrouver la base avec :

```bash
cd "$HOME/radio-vpn"
NAS_BASE=$(pwd -P)
```

## 4. Générer la clé SSH sur le NAS

**NAS — compte `vpnbackup`, jamais sur le VPS :**

```bash
KEY="$NAS_BASE/keys/vps1_ed25519"
ssh-keygen -t ed25519 -N '' -f "$KEY" -C 'vpnbackup-vps1'
chmod 600 "$KEY"
chmod 644 "$KEY.pub"
ssh-keygen -lf "$KEY.pub"
cat "$KEY.pub"
```

`-t ed25519` choisit le type accepté par l'installateur. `-N ''` produit une clé sans
phrase secrète pour une tâche automatique sans agent SSH. Elle doit donc rester privée.
`-f` fixe son emplacement. **Si ces fichiers existent déjà, ne pas les écraser** : répondre
`n` à toute demande d'écrasement et vérifier leur usage avant de poursuivre.

- `vps1_ed25519` : clé **privée**, reste sur le NAS, accessible seulement à `vpnbackup`.
- `vps1_ed25519.pub` : clé **publique**, une ligne commençant par `ssh-ed25519`, à copier au VPS.

Copier uniquement la ligne affichée par `cat "$KEY.pub"`. Ne jamais afficher/copier la
clé privée dans le terminal, une documentation ou un message. Noter l'empreinte publique.

## 5. Préparer Git et copier la clé publique sur le VPS

**VPS — compte administrateur Linux choisi pendant l'installation radio-vpn, via SSH :**

```bash
sudo apt update
sudo apt install -y git
read -r -p 'Coller la ligne de clé PUBLIQUE SSH du NAS : ' NAS_PUBLIC_KEY
PUB="$HOME/vps1-nas.pub"
printf '%s\n' "$NAS_PUBLIC_KEY" > "$PUB"
ssh-keygen -lf "$PUB"
```

Comparer l'empreinte avec celle de l'étape NAS. `PUB` désigne maintenant un vrai fichier
dans le dossier personnel de l'administrateur VPS, avec la fin de ligne attendue par
l'installateur. Ce n'est pas la clé privée et ce n'est pas un chemin à deviner.

**VPS — même compte :**

```bash
cd "$HOME"
git clone https://github.com/SmallTech2/radio-vpn-backup.git
cd "$HOME/radio-vpn-backup"
git rev-parse HEAD
```

Noter le commit utilisé. Si le dossier du dépôt existe déjà, ne pas le cloner par-dessus :
vérifier `git status`, puis utiliser `git pull --ff-only` dans ce dossier s'il est propre.

## 6. Installer le système de sauvegarde sur le VPS

**VPS — même compte, dans `$HOME/radio-vpn-backup` :**

```bash
sudo bash install.sh "$PUB"
sudo cat /etc/radio-vpn-backup.conf
sudo systemctl is-active cron
```

Le script installe Python 3, cron et util-linux si nécessaire, les scripts sous
`/usr/local/lib/radio-vpn-backup`, la commande `/usr/local/sbin/radio-vpn-backup`, le
compte VPS `radio-vpn-backup` et sa clé autorisée. Il n'installe pas `age`.
La configuration doit indiquer `KEEP_VPS=3` et `ENCRYPT=false`.

Le paquet `rsync` est également installé ; la commande forcée commune permet aussi la
lecture seule rsync confinée à l'export. Cela n'impose pas d'utiliser ABB pour ce collecteur.

L'installateur refuse un compte `radio-vpn-backup` ou une configuration déjà présents.
**Il ne s'agit pas d'une commande de réinstallation.** Si l'installation est déjà terminée,
passer à l'étape 7. Si elle est partielle, consulter le [dépannage](maintenance.md) ; ne pas
supprimer au hasard un compte, ses fichiers ou la PKI pour forcer l'exécution.

La clé autorisée impose une commande restreinte : `list`, `hash IDENTIFIANT`,
`get IDENTIFIANT`, ou rsync en lecture seule dans l'export. Pas de shell libre, terminal,
sudo, transfert de ports ou modification VPN.
En mode standard, le compte peut néanmoins lire les secrets **contenus dans l'archive**.
Si SSH utilise des règles `AllowUsers`/`AllowGroups` personnalisées, le compte doit y être
autorisé sans retirer l'administrateur. Cette personnalisation n'est pas faite par l'outil.

## 7. Faire et vérifier la première sauvegarde sans chiffrement

En lançant la commande dans votre terminal, répondre **Entrée** ou **n** à
« Voulez-vous chiffrer la sauvegarde avec age ? [o/N] ». Ce choix vaut uniquement pour
cette exécution ; le cron de 02:17 reste sans interaction et lit `ENCRYPT` dans la configuration.

**VPS — administrateur :**

```bash
sudo /usr/local/sbin/radio-vpn-backup
LATEST=$(sudo find /var/lib/radio-vpn-export -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail -n 1)
printf 'Identifiant publié : %s\n' "$LATEST"
ARCHIVE_DIR="/var/lib/radio-vpn-export/$LATEST"
sudo ls -ld "$ARCHIVE_DIR"
sudo ls -l "$ARCHIVE_DIR/backup.tar.gz" "$ARCHIVE_DIR/SHA256SUMS"
sudo sh -c 'cd "$1" && sha256sum -c SHA256SUMS && gzip -t backup.tar.gz' sh "$ARCHIVE_DIR"
sudo python3 /usr/local/lib/radio-vpn-backup/snapshot.py check "$ARCHIVE_DIR/backup.tar.gz"
```

Ne poursuivre qu'après réussite de la commande et apparition d'un identifiant non vide.
SHA-256 doit afficher `OK` ; gzip et le contrôle interne sont silencieux en cas de succès.
Le dossier doit appartenir à `root:radio-vpn-backup`, mode 750, les fichiers mode 640.
L'UI est brièvement indisponible pendant la copie ; **OpenVPN et ses clients ne sont pas
redémarrés**. Ne faire aucune opération PKI manuelle pendant la préparation.

## 8. Mettre les outils sur le NAS et vérifier l'identité SSH du VPS

**Poste d'administration — navigateur :** ouvrir le dépôt
[radio-vpn-backup](https://github.com/SmallTech2/radio-vpn-backup). Ouvrir le commit relevé
à l'étape 5, puis **Browse files / Parcourir les fichiers > Code > Download ZIP** pour
télécharger précisément cette révision. Décompresser sur le poste. Dans DSM/File Station
**connecté avec `vpnbackup`**, déposer
le dossier décompressé dans `home/radio-vpn/tools`, puis le renommer `radio-vpn-backup`.
Il doit contenir `nas-pull.sh` et `scripts/retention.py`, sans niveau de dossier supplémentaire.
Cette méthode évite d'installer Git sur le NAS. Utiliser la même révision des scripts NAS
et VPS ; l'identifiant du commit figure sur GitHub et dans le clone VPS de l'étape 5.

**VPS — administrateur, dans la session déjà reconnue comme fiable :**

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Conserver cette empreinte d'hôte : elle est différente de l'empreinte de la clé du NAS.
Relever aussi l'IPv4 publique dans le panneau de l'hébergeur et le port utilisé par votre
connexion SSH au VPS. Ce sont les valeurs réelles demandées dans le bloc suivant.

**NAS — compte `vpnbackup`, avec `NAS_BASE` redéfini si nécessaire :**

```bash
test -f "$NAS_BASE/tools/radio-vpn-backup/nas-pull.sh"
test -f "$NAS_BASE/tools/radio-vpn-backup/scripts/retention.py"
read -r -p 'IPv4 publique ou nom DNS public du VPS : ' VPS_HOST
read -r -p 'Port SSH utilisé pour ce VPS [22] : ' VPS_PORT
VPS_PORT=${VPS_PORT:-22}
ssh-keyscan -T 10 -p "$VPS_PORT" -t ed25519 "$VPS_HOST" > "$NAS_BASE/keys/vps1-host.pending"
ssh-keygen -lf "$NAS_BASE/keys/vps1-host.pending"
```

**Comparer les deux empreintes d'hôte avant de continuer.** `ssh-keyscan` collecte une clé,
mais ne prouve pas son authenticité. Si elles diffèrent, arrêter et vérifier l'adresse.
Après confirmation visuelle seulement, **NAS — `vpnbackup`** :

```bash
cat "$NAS_BASE/keys/vps1-host.pending" >> "$NAS_BASE/keys/known_hosts"
chmod 600 "$NAS_BASE/keys/known_hosts"
ssh -T -p "$VPS_PORT" -i "$NAS_BASE/keys/vps1_ed25519" \
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$NAS_BASE/keys/known_hosts" "radio-vpn-backup@$VPS_HOST" list
```

Résultat attendu : les identifiants disponibles, sans demande de mot de passe. Ce compte
ne peut pas servir à une session `ssh` ordinaire, à `scp` ou à un explorateur SFTP.
Ne pas désactiver la vérification des clés d'hôte pour contourner une erreur.

## 9. Créer la configuration NAS et faire un transfert manuel

**NAS — `vpnbackup`, même session ayant défini `VPS_HOST` et `VPS_PORT` :**

```bash
CFG="$NAS_BASE/config/vps1.conf"
printf 'VPS_NAME=%q\nHOST=%q\nPORT=%q\nSSH_KEY=%q\nKNOWN_HOSTS=%q\nDESTINATION=%q\nDAILY=7\nWEEKLY=4\n' \
  vps1 "$VPS_HOST" "$VPS_PORT" "$NAS_BASE/keys/vps1_ed25519" \
  "$NAS_BASE/keys/known_hosts" "$NAS_BASE/archives" > "$CFG"
chmod 600 "$CFG"
bash "$NAS_BASE/tools/radio-vpn-backup/nas-pull.sh" "$CFG"
ls -l "$NAS_BASE/archives/vps1"
```

`%q` protège les valeurs et chemins dans ce fichier lu par Bash. `VPS_NAME` nomme le
sous-dossier local ; `HOST`/`PORT` désignent le VPS ; `SSH_KEY` est la clé privée NAS ;
`KNOWN_HOSTS` contient la clé d'hôte vérifiée ; `DESTINATION` est le dossier de collecte.
`DAILY=7` et `WEEKLY=4` règlent la rétention. Le script récupère et vérifie les archives,
puis les classe dans le vrai dossier `$NAS_BASE/archives/vps1`.

**NAS — même compte :**

```bash
cd "$NAS_BASE/archives/vps1"
for somme in *.sha256; do sha256sum -c "$somme" || break; done
for archive in *.tar.gz; do gzip -t "$archive" || break; done
```

Le premier contrôle doit afficher `OK` pour chaque archive, le second rester silencieux.
Relancer `nas-pull.sh` : il doit vérifier les fichiers déjà présents sans les dupliquer.
Un transfert interrompu ne doit pas laisser de nouvelle archive finale invalide.

## 10. Créer la tâche planifiée DSM

**NAS — `vpnbackup`, après réussite du transfert manuel :** afficher la commande à reporter
dans DSM avec les chemins réels et le PATH qui vient d'être vérifié :

```bash
BASH_BIN=$(command -v bash)
printf 'umask 077\nexport PATH=%q\n%q %q %q >> %q 2>&1\n' \
  "$PATH" "$BASH_BIN" "$NAS_BASE/tools/radio-vpn-backup/nas-pull.sh" \
  "$NAS_BASE/config/vps1.conf" "$NAS_BASE/logs/vps1-pull.log"
```

**Poste d'administration — navigateur DSM, compte administrateur :**

1. **Panneau de configuration > Planificateur de tâches > Créer > Tâche planifiée > Script défini par l'utilisateur**.
2. Nom : `Collecte radio-vpn vps1`. Utilisateur : **`vpnbackup`**, pas root ni l'administrateur.
3. Planification quotidienne après la préparation VPS, avec une marge suffisante.
   Le cron VPS est à **02:17, heure du VPS**. Vérifier `timedatectl` sur le VPS et `date`
   sur le NAS : 03:00 NAS ne convient que si le décalage de fuseaux et la durée le permettent.
4. Dans **Paramètres de tâche > Exécuter la commande**, coller exactement les lignes affichées.
   Le PATH explicite évite de dépendre du profil du terminal interactif.
5. Activer la notification d'exécution anormale si proposée. Configurer auparavant le
   destinataire dans **Panneau de configuration > Notification** et faire un envoi de test.
6. Enregistrer, sélectionner la tâche, puis **Exécuter**. Vérifier son résultat et le journal.

**NAS — `vpnbackup` :**

```bash
tail -n 50 "$NAS_BASE/logs/vps1-pull.log"
ls -lt "$NAS_BASE/archives/vps1"
```

Les notifications ne remplacent pas le contrôle des dates et du contenu du journal.
Si le terminal NAS est fermé, l'administrateur peut le rouvrir avec l'étape 3. Après les
tests, le SSH **entrant du NAS** peut être désactivé dans DSM : la tâche utilise le client
SSH sortant, pas ce service. Ne pas désactiver le SSH du VPS.

## 11. Vérifier l'automatisation et la rétention

**VPS — administrateur, après le prochain horaire de préparation :**

```bash
sudo systemctl is-active cron
sudo cat /etc/cron.d/radio-vpn-backup
sudo journalctl -t radio-vpn-backup --since yesterday --no-pager
sudo find /var/lib/radio-vpn-export -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
sudo systemctl is-active openvpn@server.service openvpn-ui.service radio-renew-crl.timer
```

**DSM — administrateur :** contrôler la dernière exécution automatique et son utilisateur.
**NAS — `vpnbackup` :** consulter le journal de collecte, vérifier l'arrivée d'un nouvel
identifiant et ses SHA-256 comme à l'étape 9. Un essai manuel ne prouve pas que cron et
DSM s'exécutent automatiquement : attendre et vérifier au moins un cycle complet.

Le VPS garde les **3 derniers points** par défaut (réglage `KEEP_VPS`, de 2 à 30).
Le NAS garde un point par jour pour les 7 jours collectés les plus récents et un point par
semaine pour les 4 semaines collectées les plus récentes, en UTC, avec déduplication.
Ce n'est pas nécessairement 11 fichiers. Il faut plusieurs semaines pour observer la
rétention hebdomadaire complète ; une panne de collecte ne recrée pas les points manqués.
Ne pas supprimer des sauvegardes pour simuler ce vieillissement sur vos données réelles.

La prochaine étape est une [restauration de test](validation.md). Voir aussi le
[dépannage](maintenance.md) et le [chiffrement facultatif](encryption.md).

## Références DSM

Les procédures sont décrites ici ; ces références officielles permettent de vérifier
les particularités de votre DSM, dont les menus et paquets varient selon le modèle :

- [Comptes et connexion SSH Synology](https://kb.synology.com/en-us/DSM/tutorial/How_to_login_to_DSM_with_root_permission_via_SSH_Telnet).
- [Planificateur et scripts Synology](https://kb.synology.com/en-af/DSM/tutorial/common_mistake_in_task_scheduler_script).
- [Autorisations et inspecteur ACL](https://kb.synology.com/en-eu/DSM/tutorial/How_to_manage_ACL_settings_on_your_Synology_NAS).
