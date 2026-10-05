# Étape 2 — mémoire et connecteurs contrôlés

Contrats `schemaVersion=1.0`, 2026-10-05. Cette livraison ajoute des commandes explicites au socle. Planification naturelle, apprentissage inféré, MCP et voix restent aux étapes 3 et 4. [Preuves et limites](verification/stage2.md).

## Mémoire et contexte

`POST /v1/memories` conserve un échange finalisé, une préférence (`key` obligatoire) ou une procédure déclarative (`key` et `steps` obligatoires). Chaque souvenir porte propriétaire, auteur/canal serveur, origine, date, visibilité, validité, révision et époque de confidentialité. L'attribution HTTP actuelle est personnelle ; l'admission de tours d'un appareil vocal partagé appartient à l'étape 4. Les appareils partagés lisent seulement les souvenirs explicitement partagés. Les engagements sont dérivés des tâches/actions canoniques, jamais déclarés comme un texte annonçant un succès.

| Route | Contrat |
| --- | --- |
| `GET /v1/memories` | Chronologie paginée, curseur signé lié au lecteur/foyer ; objets rechargés et autorisés |
| `GET /v1/memories/{id}` | Souvenir courant ; 404 si privé, expiré ou effacé |
| `PATCH /v1/memories/{id}` | Correction de texte/étapes/validité/visibilité ; propriétaire et `If-Match` |
| `DELETE /v1/memories/{id}` | Tombstone, texte/étapes/origine effacés, époque incrémentée ; purge du vecteur asynchrone |
| `POST /v1/context` | `day` (`yesterday` ou date ISO), `key`, `query`, `limit` ≤ 8 et `maxCharacters` ≤ 12 000 |
| `GET /v1/commitments` | États et reçus actuels des tâches/actions accessibles ; pagination |

Mutations : `Idempotency-Key`. Une expansion du partage exige une preuve fraîche liée au corps normalisé via le step-up du socle. Les champs inconnus sont refusés. Une clé de préférence/procédure est unique par propriétaire/type ; sa correction vise l'objet existant. L'origine liée doit être accessible ; une source privée ne devient pas une mémoire partagée. Les reçus d'idempotence ne conservent pas le texte.

« Hier » suit le fuseau du profil s'il est défini, sinon celui du foyer ; deux minuits locaux délimitent aussi les journées de 23/25 heures. Les index chronologiques/journaliers ne conservent que des références. Le contexte relit les sources et rapporte `sourceStatus=absent` lorsque leur accès a disparu. Bornes : 500 références canoniques, 20 candidats vectoriels, 8 souvenirs et nombre de caractères demandé. `truncated` signale une borne ; aucun rappel exhaustif n'est promis. Les recherches par clé relisent aussi les slots canoniques des préférences/procédures.

`KOYORI_SEMANTIC_MODE=simulated|disabled|aws` est choisi côté serveur. Le hash lexical local de 512 dimensions permet de tester les invariants et reste une **simulation**. En AWS : Titan V2 `amazon.titan-embed-text-v2:0`, 512 dimensions normalisées, S3 Vectors cosine `memory-v1`. Les filtres proviennent du contexte serveur ; droits, révision, époque, expiration et suppression sont vérifiés sur chaque candidat.

Le worker `projection` conserve une trace indépendante `MEMWORK` avant chaque écriture/effacement S3. Un effet ancien terminé après une correction/effacement réarme la projection canonique, même si elle était déjà terminée. Après interruption, la trace répare à 120 secondes ; le runtime Lambda de projection est borné à 60 secondes. Les purges sont prioritaires. Les échecs sont différés durablement avec délai croissant de 30 secondes à une heure, pour laisser progresser les autres foyers. Avant chaque requête Bedrock, un quota UTC de 200 tentatives par foyer est réservé atomiquement (`KOYORI_EMBEDDING_DAILY_LIMIT` côté serveur). Les retries automatiques Bedrock sont désactivés ; chaque nouvel essai requiert une nouvelle réservation. Les tentatives échouées comptent, et le quota épuisé reporte les projections au prochain jour UTC ; ce compteur n'est pas une facture.

## Capacités, budgets et actions

