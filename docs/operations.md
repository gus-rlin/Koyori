# Exploitation et récupération du socle

Procédure locale et préparation AWS, actualisée le 2026-10-06. Les commandes administratives de sauvegarde ne sont pas exposées à un membre, un modèle ou un connecteur.

## Services et limites

L'API accepte une commande seulement après sa transaction durable, qui inclut l'intention de run. `publisher` publie l'outbox ; `workflow` reçoit les wakes et exécute des tentatives finies ; `activity` projette les événements ; `repair` traite les intentions prêtes et les baux expirés, même si la file a perdu un message. Les workers n'ont ni clé privée d'identité ni access token utilisateur.

Le bail vaut trente secondes. Un worker relit propriétaire, politique et génération d'accès avant chaque checkpoint, puis écrit avec conditions de révision, propriétaire du bail et génération de run. Une pause ou annulation clôt l'autorité du worker précédent. Un wake reçu pendant le run incrémente une séquence durable ; la libération crée le run suivant quand nécessaire.

Les sweeps inspectent un lot borné par shard, rechargent les lignes canoniques et répartissent leur budget entre les shards. Les records pending n'ont pas de TTL. Un acquittement suit la transaction inbox/transition. Après crash de publication, un envoi peut être répété ; la duplication est traitée par le consommateur. Un réveil de plus de quatorze jours réconcilie seulement l'intention canonique avec l'outcome `CANONICAL_RECONCILED`, sans incrémenter `wakeSeq`, reprendre un bail valide ou réouvrir une tâche suspendue ou terminale. Les autres événements anciens sont ignorés. Un major inconnu échoue et peut finir dans la DLQ.

En local, ElasticMQ persiste les messages dans un volume. Dans AWS, SQS et EventBridge restent des livraisons au moins une fois. Chaque file possède une DLQ après cinq réceptions infructueuses. Corriger la cause avant rejeu ; ne pas fabriquer un succès ou une nouvelle commande à partir d'un message en échec. Les logs exposent classe d'erreur et identifiant de requête, jamais bearer, corps privé ou réponse fournisseur.

Le plafond du socle est de 32 tâches actives et huit membres par foyer, huit foyers par principal. AWS ajoute une concurrence réservée de quatre par Lambda, une concurrence de deux par source SQS, un timeout de trente secondes et une limite d'ingress. Les alarmes portent sur erreurs, throttles, âge de file et DLQ. Aucune notification à une personne n'est configurée ou envoyée ; raccorder un canal opérationnel lors d'un déploiement autorisé.

## Sauvegarde locale hors ligne

Les volumes conservent le stockage, les files et les clés après `docker compose down`. Ne pas utiliser `down -v` pour un simple redémarrage. Un export JSON contient les données et grants du socle : garder le répertoire ignoré `.local`, des permissions privées et un stockage protégé.

1. Bloquer les nouvelles admissions et terminer les jobs d'effacement déjà acceptés avec le worker `channels`. Vérifier leur état `COMPLETED`, puis arrêter tous les writers : `docker compose stop api voice channels publisher workflow activity repair connector projection coordinator scheduler notifications`, et les processus hôte éventuels. Si la source arrêtée contient un fence `ERASING`, le ledger refuse de se créer : conserver la source et reprendre uniquement son effacement avant de recommencer cette procédure.
2. Exporter dans un fichier nouveau : `uv run python -m koyori.backup export .local/snapshot.json --writers-stopped`.
3. Au moment de la récupération, exporter le ledger actuel de la source arrêtée : `uv run python -m koyori.backup ledger .local/current-erasure.json --writers-stopped`. Il doit inclure les suppressions postérieures au snapshot ; un ledger historique ne prouve pas les suppressions courantes. Restaurer dans un préfixe neuf avec le même nombre de shards : `uv run python -m koyori.backup restore .local/snapshot.json --writers-stopped --target-prefix KoyoriRestoreTrial --erasure-ledger .local/current-erasure.json`.
4. Vérifier empreinte, compteurs, versions, suppressions et obligations commerciales. Les anciennes sessions/approbations et credentials sont retirés, les connexions désactivées et la cible porte `RESTORE_FENCE`. Inspecter aussi les révocations d'appartenance/politiques depuis le snapshot ; le ledger porte seulement sur les souvenirs. Les clés d'identité/curseur sont des volumes distincts, à protéger séparément.
5. Faire l'essai de reprise uniquement sur les données synthétiques isolées. Ne pas raccorder un fournisseur ni modifier le préfixe de l'environnement actif sans un contrôle explicite de la récupération.
6. Redémarrer les services d'origine : `docker compose start api voice channels publisher workflow activity repair connector projection coordinator scheduler notifications`.

