# Recette réelle de sauvegarde

Appliquer d'abord le [guide d'installation](installation.md). Cette recette se fait sur
des machines de test ; ne pas simuler des pannes ou des révocations sur vos clients métiers.

## NAS Synology : éléments à valider sur votre DSM

1. Le compte local `vpnbackup` est non administrateur et accède seulement à son dossier personnel.
2. La clé est créée sous ce compte, puis l'administrateur quitte sa session de préparation.
3. Le test manuel `ssh ... list` et la collecte fonctionnent sous ce compte, sans mot de passe.
4. La tâche DSM choisit exactement ce compte, avec le PATH réel de Bash/Python.
5. Les ACL effectives interdisent l'accès d'un autre utilisateur aux clés et archives.
6. Après un transfert interrompu, aucune nouvelle archive finale invalide n'apparaît.
7. Une tâche en échec provoque la notification configurée et laisse les archives précédentes intactes.
8. La prochaine exécution automatique de cron produit un nouveau point, puis DSM le collecte.
9. Les SHA-256 passent ; la rétention quotidienne puis hebdomadaire s'observe au fil des semaines.
10. Après une mise à jour/redémarrage du NAS, le PATH, les paquets, droits et tâches restent fonctionnels.

Un test depuis le terminal d'un administrateur NAS ne valide pas l'exécution sous `vpnbackup`.

## VPS et restauration complète

Avant la sauvegarde, relever l'empreinte CA, la série/empreinte d'un client de test et son
IP fixe. Utiliser un second client de test déjà révoqué. Pendant la sauvegarde, le premier
doit rester connecté : l'UI peut être suspendue, OpenVPN ne doit pas redémarrer.

Suivre ensuite le [guide complet de restauration](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/restoration.md)
et sa [check-list](https://github.com/SmallTech2/radio-vpn-restore/blob/main/docs/validation.md) :
ancien certificat et IP fixe conservés, certificat révoqué refusé, création d'un nouveau
client et contrôles après redémarrage. Ne pas faire fonctionner deux CA identiques avec
des historiques d'émission divergents ; maintenir le serveur source hors service après bascule.

Tester séparément le [mode age](encryption.md), le refus d'une mauvaise clé et une collecte
mixte. Le mode standard doit fonctionner sans age et sans demande de clé.

Ces validations VPS/DSM ne sont pas déclarées réalisées par les tests automatisés.
