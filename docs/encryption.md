# Chiffrement facultatif avec age

[Accueil sauvegarde](../README.md) · [Installer sur le VPS](vps-installation.md) · [Collecte ABB](abb.md) · [Collecteur personnalisé](installation.md)

Le mode standard du [guide d’installation VPS](vps-installation.md) ne nécessite pas `age`.
Ce guide décrit la préparation du mode chiffré ; la collecte NAS utilise les mêmes mécanismes.
La clé SSH de collecte et la clé age sont **deux paires différentes**, avec des rôles différents.

## 1. Générer la clé hors du VPS

**Poste de confiance Debian/Ubuntu — utilisateur habituel**, ou autre poste disposant d'age :

```bash
sudo apt update
sudo apt install -y age
umask 077
mkdir -p "$HOME/radio-vpn-recovery"
chmod 700 "$HOME/radio-vpn-recovery"
cd "$HOME/radio-vpn-recovery"
age-keygen -o radio-vpn-recovery.key
age-keygen -y radio-vpn-recovery.key > radio-vpn-recipient.txt
cat radio-vpn-recipient.txt
```

Ne pas écraser une clé existante. `radio-vpn-recovery.key` est la clé **privée**, à garder
dans un coffre et sur un second support indépendant, hors du VPS sauvegardé. Sa perte
rend les archives chiffrées inutilisables. `radio-vpn-recipient.txt` contient uniquement
le destinataire **public** `age1...`, à transmettre au VPS. Sur un poste d'un autre OS,
utiliser l'outil age déjà installé ; les trois commandes `age-keygen`/`cat` ont le même rôle.
La procédure standard reste disponible si votre poste ne dispose pas de cet outil.

## 2. Préparer le chiffrement sur le VPS

**VPS — administrateur Linux, session Bash :** installer age uniquement si vous souhaitez
chiffrer, puis copier le destinataire public créé sur le poste de confiance. Ne jamais
copier la clé privée sur le VPS sauvegardé.

```bash
sudo apt update
sudo apt install -y age
read -r -p 'Coller le destinataire PUBLIC age1... : ' AGE_RECIPIENT
printf '%s\n' "$AGE_RECIPIENT" > "$HOME/radio-vpn-recipient.txt"
sudo install -m 600 "$HOME/radio-vpn-recipient.txt" /etc/radio-vpn-backup.recipients
```

### Sauvegarde manuelle : choix pour une seule exécution

**VPS — même administrateur, dans un terminal :**

```bash
sudo /usr/local/sbin/radio-vpn-backup
```

À « Voulez-vous chiffrer la sauvegarde avec age ? [o/N] », répondre `o` pour chiffrer.
Entrée ou `n` produit une archive classique, même si `ENCRYPT=true` est configuré pour cron.
La configuration n’est jamais modifiée par cette réponse.

Le fichier `RECIPIENTS` configuré, ou `/etc/radio-vpn-backup.recipients` par défaut, est
réutilisé sans redemander son chemin s’il est déjà présent et non vide. Sinon, donner
le chemin réel du fichier de destinataires **publics** préparé ci-dessus. Le script ne
demande pas de clé privée et n’en génère pas. Il refuse le chiffrement si age ou le
fichier requis manque, sans revenir silencieusement à une archive non chiffrée.

### Sauvegarde automatique : configuration uniquement

Le cron, à l’heure choisie pendant l’installation (**02:17 par défaut**, heure du VPS),
n’a pas de terminal en entrée et ne pose jamais de
question. Il utilise seulement `/etc/radio-vpn-backup.conf`. Pour chiffrer ces exécutions :

```bash
sudoedit /etc/radio-vpn-backup.conf
```

Conserver `KEEP_VPS` et définir :

```bash
ENCRYPT=true
RECIPIENTS=/etc/radio-vpn-backup.recipients
```

Pour rester sans chiffrement, conserver `ENCRYPT=false` (valeur par défaut). Tout autre
lancement sans terminal en entrée suit également cette configuration. Une dépendance
manquante provoque un échec explicite, jamais une attente de saisie.

Le résultat chiffré est `backup.tar.gz.age` dans le répertoire daté d’export. Vérifier
`SHA256SUMS` comme en mode standard ; ne pas lancer `gzip -t` directement sur un `.age`.

## 3. Collecte et restauration

**NAS — opérateur ABB, ou compte du collecteur personnalisé :** la tâche de collecte
récupère les deux formats et leurs SHA-256, sans age ni clé privée de déchiffrement.
La rétention de la méthode choisie s’applique également aux archives chiffrées.
La vérification SHA-256 porte sur le fichier chiffré ; elle ne prouve pas qu'une clé de
secours est disponible. Conserver la clé originale accessible indépendamment du VPS et du VPN.

Pour une restauration chiffrée, le [guide radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/encryption.md)
explique où copier temporairement la clé privée et quand le script la demande.
Les copies de travail de sauvegarde et de restauration existent en clair dans des dossiers
root privés avant nettoyage. Ne pas considérer le chiffrement comme une protection contre
un VPS source compromis. Conserver plusieurs générations et la clé originale hors VPS.