Le flag `--writers-stopped` confirme l'application de la procédure ; il ne détecte pas les processus de l'hôte. Le script refuse un fichier existant, un snapshot altéré, un préfixe d'origine ou un namespace cible déjà présent. La restauration n'est pas atomique entre plusieurs lots : une interruption laisse un namespace partiel hors ligne. Aucun mécanisme ne l'active automatiquement ; reprendre avec une nouvelle cible après inspection. Le test d'intégration couvre la restauration complète et la reprise d'une tâche au premier checkpoint.

## Préparation AWS et critères avant déploiement

Construire le bundle Linux, définir `KOYORI_STAGE=dev|prod` et un `KOYORI_CALLBACK_URL` HTTPS exact, puis synthétiser CDK. Les templates versionnés préparent les services ; le répertoire `cdk.out` est généré et ignoré. Le bundle et l'image ont des empreintes ; les clés synthétiques sont interdites en `dev/prod`.

Avant un déploiement autorisé, qualifier sur un compte isolé : transactions et conflits concurrentiels, permissions de chaque rôle, login Cognito code/PKCE et preuve fraîche avec nonce, accès refusés, duplication du bus, messages SQS et DLQ, alarmes, retries et limites. Mesurer les coûts et noter les ressources réellement actives. Ces vérifications distantes ne sont pas effectuées pendant la livraison locale.

Les tables ont chiffrement géré AWS, PITR, protection contre suppression, conservation et sauvegarde quotidienne de 35 jours. Une restauration AWS doit viser des tables neuves et rester en quarantaine. Arrêter les writers avant la recette de sauvegarde cohérente du socle ; des backups de tables prises séparément ne prouvent pas un snapshot transactionnel entre tables. Comparer commandes, idempotence, quotas, versions, inbox, outbox et intentions avant remise en service. Appliquer les révocations intervenues depuis la sauvegarde ; ne pas rétablir des droits simplement parce qu'une ancienne ligne est présente.

L'étape 4 qualifie les suppressions et le fence de restauration localement. PITR AWS et rapprochement d'un fournisseur réel restent à exécuter à distance. Un rollback du code ne prétend pas annuler un effet externe. Aucun effet externe n'est possible avec `synthetic.checkpoint`.

## Arrêter sans effacer

`docker compose down` arrête les conteneurs de Koyori et conserve leurs volumes. Le sous-réseau et les ports sont propres au projet. Les tests d'intégration créent et suppriment uniquement leurs namespaces temporaires et files `test-*` ; ils n'utilisent pas les tables de la démonstration.

## Complément étape 2

Ajouter les services `connector` et `projection` à tout arrêt des writers et à toute reprise. La quatrième table `Connections` contient des enveloppes chiffrées ; sauvegarder séparément et confidentiellement la clé locale du volume `provider-key` pour pouvoir relire un export. Les exports anciens à trois tables restent restaurables, mais ne contiennent aucune connexion de cette étape. Les tombstones de mémoire sont restaurés ; avant ouverture d'une sauvegarde antérieure, appliquer les effacements plus récents et rapprocher actions/réservations. Une restauration ne doit pas déclencher silencieusement des commandes externes. Voir [configuration, statuts et limites de l'étape 2](stage2.md).

