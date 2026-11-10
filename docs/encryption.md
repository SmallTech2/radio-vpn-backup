# Chiffrement facultatif avec age

Le mode standard du [guide d'installation](installation.md) ne nécessite pas `age`.
Suivre ce guide seulement après avoir validé la sauvegarde et la collecte sans chiffrement.
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

## 2. Activer sur le VPS

**VPS — administrateur Linux, session Bash :** coller uniquement la ligne publique affichée
sur le poste de confiance, jamais la clé privée.

```bash
sudo apt update
sudo apt install -y age
read -r -p 'Coller le destinataire PUBLIC age1... : ' AGE_RECIPIENT
printf '%s\n' "$AGE_RECIPIENT" > "$HOME/radio-vpn-recipient.txt"
sudo install -m 600 "$HOME/radio-vpn-recipient.txt" /etc/radio-vpn-backup.recipients
sudoedit /etc/radio-vpn-backup.conf
```

Dans l'éditeur, conserver votre valeur `KEEP_VPS` et définir :

```bash
ENCRYPT=true
RECIPIENTS=/etc/radio-vpn-backup.recipients
```

Enregistrer, fermer, puis **VPS — administrateur** :

```bash
sudo /usr/local/sbin/radio-vpn-backup
```

Le résultat doit être `backup.tar.gz.age` dans le répertoire daté d'export. Vérifier son
`SHA256SUMS` comme pour le mode standard, mais ne pas lancer `gzip -t` directement sur
un `.age`. L'absence d'age ou de destinataire provoque un refus, pas un retour silencieux
au mode non chiffré. Pour revenir au mode standard : `sudoedit` puis `ENCRYPT=false`.

## 3. Collecte et restauration

**NAS — `vpnbackup` :** la même tâche récupère les deux formats et leurs SHA-256, sans age
ni clé privée de déchiffrement. La rétention commune accepte les archives mixtes.
La vérification SHA-256 porte sur le fichier chiffré ; elle ne prouve pas qu'une clé de
secours est disponible. Tester son déchiffrement/restauration sur une machine de test.

Pour une restauration chiffrée, le [guide radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/encryption.md)
explique où copier temporairement la clé privée et quand le script la demande.
Les copies de travail de sauvegarde et de restauration existent en clair dans des dossiers
root privés avant nettoyage. Ne pas considérer le chiffrement comme une protection contre
un VPS source compromis. Conserver plusieurs générations et la clé originale hors VPS.
