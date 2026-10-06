# Canaux, confidentialité et livraison — étape 4

Contrats codés le 2026-10-06. La qualification locale et la préparation AWS sont distinctes de l'exécution distante. [Rapport](verification/stage4.md), [manifestes et preuves](verification/artifact-evidence.json), [journal](../JOURNAL.md), entrée JRN-021.

## Domaine commun et autorité

`channel_tools.py` expose exactement huit outils : `get_daily_context`, `recall_memories`, `get_task_status`, `submit_goal`, `amend_goal`, `pause_goal`, `resume_goal`, `cancel_goal`. Les schémas Pydantic refusent les champs supplémentaires. Les trois lectures sont disponibles en mode partagé dans la seule visibilité autorisée ; les mutations exigent le mode personnel. Aucun outil ne crée une permission, une approbation, un budget ou un compte.

MCP et voix réutilisent `Goals`, `Memory`, les transactions, les clés d'intention et l'idempotence de l'API. Les lectures rechargent les sources et conditionnent leurs révisions et droits. Le contexte comporte les souvenirs bornés, au plus deux agendas et six engagements visibles ; les limites sont signalées par `truncated`/`dailySourcesTruncated`. Le lecteur Google vérifie les droits fournisseur avant de rendre son snapshot. Dans AWS, les canaux invoquent le lecteur Lambda existant au moyen d'une délégation opaque ; ils n'accèdent ni à `Connections`, ni au déchiffrement OAuth. Les agendas personnels sont absents du mode partagé.

Une délégation `CHANNELGRANT` expire après 30 secondes et lie acteur, foyer, mode, outils, générations de profil/appartenance/confidentialité et éventuellement session vocale. Seule son empreinte est stockée. Expiration et révocation sont logiques, indépendantes du nettoyage TTL. Les paramètres d'outil ne choisissent jamais l'identité. La voix appelle directement la même bibliothèque de domaine ; elle ne fait pas un second aller-retour MCP interne pour chaque outil, simplification assumée du schéma proposé dans le TDD.

## MCP Streamable HTTP

`POST /mcp` utilise le SDK MCP Python 1.30.0 et le protocole **2025-11-25**. Une autre version est refusée ; aucune négociation silencieuse. Réponses JSON, transport stateless, pas de session MCP durable : le travail et l'idempotence sont dans le domaine. `GET` et `DELETE` répondent 405. Une requête contient un seul objet JSON-RPC de 32 Ko maximum. Le client fournit `Accept: application/json, text/event-stream`, `MCP-Protocol-Version` et `X-Household-Id`.

Le bearer public exige signature, issuer, client, expiration, `token_use=access`, scope `koyori/mcp` et `aud` égal à `KOYORI_MCP_RESOURCE`. Un token REST sans cette portée est refusé. `/.well-known/oauth-protected-resource/mcp` décrit la ressource, et le 401 donne son adresse dans `WWW-Authenticate`. Pour Cognito, demander le scope et `resource=<URL HTTPS exacte /mcp>` dans le flux code/PKCE. Le login et cette liaison restent à qualifier à distance. [Documentation Cognito, consultée le 2026-10-06](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html).

L'API remplace entièrement `_meta.koyori/internal-grant` par sa délégation. Dans AWS elle invoque le runtime MCP sous SigV4 ; le bearer utilisateur n'est pas transmis. Le runtime n'accepte qu'une délégation valide créée par l'API. L'Origin, lorsqu'il est présent, doit appartenir à `KOYORI_ALLOWED_ORIGINS` ; l'URL publique HTTPS et IAM constituent les autres frontières. Les appels non navigateur peuvent omettre Origin. Les erreurs d'outil sont expurgées et ne recopient pas leurs arguments.

Les créations/amendements/contrôles d'objectif portent `idempotencyKey` (32 caractères hexadécimaux). Les contrôles portent `taskId` et `revision`. Les répétitions conservent l'intention ; un corps ou une révision incompatible échoue. Un `submit_goal` signifie acceptation durable, jamais achat ou livraison.

## Admission et WebSocket vocal

`POST /v1/sessions`, avec le bearer REST et le foyer, accepte :

```json
{"schemaVersion":"1.0","mode":"personal","microphoneConsent":true,"locale":"fr-FR"}
```

Le mode par défaut est `shared`. `microphoneConsent=true` est obligatoire ; le client doit recueillir ce choix et obtenir l'autorisation de microphone du navigateur. Le serveur ne déduit pas une identité personnelle d'une voix reconnue. `conversationId` facultatif permet de reprendre la même conversation, pour le même acteur/foyer/mode/génération, avec un nouveau runtime et un nouveau ticket.

La réponse 201 inclut `ticket`, `runtimeSessionId`, `conversationId`, `connectionUrl`, formats et flag `simulation`. Ne pas les journaliser. Ticket opaque à usage unique, expirant à 30 secondes ; bootstrap exigé en cinq secondes. Dans AWS, l'URL est signée par `AgentCoreRuntimeClient.generate_presigned_url`, et son identifiant de transport doit correspondre au bootstrap. Aucun bearer n'est mis dans le WebSocket.