Les rôles du socle gardent leur timeout de 30 secondes ; API et projection disposent de 60 secondes, connecteur de 180 secondes. Les lots et appels restent bornés. Lors d'un futur déploiement progressif, provisionner d'abord les nouvelles ressources et mettre à jour les consommateurs pour les nouveaux types d'événement, puis activer l'API de l'étape 2. Les intentions et enveloppes du socle restent compatibles. Aucun déploiement n'a été réalisé dans cette livraison.

Si le réseau utilise une autorité de certification supplémentaire déjà approuvée sur le poste, fournir un bundle PEM public de confiance au builder, sans désactiver TLS. `KOYORI_BUILD_CA_FILE` monte ce fichier en lecture seule dans le builder Lambda et configure `PIP_CERT`. Pour l'image : `docker build --secret id=trusted_ca,src=CHEMIN_PEM -t koyori-stage1:local .`, puis `docker compose up -d --no-build`. Le secret de build reste hors de l'image finale ; ce fichier ne doit contenir aucune clé privée. La configuration standard sans certificat supplémentaire conserve son comportement.

## Complément étape 3

Arrêter et reprendre aussi `coordinator`, `scheduler` et `notifications` lors de toute sauvegarde ou restauration. La commande complète d'arrêt des writers est `docker compose stop api publisher workflow activity repair connector projection coordinator scheduler notifications`. Les processus hôte doivent être arrêtés séparément. Préserver les intentions `GOALRUN`, `WORKFLOWSTART`, `WAKE`, `WAKEDELETE`, les compteurs de raisonnement et les occurrences ; une restauration ancienne ne constitue pas une permission de recréer un achat.

Le coordinateur possède un bail de 120 secondes et un timeout Lambda de 100 secondes ; les workflows Standard expirent après trois minutes. Le dispatcher doit vérifier l'exécution encore active avant reprise d'un bail. Les modèles n'ont qu'un retry de structuration explicitement borné et les compteurs sont réservés avant chaque requête ; une incertitude fournisseur est traitée par `connector` indépendamment de ces quotas.

Le scheduler répare la création et la suppression des programmes, puis les échéances persistées manquées. Inspecter la règle/version et l'occurrence avant de rejouer un ancien wake. Modifier une règle invalide ses anciens envois ; ne pas rétablir manuellement une vieille génération d'objectif. Une attente d'approbation ou une panne modèle nécessite une nouvelle décision/amendement, pas une boucle de requêtes.

Provisionner les nouveaux rôles, Standard et groupe Scheduler, mettre à jour les consommateurs pour les événements `routine`/`learning`, puis activer l'API de coordination. Le coordinateur n'a ni accès à `Connections`, ni KMS decrypt, ni secret OAuth : il invoque le lecteur d'agenda dédié. Scheduler ne peut passer que son rôle fixe à son service et invoquer la cible fixe. Qualifier ces restrictions dans AWS avant d'activer des données réelles.

`COMPOSE_PROJECT_NAME` et les ports/image configurables isolent les volumes et conteneurs d'une recette. Ne pas utiliser la même image mutable pour remplacer celle d'un autre checkout. Si pip échoue en téléchargement de bundle, `scripts/build_lambda.py --runtime-image IMAGE_VERROUILLEE` utilise uv dans le runtime Linux, avec le même export `uv.lock`, les hash obligatoires et le certificat public de confiance. Cette option a contourné `InvalidChunkLength` observé localement ; la cause réseau/proxy demeure une hypothèse, TLS n'a pas été désactivé.

## Livraison des canaux et retour compatible

Construire les sources relues et les artefacts avec le lock frozen ; appliquer les quatre recettes, tests d'émulateurs, synthèse et audit. `record_evidence.py` lie les empreintes et refuse une suite avec échec/skip ou une recette non PASS. `prepare_release.py --previous MANIFESTE_PRECEDENT` refuse un changement de contrat sans migration. Les manifestes doivent accompagner le code livré.

