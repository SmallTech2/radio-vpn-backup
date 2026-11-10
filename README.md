# radio-vpn-backup

Preparation de sauvegardes **au format `.tar.gz` non chiffre par defaut** d'un VPS Debian 13 AMD64 installe avec
[radio-vpn](https://github.com/SmallTech2/radio-vpn), reference **radio-v2.4**.
Le VPS prepare les archives ; le NAS les recupere en SSH. **Le VPS ne contacte jamais le NAS.**

Le chiffrement avec `age` est facultatif et active volontairement ; age n est ni installe
ni requis pour le mode standard.

Code a valider sur un VPS de test avant utilisation comme seule sauvegarde.
Aucune Release n'est publiee. Les tests automatiques ne remplacent pas une restauration reelle.

## Donnees sauvegardees

La [liste exacte et l'analyse de compatibilite](docs/format.md) couvrent la PKI complete,
les cles et certificats, les revocations, les IP fixes, les profils clients et secrets MFA,
la base SQLite UI, le binaire et ses ressources, les scripts et les configurations du projet.
Les permissions, proprietaires numeriques et liens symboliques sont conserves.
`manifest.json` contient les empreintes internes et versions ; `INVENTORY.txt` liste
les fichiers, modes, UID/GID et liens dans l archive.
Les journaux et l'OS complet ne sont pas sauvegardes.

## Confidentialite

**En mode standard, les archives ne sont pas chiffrees.** Elles contiennent des informations sensibles,
notamment la cle privee de la CA OpenVPN et les cles privees des clients. Ce choix est
volontaire et le risque est accepte pour simplifier la restauration d'urgence.
Les stocker dans des dossiers prives, sans partage public ni publication GitHub.
Le compte SSH de sauvegarde peut lire ces secrets dans une archive non chiffree ; limiter sa cle
au NAS autorise. Le transport SSH protege le transfert, pas le fichier stocke sur disque.

## 1. Preparer la cle SSH du NAS

Sur un poste de confiance ou sur le NAS :

```bash
umask 077
ssh-keygen -t ed25519 -f vpn-backup-ed25519
```

Conserver la cle privee sur le NAS, fichier 0600 ; seule la cle publique est transferee
au VPS. Pour une tache automatique, utiliser un agent SSH ou une cle dediee sans phrase
secrete, dont l'acces reste reserve au compte de la tache.

## 2. Installer sur le VPS

Lire les scripts puis recuperer ce depot. Noter le commit utilise (`git rev-parse HEAD`)
et conserver une copie : les outils ne disposent pas encore d'une Release stable.
Par exemple, sur le VPS :

```bash
sudo apt install -y git
git clone https://github.com/SmallTech2/radio-vpn-backup.git
cd radio-vpn-backup
git rev-parse HEAD
```

Transferer **uniquement** la cle SSH publique au VPS, puis depuis ce depot :

```bash
sudo bash install.sh /chemin/vpn-backup-ed25519.pub
sudo radio-vpn-backup
```

L'installation utilise Python 3 standard (SQLite et verification), cron et util-linux. Le compte systeme `radio-vpn-backup` est
reserve a cet outil ; l'installateur refuse de reutiliser un compte existant.
Il ne modifie pas la configuration SSH globale, nftables ou OpenVPN.

`authorized_keys` appartient a root et impose une commande forcee avec `restrict` :
pas de terminal, transfert de ports, agent, X11 ou commande libre. Les seules commandes
sont `list`, `hash IDENTIFIANT` et `get IDENTIFIANT`. Le compte peut lire les archives
**non chiffrees** : leur contenu inclut la PKI. Il n'accede pas directement aux
copies de travail ou aux configurations VPN protegees et ne peut pas les modifier.
Il ne dispose pas de sudo. Les permissions Unix ordinaires des autres fichiers publics
du systeme ne sont pas changees ; la commande forcee ne fournit aucun moyen de les lire.
Si votre SSH utilise `AllowUsers`/`AllowGroups`, autoriser explicitement ce compte sans
retirer l'administrateur, verifier `sshd -t` et tester une nouvelle connexion avant fermeture.
Ne pas ouvrir de port supplementaire : le NAS utilise le port SSH existant.

Configuration root uniquement : `/etc/radio-vpn-backup.conf` :

```bash
KEEP_VPS=3
ENCRYPT=false
```

`KEEP_VPS` conserve entre 2 et 30 archives, independamment du succes des recuperations NAS.
Par defaut le VPS ne garde que les 3 dernieres : une panne NAS prolongee perd les points
intermediaires, mais la derniere sauvegarde preparee reste disponible. Surveiller l'espace disque.
Les repertoires de travail et d'export doivent rester sur le meme systeme de fichiers
pour que leur renommage soit atomique.

### Mode securise facultatif

Avec `ENCRYPT=false` (valeur par defaut), aucun outil ni aucune cle de chiffrement ne
sont demandes. L'archive produite est `backup.tar.gz`.

Pour activer `age`, generer les cles **hors du VPS** sur un poste de confiance disposant
de cet outil :

```bash
umask 077
age-keygen -o radio-vpn-recovery.key
age-keygen -y radio-vpn-recovery.key > radio-vpn-recipient.txt
```

Conserver deux copies independantes de la cle privee `radio-vpn-recovery.key`, dont une
hors ligne. Ne pas la copier sur le VPS sauvegarde. Transferer uniquement le fichier public,
puis sur le VPS :

```bash
sudo apt install -y age
sudo install -m 600 /chemin/radio-vpn-recipient.txt /etc/radio-vpn-backup.recipients
sudoedit /etc/radio-vpn-backup.conf
```

Conserver `KEEP_VPS` et definir :

```bash
ENCRYPT=true
RECIPIENTS=/etc/radio-vpn-backup.recipients
```

L'archive produite est alors `backup.tar.gz.age`. Si l'outil ou le fichier public manque,
la sauvegarde echoue explicitement ; elle ne revient pas silencieusement au mode non chiffre.
Tester une restauration avec la cle de secours. Pour revenir au mode standard, definir
`ENCRYPT=false`. La collecte NAS et la retention acceptent les deux formats sans installer
`age` sur le NAS. Utiliser les scripts VPS et NAS de ce meme depot pour le protocole
`hash`, qui retourne l'empreinte et le nom de fichier attendu.

## 3. Cron et sauvegarde manuelle

`/etc/cron.d/radio-vpn-backup` lance la preparation chaque jour a **02:17, heure du VPS**.
Modifier uniquement ce fichier pour changer l'horaire. Commande manuelle :

```bash
sudo radio-vpn-backup
sudo journalctl -t radio-vpn-backup --since today --no-pager
```

La commande manuelle ecrit sur sa sortie standard ; cron transmet les messages a journald.
Une erreur retourne un code non nul et ne publie aucune nouvelle archive incomplete.
Les messages ne contiennent ni mot de passe ni cle. Une notification d'echec de la tache
NAS doit etre activee dans DSM ; aucune messagerie n'est configuree par cet outil.

La sauvegarde suspend le timer CRL, attend le renouvellement en cours, refuse une
operation Easy-RSA detectee, puis arrete l'UI le temps de copier les donnees. SQLite
est copie via son API de sauvegarde et controle par `integrity_check`. L'index, les
revocations, la CRL, les certificats et les IP fixes sont controles avant publication.
L'UI et le timer initialement actifs sont relances meme sur erreur interceptable.
**OpenVPN n'est ni arrete ni redemarre : les clients connectes restent connectes.**

Ne lancer aucune operation PKI manuelle pendant cette fenetre ; programmer la sauvegarde
hors administration. radio-v2.4 n'offre pas de transaction globale entre SQLite, PKI et
CCD : les controles refusent les incoherences detectees, mais ne constituent pas un verrou
partage avec un administrateur executant directement Easy-RSA. Un SIGKILL ou une panne
pendant la maintenance peut laisser l'UI ou le timer arretes : verifier leur etat.
Declencher une sauvegarde apres les creations/revocations importantes pour limiter la perte
d'etat depuis la derniere archive. Restaurer une archive ancienne peut perdre une revocation recente.

## 4. Recuperation sur Synology

Copier ce depot sur le NAS. Prerequis : Bash, client OpenSSH, `sha256sum`, Python 3
(paquet Python3 DSM si absent).
Copier `nas.conf.example` vers un fichier prive `nas.conf`, puis adapter les chemins,
le nom du VPS, son adresse publique et son port SSH. Utiliser un dossier local par VPS,
sans droits pour les autres utilisateurs DSM : `umask 077`, fichiers 0600, dossiers 0700.

Installer la cle SSH privee dediee au NAS. Ajouter la cle d'hote du VPS a `KNOWN_HOSTS`
**apres comparaison de son empreinte avec celle obtenue depuis une console de confiance**.
Ne pas desactiver `StrictHostKeyChecking` et ne pas faire confiance aveuglement a `ssh-keyscan`.

```bash
bash /volume1/outils/radio-vpn-backup/nas-pull.sh /volume1/outils/vpn-exemple.conf
```

Dans DSM > Panneau de configuration > Planificateur de taches, creer une tache utilisateur
quotidienne executant cette commande, par exemple a 03:00 (tenir compte des fuseaux horaires).
Activer la notification d'echec. Le compte DSM ne doit avoir acces qu'aux dossiers necessaires.
La recuperation passe par l'IP publique SSH : elle fonctionne meme si OpenVPN est arrete.

Le transfert se fait dans un fichier cache `.partial`, verifie son SHA-256, puis le renomme.
Une archive existante est reverifiee. La retention ne s'execute qu'apres un transfert complet
reussi : par defaut **7 points quotidiens et 4 points hebdomadaires**, un point par jour/semaine UTC,
avec deduplication lorsqu'un point appartient aux deux categories. Adapter `DAILY` et `WEEKLY`.
Elle se construit au fil des collectes ; elle ne peut pas recreer des sauvegardes non recuperees.
Les autres fichiers sont ignores. Le verrou `.pull.lock` empeche deux collectes simultanees.

## 5. Verification et restauration

Sur le NAS, dans le dossier du VPS :

```bash
sha256sum -c NOM_ARCHIVE.tar.gz.sha256
# Verifier aussi la structure gzip sans extraire de secrets :
gzip -t NOM_ARCHIVE.tar.gz
# Pour une archive chiffree, utiliser son fichier NOM_ARCHIVE.tar.gz.age.sha256.
```

Le SHA-256 verifie le transfert et les empreintes internes controlent les fichiers
pendant la restauration. Ce n'est pas une signature : utiliser une archive provenant
d'une source de confiance. En mode age, le dechiffrement verifie aussi l'integrite du
contenu chiffre. Tester regulierement la restauration hors production.
Pour reconstruire le serveur, suivre [radio-vpn-restore](https://github.com/SmallTech2/radio-vpn-restore)
et le [plan de recette](docs/validation.md).

## Depannage et limites

- Echec SSH : verifier cle dediee, empreinte d'hote, port et autorisations SSH. Ne jamais utiliser root pour la collecte.
- Echec PKI/SQLite : aucune nouvelle archive n'est publiee ; verifier l'etat UI/CRL et les donnees. Ne pas supprimer l'index.
- Recuperation interrompue : les anciennes archives restent presentes. Relancer ; si `.pull.lock` subsiste apres un arret brutal, verifier qu'aucune tache ne tourne avant de le retirer.
- Verifier les dates des sauvegardes et l'espace disque, pas seulement le code retour du dernier cron.
- La derniere version valide reste disponible si une preparation echoue, mais son anciennete peut augmenter.
- SHA-256 n'est pas une signature. Un VPS compromis peut produire une archive malveillante : conserver plusieurs generations et verifier les restaurations.
- Pas de sauvegarde de l'hebergeur, de reseau OS complet, de cles SSH d'hote ou de comptes/mots de passe Linux.
- Les personnalisations hors chemins du contrat et les versions autres que radio-v2.4 sont refusees ou non prises en charge.

## Licence et controles

Licence [MIT](LICENSE). Outil compagnon de Radio Bonheur pour radio-vpn, derive de
[d3vilh/openvpn-ui](https://github.com/d3vilh/openvpn-ui) ; attributions d'origine conservees.
Tests : `python3 -B -m unittest discover -s tests -v`. La CI Linux teste la PKI jetable,
SQLite, le format, les permissions, les refus de chemins dangereux, les transferts SSH simules
et la retention. Elle ne valide pas les services d'un vrai VPS ou DSM.
