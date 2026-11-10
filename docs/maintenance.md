# Contrôles et dépannage

Les commandes NAS ci-dessous concernent **le collecteur personnalisé**. Pour ABB, voir
ses [étapes de contrôle et de diagnostic](abb.md). Les commandes VPS de préparation des
archives restent communes aux deux méthodes.

Les variables NAS de ce guide sont redéfinies sous le compte `vpnbackup` :

```bash
cd "$HOME/radio-vpn"
NAS_BASE=$(pwd -P)
CFG="$NAS_BASE/config/vps1.conf"
```

Ce sont les dossiers créés dans le [guide d'installation](installation.md), pas un volume
supposé. Si votre identifiant n'est pas `vps1`, employer celui de votre fichier de configuration.

## Commandes courantes

**VPS — administrateur Linux, sudo :**

```bash
sudo /usr/local/sbin/radio-vpn-backup
sudo journalctl -t radio-vpn-backup --since yesterday --no-pager
sudo systemctl status cron --no-pager
sudo cat /etc/cron.d/radio-vpn-backup
sudo cat /etc/radio-vpn-backup.conf
df -h /var/lib
```

La commande manuelle affiche directement son résultat ; seuls les passages par cron
envoient leurs messages au tag journald `radio-vpn-backup`. Un retour non nul indique
un échec ; vérifier la date de la dernière archive complète, pas seulement sa présence.
Le cron ne définit aucune notification de courriel. La notification de collecte se règle dans DSM.

**NAS — `vpnbackup` :**

```bash
bash "$NAS_BASE/tools/radio-vpn-backup/nas-pull.sh" "$CFG"
tail -n 50 "$NAS_BASE/logs/vps1-pull.log"
ls -lt "$NAS_BASE/archives/vps1"
df -h "$NAS_BASE/archives"
```

L'exécution directe n'écrit pas dans le journal de la tâche, sauf redirection explicite
comme celle générée pour DSM. Vérifier régulièrement la place occupée par ce journal.

## Installation VPS déjà présente ou partielle

Ne pas répéter `install.sh` pour ajouter une deuxième fois le même compte.
**VPS — administrateur :**

```bash
sudo test -x /usr/local/sbin/radio-vpn-backup
getent passwd radio-vpn-backup
sudo ls -l /etc/radio-vpn-backup.conf /etc/cron.d/radio-vpn-backup
sudo ls -l /usr/local/lib/radio-vpn-backup
```

Si ces éléments existent et que la sauvegarde manuelle fonctionne, reprendre à la première
sauvegarde ou à la collecte NAS. Si certains manquent, conserver les messages d'erreur et
faire diagnostiquer l'installation. L'outil n'a pas de mode de réparation ou de réinstallation
automatique ; ne pas supprimer le compte, les archives ou la PKI pour contourner son refus.

## Erreur SSH ou demande de mot de passe

Le client NAS doit employer le compte **VPS** `radio-vpn-backup`, la clé privée **NAS**
créée sous `vpnbackup`, et le bon port. `BatchMode=yes` interdit toute question de mot de passe.
Reprendre le test `ssh ... list` du guide d'installation. Sur le VPS, vérifier la présence
de la clé publique et les restrictions SSH éventuelles, sans élargir les droits :

```bash
sudo ssh-keygen -lf /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
sudo ls -ld /var/lib/radio-vpn-backup-user /var/lib/radio-vpn-backup-user/.ssh
sudo ls -l /var/lib/radio-vpn-backup-user/.ssh/authorized_keys
sudo /usr/sbin/sshd -t
sudo journalctl -u ssh -n 50 --no-pager
```

Une erreur de clé d'hôte doit être vérifiée depuis la console du VPS ou une connexion
administrateur fiable. Après remplacement d'un VPS, contrôler sa nouvelle empreinte avant
de mettre à jour `known_hosts` ; ne pas désactiver `StrictHostKeyChecking`.

## La tâche manuelle marche, mais pas DSM

Dans DSM, vérifier l'utilisateur **`vpnbackup`**, la commande, les chemins absolus et le
PATH obtenus lors de l'installation. Le planificateur ne reprend pas nécessairement le
profil de votre terminal. Vérifier que Python3 reste disponible après une mise à jour DSM.
Dans l'inspecteur de permissions, contrôler l'accès effectif au script, à la clé, au fichier
de configuration et aux dossiers de destination. Ne pas résoudre ce problème en passant
la tâche en root ou en ajoutant `vpnbackup` aux administrateurs.

## Verrou après interruption ou contrôles d'intégrité en échec

- Un fichier caché `.partial` n'est pas une sauvegarde validée. Une interruption normale
  le nettoie ; un arrêt brutal peut le laisser. Relancer la collecte pour un nouvel essai.
- Si `.pull.lock` reste présent, vérifier dans DSM qu'aucune tâche ne tourne et qu'aucun
  essai manuel n'est actif avant d'enlever **ce seul dossier vide** avec `rmdir`.
- SHA-256 invalide : conserver les anciennes sauvegardes ; ne pas ignorer le contrôle.
- PKI/CCD/CRL/SQLite incohérents : vérifier les données et l'absence d'administration
  concurrente. Ne jamais effacer `index.txt` ou régénérer la CA pour faire passer le contrôle.
- Après une panne ou un SIGKILL pendant la copie, contrôler sur le VPS :

```bash
sudo systemctl is-active openvpn@server.service openvpn-ui.service radio-renew-crl.timer
```

Les erreurs interceptables tentent de rétablir l'UI et le timer initialement actifs ; une
coupure électrique ne peut pas être traitée par le script. Garder un accès console disponible.

## Limites à connaître

Le VPS conserve `KEEP_VPS` points même si le NAS ne collecte plus : les points intermédiaires
finissent donc par disparaître lors d'une longue panne NAS. La rétention NAS se construit
au fil des collectes et ne peut pas récupérer des semaines jamais collectées.
La sauvegarde ne couvre pas l'OS complet, les mots de passe Linux ou les clés SSH d'hôte.
Les ACL personnalisées et les chemins hors contrat demandent une analyse distincte.
La cohérence suppose une fenêtre sans opérations PKI manuelles ; l’installation ne fournit
pas de transaction globale entre SQLite, PKI et CCD. Tester la restauration régulièrement.