Pour AgentCore, construire `docker buildx build --platform linux/arm64 -f Dockerfile.runtime -t IMAGE_LOCALE --load .`, tester imports et endpoints, puis publier dans deux repositories ECR `koyori-*` à tags immuables. Relire leurs digests ; les paramètres CloudFormation `VoiceImageDigest` et `McpImageDigest` exigent `REGISTRE/koyori-...@sha256:...`, même compte/région. La publication ECR et le déploiement sont des opérations distinctes, non exécutées ici. Faire la synthèse avec le vrai callback HTTPS, les origines et les secrets, puis inspecter le diff de stack avant livraison. Le backend est configuré en `eu-west-1`, la voix Nova en `eu-north-1` ; la planification US conserve son contrôle de consentement.

Provisionner ressources/rôles, puis activer les canaux. Qualifier Cognito code/PKCE avec audience `/mcp`, runtime IAM, fournisseur read-only, audio FR/EN, Polly, AppSync et les parcours du concept sur fixtures synthétiques. Définir les logs runtime `/aws/bedrock-agentcore/runtimes/<runtime-id>-<endpoint>` avec rétention de quatorze jours après création ; ne pas activer de collecte de payloads privés. La politique runtime limite logs au préfixe du runtime et métriques au namespace AgentCore. [Référence IAM consultée le 2026-10-06](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html).

Si une livraison échoue, arrêter les nouvelles admissions, garder les tâches/reçus courants, remettre les digests et versions précédents **compatibles** et reprendre les réparateurs canoniques. Ne pas restaurer les données pour un simple rollback du code. Une nouvelle cible restaurée reste bloquée ; aucun bouton ni suppression automatique du fence. Avant toute levée administrateur : compléter les lots, appliquer ledger/révocations actuels, relier explicitement les comptes, rapprocher actions `UNKNOWN`/`DISPATCHING` et réservations et vérifier quotas/idempotence. L'activation réelle et PITR nécessitent une recette opérateur distincte.

## Rotation des secrets

Arrêter les admissions et fermer les sessions, conserver l'ancien matériel chiffrant jusqu'à relecture/rotation des données concernées. Une rotation ne donne pas une nouvelle autorité à une tâche.

- **Identité** : Cognito gère ses clés/JWKS ; qualifier une nouvelle clé et refus des anciennes après la fenêtre prévue. Pour l'émetteur synthétique, créer des volumes de clés isolés, redémarrer l'émetteur et les consommateurs avec la nouvelle clé publique, vérifier nouveau token accepté/ancien refusé ; ne pas effacer les volumes métier. En cas de compromission, révoquer aussi les générations de profil/appartenance afin de fermer les délégations déjà acceptées.
- **Curseurs** : changer la version du secret, redémarrer tous les lecteurs qui le chargent et forcer une nouvelle pagination ; les anciens curseurs doivent être refusés. Les identifiants métier et reçus restent inchangés. Les délégations opaques expirent ou sont invalidées par leurs générations, elles ne sont pas dérivées du secret de curseur.
- **Google/local provider-key** : ne pas remplacer la clé puis tenter de lire les anciennes enveloppes. Rechiffrer hors ligne avec ancienne/nouvelle clé, vérifier toutes les enveloppes, puis permuter de manière atomique ; à défaut, révoquer et relier les comptes explicitement. Sur AWS, la rotation KMS conserve les anciennes versions nécessaires au déchiffrement ; une nouvelle clé maîtresse exige un rechiffrement vérifié. Qualifier refus IAM hors lecteur et état fournisseur après rotation.
- **Client secret OAuth** : préparer la nouvelle version Secrets Manager, contrôler une autorisation/refresh/révocation sur fixture dédiée, puis retirer l'ancienne selon la fenêtre du fournisseur. Ne pas consigner les valeurs ni les réponses contenant des tokens.

Les contrôles locaux de token/curseur et de générations sont automatisés ; les permutations KMS/Cognito/Google réelles restent non exécutées. Consigner version sans valeur, date, preuves, coût et ressources actives lors de qualification distante.
