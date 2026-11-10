# radio-vpn-backup

Sauvegarde d'un VPS Debian 13 AMD64 installé avec
[radio-vpn radio-v2.4](https://github.com/SmallTech2/radio-vpn/tree/radio-v2.4).
Le VPS prépare une archive chaque jour par cron ; un compte dédié sur le Synology
la récupère par SSH. **Le VPS ne contacte jamais le NAS.**

## Commencer

Suivre le [guide de première installation](docs/installation.md), dans l'ordre :

1. Créer le compte non administrateur `vpnbackup` sur le Synology.
2. Générer sa clé SSH **sur le NAS**, sous ce compte ; transmettre seulement la clé publique au VPS.
3. Installer Git et cloner ce dépôt **sur le VPS**, puis installer la sauvegarde avec sudo.
4. Produire et vérifier une première archive, sans chiffrement.
5. Préparer la collecte **sur le NAS**, vérifier la clé d'hôte du VPS et tester le transfert.
6. Créer la tâche DSM sous `vpnbackup`, puis contrôler un cycle automatique complet.

Le guide indique pour chaque commande la machine, le compte et la manière d'obtenir les
chemins réels. Git n'est pas nécessaire sur le NAS : le téléchargement des outils est expliqué.

## Données et modes

PKI complète, certificats, révocations, IP fixes, profils clients, base SQLite et ressources
UI, scripts et configurations du projet sont inclus. Voir la [liste exacte](docs/format.md).
La copie suspend brièvement l'UI, mais ne redémarre pas OpenVPN ni ses clients.

- **Standard :** `ENCRYPT=false`, archive `.tar.gz`, aucune dépendance à `age`.
- **Sécurisé facultatif :** `ENCRYPT=true`, archive `.tar.gz.age` ; suivre le
  [guide séparé](docs/encryption.md), après avoir validé le mode standard.

**Les archives non chiffrées contiennent notamment la clé privée de la CA et les clés
clients. Ce choix est volontaire et son risque est accepté.** Limiter l'accès aux fichiers
et aux dossiers ; ne jamais publier les sauvegardes. SHA-256 contrôle l'intégrité, pas
l'identité de leur auteur.

## Guides

- [Première installation et automatisation VPS/NAS](docs/installation.md).
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
