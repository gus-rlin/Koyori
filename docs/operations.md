# Exploitation et récupération du socle

Procédure locale et préparation AWS, 2026-10-05. Les commandes administratives de sauvegarde ne sont pas exposées à un membre, un modèle ou un connecteur.

## Services et limites

L'API accepte une commande seulement après sa transaction durable, qui inclut l'intention de run. `publisher` publie l'outbox ; `workflow` reçoit les wakes et exécute des tentatives finies ; `activity` projette les événements ; `repair` traite les intentions prêtes et les baux expirés, même si la file a perdu un message. Les workers n'ont ni clé privée d'identité ni access token utilisateur.

Le bail vaut trente secondes. Un worker relit propriétaire, politique et génération d'accès avant chaque checkpoint, puis écrit avec conditions de révision, propriétaire du bail et génération de run. Une pause ou annulation clôt l'autorité du worker précédent. Un wake reçu pendant le run incrémente une séquence durable ; la libération crée le run suivant quand nécessaire.

Les sweeps inspectent un lot borné par shard, rechargent les lignes canoniques et répartissent leur budget entre les shards. Les records pending n'ont pas de TTL. Un acquittement suit la transaction inbox/transition. Après crash de publication, un envoi peut être répété ; la duplication est traitée par le consommateur. Un réveil de plus de quatorze jours réconcilie seulement l'intention canonique avec l'outcome `CANONICAL_RECONCILED`, sans incrémenter `wakeSeq`, reprendre un bail valide ou réouvrir une tâche suspendue ou terminale. Les autres événements anciens sont ignorés. Un major inconnu échoue et peut finir dans la DLQ.

En local, ElasticMQ persiste les messages dans un volume. Dans AWS, SQS et EventBridge restent des livraisons au moins une fois. Chaque file possède une DLQ après cinq réceptions infructueuses. Corriger la cause avant rejeu ; ne pas fabriquer un succès ou une nouvelle commande à partir d'un message en échec. Les logs exposent classe d'erreur et identifiant de requête, jamais bearer, corps privé ou réponse fournisseur.

Le plafond du socle est de 32 tâches actives et huit membres par foyer, huit foyers par principal. AWS ajoute une concurrence réservée de quatre par Lambda, une concurrence de deux par source SQS, un timeout de trente secondes et une limite d'ingress. Les alarmes portent sur erreurs, throttles, âge de file et DLQ. Aucune notification à une personne n'est configurée ou envoyée ; raccorder un canal opérationnel lors d'un déploiement autorisé.

## Sauvegarde locale hors ligne

Les volumes conservent le stockage, les files et les clés après `docker compose down`. Ne pas utiliser `down -v` pour un simple redémarrage. Un export JSON contient les données et grants du socle : garder le répertoire ignoré `.local`, des permissions privées et un stockage protégé.

1. Arrêter l'API et tous les workers de mutation : `docker compose stop api publisher workflow activity repair`.
2. Exporter dans un fichier nouveau : `uv run python -m koyori.backup export .local/snapshot.json --writers-stopped`.
3. Restaurer dans un préfixe de tables neuf : `uv run python -m koyori.backup restore .local/snapshot.json --writers-stopped --target-prefix KoyoriRestoreTrial`.
4. Vérifier empreinte, counts, versions, grants, autorisations actuelles et intentions de reprise sur les tables restaurées. Les clés d'identité et de curseur sont des volumes distincts : les conserver et les protéger séparément. L'export JSON ne les contient pas.
5. Faire l'essai de reprise uniquement sur les données synthétiques isolées. Ne pas raccorder un fournisseur ni modifier le préfixe de l'environnement actif sans un contrôle explicite de la récupération.
6. Redémarrer les services d'origine : `docker compose start api publisher workflow activity repair`.

Le flag `--writers-stopped` confirme l'application de la procédure ; il ne détecte pas les processus de l'hôte. Le script refuse un fichier existant, un snapshot altéré, un préfixe d'origine ou un namespace cible déjà présent. La restauration n'est pas atomique entre plusieurs lots : une interruption laisse un namespace partiel hors ligne. Aucun mécanisme ne l'active automatiquement ; reprendre avec une nouvelle cible après inspection. Le test d'intégration couvre la restauration complète et la reprise d'une tâche au premier checkpoint.

## Préparation AWS et critères avant déploiement

Construire le bundle Linux, définir `KOYORI_STAGE=dev|prod` et un `KOYORI_CALLBACK_URL` HTTPS exact, puis synthétiser CDK. Les templates versionnés préparent les services ; le répertoire `cdk.out` est généré et ignoré. Le bundle et l'image ont des empreintes ; les clés synthétiques sont interdites en `dev/prod`.

Avant un déploiement autorisé, qualifier sur un compte isolé : transactions et conflits concurrentiels, permissions de chaque rôle, login Cognito code/PKCE et preuve fraîche avec nonce, accès refusés, duplication du bus, messages SQS et DLQ, alarmes, retries et limites. Mesurer les coûts et noter les ressources réellement actives. Ces vérifications distantes ne sont pas effectuées pendant la livraison locale.

Les tables ont chiffrement géré AWS, PITR, protection contre suppression, conservation et sauvegarde quotidienne de 35 jours. Une restauration AWS doit viser des tables neuves et rester en quarantaine. Arrêter les writers avant la recette de sauvegarde cohérente du socle ; des backups de tables prises séparément ne prouvent pas un snapshot transactionnel entre tables. Comparer commandes, idempotence, quotas, versions, inbox, outbox et intentions avant remise en service. Appliquer les révocations intervenues depuis la sauvegarde ; ne pas rétablir des droits simplement parce qu'une ancienne ligne est présente.

La qualification d'une restauration AWS, des suppressions de mémoire et des obligations déjà engagées auprès d'un fournisseur reste à effectuer dans les étapes appropriées. Un rollback du code ne prétend pas annuler un effet externe. Aucun effet externe n'est possible avec `synthetic.checkpoint`.

## Arrêter sans effacer

`docker compose down` arrête les conteneurs de Koyori et conserve leurs volumes. Le sous-réseau et les ports sont propres au projet. Les tests d'intégration créent et suppriment uniquement leurs namespaces temporaires et files `test-*` ; ils n'utilisent pas les tables de la démonstration.