`GET /v1/capabilities` décrit `commerce.groceries`, `commerce.meals` (simulateur) et `calendar.read` (Google), avec version, preuve attendue, accès, délais et règles de reprise. Une capacité sans configuration renvoie une indisponibilité explicite. Le commerce réel n'est pas admis. Le client ne choisit ni mode, ni prix, ni propriétaire, ni reçu.

`POST /v1/connections/simulated` crée un compte de recette persistant. `GET /v1/connections[/{id}]` et `DELETE /v1/connections/{id}` lisent/révoquent le compte privé à son propriétaire ; la révocation exige la révision. Elle bloque les nouveaux envois et les actions encore `READY`, tout en conservant le rapprochement des envois engagés.

`GET/PUT /v1/budget` : budget EUR par propriétaire et foyer, avec `limitMinor`, `perActionMinor`, `enabled`, `approvalRequired`. Les montants sont des centimes entiers. Première configuration : `If-Match: "0"`, ensuite révision actuelle. Une expansion ou la désactivation de l'approbation obligatoire exige une preuve fraîche. `spentMinor + heldMinor` ne dépasse jamais la limite ; réduire sous les engagements est refusé. La politique synthétique de l'étape 1 reste indépendante.

1. `POST /v1/quotes` : compte, capacité, `intentionId`, `operation=create|modify|cancel`, lignes et `deliveryAt` futur. Modifier/annuler exige `targetActionId` : dernière opération confirmée de la même intention. Le prix vient du fournisseur simulé. Le devis expire après 120 secondes ; l'empreinte couvre les conditions, le compte/époque et la version fournisseur.
2. `POST /v1/approvals` : `quoteId` et preuve fraîche. Approbation liée au devis exact, à la politique actuelle, à la génération d'accès et à l'expiration ; consommation atomique avec la réservation. Préférences, procédures et modèles n'accordent aucun droit.
3. `POST /v1/actions` : `quoteId`, éventuellement `approvalId`. `202` confirme seulement l'enregistrement atomique de l'action, réservation, verrou d'intention, événement et travail durable. `GET /v1/actions[/{id}]` expose progression et preuve.

| État | Signification et fonds |
| --- | --- |
| `READY` | Autorisé/réservé ; droits, politique et expiration revalidés avant envoi |
| `DISPATCHING` | Envoi engagé après écriture durable ; sans reçu, aucun succès établi |
| `UNKNOWN` | Réponse perdue/absente ; fonds conservés, recherche par clé fournisseur stable |
| `CONFIRMED` | Reçu vérifié ; fonds transférés aux dépenses confirmées |
| `CANCELLED` | Annulation prouvée par sa propre opération/reçu ; montant libéré selon ce reçu |
| `REJECTED` | Rejet prouvé ; réservation de cette opération libérée |
| `BLOCKED` | Droits/politique/expiration inadéquats avant envoi ; réservation non envoyée libérée |

Une même clé fournisseur ne produit pas deux mutations. Sans preuve, seul le rapprochement continue ; aucune commande n'est automatiquement renvoyée, ni remplacée pendant l'incertitude. La génération empêche un ancien worker de finaliser. Une modification réserve seulement une augmentation ; diminution/annulation affectent les dépenses après leur reçu. Le catalogue fictif contient lait, pain, fruits et deux repas ; aucun achat réel n'est effectué.

`POST /v1/webhooks/commerce-simulator` accepte `schemaVersion`, `eventId`, `householdId`, `actionId`, `occurredAt`. `X-Koyori-Signature` est HMAC-SHA256 du JSON trié compact, avec secret chiffré propre au compte ; fenêtre de cinq minutes et inbox anti-rejeu. Le signal réveille uniquement le rapprochement, y compris après révocation. Il ne devient jamais un reçu. Aucun secret de signature n'est exposé par HTTP.

## Google Calendar

Lecture seule : `POST /v1/connections/google-calendar/authorize` reçoit au plus huit `calendarIds`, exige une preuve fraîche et retourne l'URL OAuth. `GET /v1/oauth/google/callback` vérifie l'état unique/expirant, échange le code avec PKCE, vérifie les deux scopes read-only et les calendriers accessibles, puis chiffre les jetons par AES-GCM avec contexte propriétaire/connexion. L'idempotence sensible est également chiffrée. Un callback interrompu après consommation nécessite une nouvelle autorisation ; aucun code n'est rejoué aveuglément.