```json
{"type":"session.bootstrap","protocolVersion":"1.0","runtimeSessionId":"UUID-RETOURNE","ticket":"TICKET-RETOURNE","inputFormat":"pcm16-16000-mono"}
```

Entrée et sortie négocient **PCM signé 16 bits little endian, 16 kHz, mono**. Chaque trame binaire commence par huit octets : `uint32 sequence`, `uint32 generation`, little endian, puis 2 à 6 400 octets PCM. Les séquences d'entrée et de sortie sont indépendantes et commencent à zéro. Une interruption incrémente la génération, sans remettre les séquences à zéro ; le client abandonne les anciennes trames et transmet la nouvelle génération. Une trame hors ordre, trop grande, impaire ou accélérée est refusée. File WebSocket limitée à quatre messages par Uvicorn.

Contrôles : `playback.interrupt`, `playback.backpressure` avec `bufferedMs`, `session.heartbeat`, `session.renew`, `session.close`. Un tampon supérieur à deux secondes stoppe la génération audio. Le heartbeat ne prolonge pas l'inactivité métier. Session : 60 secondes d'inactivité, dix minutes maximum, quatre admissions simultanées par foyer et deux par acteur. Chaque admission réserve dix minutes sur un plafond par foyer/jour UTC (3 600 secondes par défaut) ; absence de remboursement, limite volontairement conservatrice. Une URL signée échouée après admission peut aussi consommer cette réservation.

En mode `aws`, `speech.py` ouvre Nova 2 Sonic (`amazon.nova-2-sonic-v1:0`) avec le SDK natif 0.11.0, HTTP/2 CRT obligatoire et credentials de rôle renouvelés par la chaîne boto3. Entrée PCM 16 kHz ; l'audio génératif Nova 24 kHz est supprimé. Le flux se renouvelle à 420 secondes, avant la limite fournisseur, avec un contexte frais. Limites applicatives : 32 appels d'outil, 64 tours, transcription finalisée de 2 000 caractères ; contenu fournisseur et appels d'outil bornés. Un échec termine la session avec un code expurgé ; une reconnexion ne rejoue pas les tours acceptés.

Seul un `contentEnd` de transcription utilisateur finalisée devient un souvenir. Un texte provisoire/interrompu et la sortie du modèle ne deviennent pas une mémoire. La transaction du tour lie son identifiant, son empreinte, la mémoire et, pour la recette simulée, l'objectif. Les reconnexions retrouvent l'objectif par API/MCP ; aucune tâche ne dépend de la présence du socket. Les transcripts personnels sont privés, ceux d'un mode partagé explicitement choisi sont partagés au foyer.

En local, `speech_mode=simulated` accepte `turn.final` avec `turnId`/`text` et ne produit aucun faux PCM vocal. Ce contrôle client est interdit en mode réel. La recette utilise ce chemin pour tester finalisation, idempotence, fermeture et reprise ; elle ne mesure pas la reconnaissance vocale.

## Annonces et interruption

Toute parole générative du modèle est supprimée. Les réponses d'outil sont exposées comme données et parlées à partir de templates contrôlés via Polly (PCM 16 kHz, Lea FR, Joanna EN). Ce compromis privilégie la vérité transactionnelle et limite la conversation libre ; il reste à évaluer sur la voix réelle. Les souvenirs sont introduits comme souvenirs retrouvés, et ne constituent pas des instructions.

Un succès commercial exige un reçu canonique dont le statut correspond à l'action. Les formulations distinguent demande reçue, approbation dans l'espace personnel, résultat inconnu, commande confirmée, annulation fournisseur et livraison encore non attestée. Le seul commerce actuellement codé reste explicitement simulé. Les sources/révisions sont revalidées avant et pendant la diffusion PCM ; une correction, révocation ou suppression coupe l'ancienne lecture. Une trame déjà reçue ne peut pas être retirée du client.

`playback.interrupt` arrête uniquement le son ; aucune action commerciale n'est annulée. Une demande d'annulation passe par `cancel_goal` et le rapprochement du fournisseur. Un « oui » parlé ne consomme aucun grant d'approbation.

## Activité, abonnement et rattrapage

`POST /v1/activity/subscription` fournit endpoint, channel exact `/activity/<foyer>/<acteur>`, délégation d'abonnement de 30 secondes et URL de rattrapage. En local sans AppSync, le transport annoncé est `polling`. L'autorizer Lambda AppSync vérifie les générations actuelles à chaque connexion/abonnement, refuse wildcard, autre personne et publication utilisateur, sans cache d'autorisation. Publication réservée au rôle IAM de maintenance.

La projection du journal durable crée un signal coalescé dans la même transaction que le feed. Son contenu est seulement `activity.available` et le dernier numéro de séquence ; aucun texte ou identifiant d'objet privé. Une connexion déjà abonnée peut conserver un signal de séquence après révocation jusqu'à sa fermeture ; toutes les lectures de contenu appliquent les droits actuels. Le client ne doit pas afficher un signal comme une preuve de succès ou de livraison de notification.

