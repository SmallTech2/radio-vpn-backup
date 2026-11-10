# radio-vpn-backup

Sauvegarde d'un VPS Debian 13 AMD64 installé avec
[radio-vpn](https://github.com/SmallTech2/radio-vpn).
La compatibilité dépend des [composants présents](docs/format.md#compatibilité),
pas du numéro de version. La version d’origine est conservée dans la sauvegarde.
Le VPS prépare une archive chaque jour par cron ; le Synology la récupère par SSH.
L’installation demande l’heure au format `HH:MM` (défaut **02:17**, heure locale du VPS)
et l’inscrit dans `/etc/cron.d/radio-vpn-backup`.
**Le VPS ne contacte jamais le NAS.** Le même compte Linux `radio-vpn-backup` sert aux
deux méthodes de collecte ; il ne reçoit ni sudo ni shell libre.

## Commencer

Choisir une méthode et suivre son guide, sans mélanger leurs tâches ni leurs rétentions :

1. **Principale : [Active Backup for Business](docs/abb.md)**, serveur de fichiers rsync
   **module via SSH**. ABB gère la collecte, le stockage des versions et la rétention NAS.
2. **Alternative : [collecteur personnalisé](docs/installation.md)** pour les NAS sans ABB,
   avec compte DSM dédié et tâche du planificateur.

La commande forcée expose uniquement le module **archives**, en lecture seule, à travers
SSH. Aucun service rsync permanent ni port 873 n'est nécessaire. Le mode shell avec
`--protect-args` n'est pas compatible avec `rrsync` : sélectionner **module via SSH**.
Les tests SSH/rsync ne remplacent pas une collecte réelle réussie dans votre ABB.

Le compte DSM `vpn-backup` et le partage `VPN-Backup` ne sont pas des prérequis ABB :
ABB gère ses propres tâches et sa destination. Le compte **VPS** reste `radio-vpn-backup`.

## Données et modes

PKI complète, certificats, révocations, IP fixes, profils clients, base SQLite et ressources
UI, scripts et configurations du projet sont inclus. Voir la [liste exacte](docs/format.md).
La copie suspend brièvement l'UI, mais ne redémarre pas OpenVPN ni ses clients.

- **Lancement manuel dans un terminal :** « Voulez-vous chiffrer la sauvegarde avec age ? [o/N] ».
  Entrée ou `n` produit une `.tar.gz` sans age. `o` utilise les destinataires publics configurés
  ou demande le chemin de leur fichier s’il manque. Ce choix ne modifie pas la configuration.
- **Cron quotidien, sans interaction :** `ENCRYPT=false` produit une `.tar.gz` ; `ENCRYPT=true`
  produit une `.tar.gz.age` avec les destinataires configurés. Aucune question n’est posée.

Le [guide de chiffrement facultatif](docs/encryption.md) explique la préparation des clés.
Age n’est nécessaire que pour une exécution chiffrée. Tout lancement sans terminal en
entrée utilise la configuration, comme cron.

**Les archives non chiffrées contiennent notamment la clé privée de la CA et les clés
clients. Ce choix est volontaire et son risque est accepté.** Limiter l'accès aux fichiers
et aux dossiers ; ne jamais publier les sauvegardes. SHA-256 contrôle l'intégrité, pas
l'identité de leur auteur.

## Guides

- [Active Backup for Business : installation et validation](docs/abb.md).
- [Alternative : première installation et automatisation personnalisée](docs/installation.md).
- [Contrôles courants et dépannage](docs/maintenance.md).
- [Chiffrement facultatif](docs/encryption.md).
- [Contenu et format d'archive](docs/format.md).
- [Recette réelle de sauvegarde/restauration](docs/validation.md).
- [Restaurer sur un VPS de remplacement](https://github.com/SmallTech2/radio-vpn-restore).

Les tests automatisés ne remplacent pas une recette sur VPS et DSM. Ne lancer aucune
opération PKI manuelle pendant la copie ; une ancienne archive ne contient pas les
créations ou révocations postérieures. Aucune Release des outils n'est publiée.

## Licence

[MIT](LICENSE). Outil compagnon de Radio Bonheur pour radio-vpn, dérivé de
[d3vilh/openvpn-ui](https://github.com/d3vilh/openvpn-ui), avec les attributions conservées.