`POST /v1/connections/{id}/sync` accepte un travail durable. `GET /v1/connections/{id}/events` revalide compte, jeton et calendriers accessibles chez Google, puis retourne la dernière synchronisation complète. Une page de 50 événements est appliquée sous bail/version. Un token expiré (`410`) lance une génération complète ; les anciennes générations ne sont plus restituées. Une synchronisation partielle n'est pas présentée comme complète. URLs encodées, redirections refusées, réponses bornées à 1 Mo.

Refresh sous bail de 30 secondes ; un retour après révocation ne remplace pas l'enveloppe. Révocation locale immédiate, puis révocation Google durable et effacement du jeton. Une révocation déjà demandée/achevée conserve sa révision lors d'une nouvelle DELETE avec la version courante. Le retour fournisseur `400 invalid_token` prouve que le jeton est expiré/déjà révoqué ; les autres échecs gardent `revokePending` et sont différés sans bloquer les autres comptes. Une erreur OAuth `invalid_client` ne révoque pas les droits de l'utilisateur. Les traces HTTPX/httpcore détaillant URL et en-têtes sont désactivées ; les erreurs structurées restent expurgées. Push : ID de canal, hash du channel token, resource ID, expiration et numéro de message. Les doublons/anciens signaux ne modifient pas les données ; ils déclenchent seulement une synchronisation. Renouvellement une heure avant expiration et polling à 60 secondes pour réparer les signaux perdus.

### Configuration et qualification externe

Local : client OAuth Web Google, Calendar API activée, callback loopback autorisé. Fournir `KOYORI_GOOGLE_CLIENT_ID`, `KOYORI_GOOGLE_REDIRECT_URI`, `KOYORI_GOOGLE_CONFIG_FILE` (fichier privé contenant `client_secret`) et éventuellement `KOYORI_GOOGLE_WEBHOOK_URL` HTTPS. Le bootstrap Docker conserve la clé dans `provider-key`, monté seulement dans l'API et le connecteur. Sur l'hôte : `KOYORI_TOKEN_KEY_FILE` pointe vers une clé aléatoire de 32 octets hors Git. Un override Compose local doit monter le fichier Google et transmettre ces variables aux rôles API/connecteur ; ne committer aucune valeur secrète.

AWS : table `Connections`, clé KMS à rotation et secret applicatif Google à renseigner. `KOYORI_GOOGLE_CLIENT_ID` est facultatif à la synthèse ; sans lui, Google reste indisponible. Le callback réel émis par API Gateway doit être enregistré chez Google. API/connecteur accèdent aux enveloppes ; workflows synthétiques, activité et projection n'ont pas le déchiffrement KMS. API/projection invoquent seulement le profil Titan retenu ; API lit l'index, projection écrit/efface.

**Qualification réelle encore à faire** : aucun consentement Google, appel réel Titan, écriture S3 Vectors, déploiement ou coût AWS n'est qualifié dans cette session. Exécuter OAuth sur un compte de recette, vérifier retrait d'accès/refresh/watch ; tester Titan/S3 Vectors sur corpus français/anglais, corrections, effacement et quotas. Conserver région, droits, artefacts, résultats et coûts observés. La revue de code ne remplace pas ces preuves.

Sources officielles consultées le 2026-10-05 : [Google OAuth Web](https://developers.google.com/identity/protocols/oauth2/web-server), [Calendar sync](https://developers.google.com/workspace/calendar/api/guides/sync), [Calendar push](https://developers.google.com/workspace/calendar/api/guides/push), [Titan V2](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html), [S3 Vectors query](https://docs.aws.amazon.com/boto3/latest/reference/services/s3vectors/client/query_vectors.html), [CloudFormation index](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3vectors-index.html).

Contrats d'erreur recontrôlés le 2026-10-06 : [révocation Google](https://developers.google.com/identity/openid-connect/reference#revocation-endpoint) et [erreurs OAuth](https://developers.google.com/identity/protocols/oauth2/web-server#errors).