`GET /v1/activity/catchup?after=<sequence>` lit vingt candidats, recontrôle leurs objets canoniques et retourne `nextAfter`/`hasMore`. Une page filtrée vide peut avancer. Conserver le dernier numéro et rattraper après reconnexion, même lorsque tous les signaux ont été perdus. Le feed durable reste la référence ; AppSync n'est pas le stockage d'activité. Les notifications de l'étape 3 conservent leurs permissions et horaires de calme ; aucune parole proactive Alexa+ native n'est ajoutée.

## Export, effacement et restauration

`GET /v1/privacy/export` pagine les données possédées dans ce foyer, avec curseur chiffré lié à la personne : souvenirs, tâches, actions, connexions publiques, routines et apprentissage. Credentials, grants transitoires et données d'autres membres sont exclus. Continuer jusqu'à `nextCursor=null`, y compris sur une page vide ; les souvenirs supprimés ou expirés sont ignorés.

`POST /v1/privacy/memories/erase`, corps `{"schemaVersion":"1.0","confirmation":"erase-my-memories"}`, exige idempotence et preuve fraîche liée à cette opération/corps. Le 202 désigne une intention d'effacement, consultable dans `/v1/privacy/erasures/<id>`. Le worker traite huit candidats par lot et reprend durablement après crash. Le fence bloque les nouvelles écritures et masque immédiatement les souvenirs pendant l'effacement ; la génération de confidentialité invalide définitivement les anciennes admissions/délégations. Les tombstones et intentions de suppression de vecteurs restent conservés. **Portée : souvenirs**, avec leurs références/projections ; les objectifs, textes de demande et preuves commerciales ne sont pas un effacement total du compte. Aucun endpoint ne prétend le contraire.

Une restauration locale nécessite un ledger d'effacement récent exporté de la source arrêtée, de la même origine, dans de nouvelles tables et avec le même nombre de shards. Elle applique les suppressions intervenues après le snapshot, recrée les intentions de retrait des vecteurs, retire approvals/tickets/sessions/délégations et credentials OAuth, désactive les connexions et conserve l'idempotence métier. `RESTORE_FENCE` interdit les mutations et workers avant tout lot de restauration ; la cible partielle reste hors ligne. L'outil est réservé aux fixtures locales ; PITR AWS exige une recette séparée. [Procédure et rotation](operations.md).

Le ledger refuse toute demande d'effacement encore `ERASING` : terminer ses lots dans la source avant de générer la preuve actuelle. Une demande acceptée avant le premier lot ne peut ainsi être oubliée lors de la récupération d'un snapshot antérieur. Les conditions de divulgation des souvenirs gardent aussi le fence de leur propriétaire, même si le lecteur est un autre membre et même si ce fence était absent.

## Artefacts et qualification distante

Le builder hôte installe les roues verrouillées pour la plateforme cible, sans exécuter de shell ARM64 sur l'hôte AMD64. La CI construit les deux variantes et contrôle les imports AMD64 ; l'exécution native ARM64 reste un contrôle distinct avant déploiement.

`Dockerfile.runtime` prépare une image non root, verrouillée, avec factory vocal sur `0.0.0.0:8080/ws` et `/ping`, ou MCP sur `0.0.0.0:8000/mcp`. AgentCore exige ARM64 : construire et tester cette architecture avant publication ECR. Les paramètres CDK imposent un digest immuable, sans valeur par défaut. API, runtimes, lecteur Google, projection et maintenance conservent leurs rôles séparés. AppSync utilise uniquement IAM et Lambda, sans API key. [Contrats AWS et ports, consultés le 2026-10-06](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html).

`scripts/prepare_release.py` produit [deployment-manifest.json](verification/deployment-manifest.json), lie lock, sources, image locale, bundle Lambda et template, et vérifie les contrats de rollback. Son état `PREPARED_NOT_DEPLOYED` ne qualifie pas l'architecture ARM64 ni AWS. `--previous` interdit une modification silencieuse du sens d'approbation, de l'intention commerciale ou des versions. Un rollback conserve les données courantes et ne défait aucun effet fournisseur.

`scripts/qualify_channels.py --live` est un **précontrôle de credentials**, sans appel de modèle et sans validation automatique distante ; il produit `NOT_RUN` et les preuves encore requises. Pour qualifier réellement : login Cognito/PKCE et refus OAuth, déploiement ARM64 et IAM refusés, PCM Nova finalisé FR/EN et renouvellement, Polly/interruption, AppSync/perte/rattrapage, puis les trois parcours du concept avec Google réel et commerce simulé. Répéter crash, refus, concurrence et restauration sur fixtures synthétiques ; mesurer p50/p95 du client vocal, mémoire sourcée, appels, unités facturées et facture observée. Ne jamais assimiler latence localhost et latence vocale distante.

La proposition Open Source complémentaire est préparée dans [contribution indépendante](../contributions/mcp-authority-boundary/README.md). Elle n'est ni publiée ni soumise ni fusionnée. Le dossier [AWS Builder/Open Source](verification/hackathon-stage4.md) reste fondé sur les observations, sans inventer de coûts ou d'accès Alexa+.
