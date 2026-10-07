# Vérification du raccordement interface/backend

Date : **2026-10-07**, Europe/Paris. Branche `gus-rlin/connect-web-backend`, base `42008d7`. Voir JRN-036. Les mesures historiques de [l’interface de démonstration](interface.md) ne sont pas réattribuées à cette version.

## Portée

L’application charge le backend par défaut ; la démo en mémoire est isolée derrière `?demo=1`. Aucune source Python du backend ni dépendance n’a changé. Compose transmet les origines navigateur autorisées et le workflow ajoute un job frontend. La documentation précise l’identité par jeton fourni, le step-up, la configuration de même origine et les limites des fournisseurs.

## Preuves

- Build TypeScript strict et Vite réussi, puis tests exécutés contre ce build de production sur 4178. Playwright construit/démarre son propre serveur, sans réutilisation d’un serveur inconnu.
- `npm test --prefix apps/web -- --workers=2` avec la recette Docker activée : **38 réussites, zéro échec/exclusion, 58,4 s** (19 scénarios sur ordinateur et mobile émulé).
- Tests navigateur : démonstration historique ; lecture des données autorisées, création/pause, correction de mémoire, pagination avec page vide, expiration du jeton, conflits de révision, panne réseau sans repli synthétique, idempotence après perte de réponse et approbation en deux étapes avec reprise du seul appel non résolu.
- Voix : véritable AudioContext/AudioWorklet dans Chrome avec périphérique synthétique. Frames PCM16 mono de 648 octets (en-tête de 8 + 320 échantillons), séquences et générations, lecture de PCM serveur, interruption, fermeture des pistes, refus d’autorisation et permission tardive après arrêt. Transport WebSocket intercepté pour ces cas.
- Recette navigateur→backend Docker sans interception : identité signée locale distincte par exécution, nouveau foyer, demande créée, mémoire corrigée puis lue via HTTP, données retrouvées après rechargement/reconnexion, admission WebSocket et tour textuel explicitement simulé créant une demande durable. Budget et connexion de commerce préparés par l’API ; approbation effectuée dans le navigateur après challenge et preuve fraîche, puis reçu `CONFIRMED` du simulateur lu côté API. Les traces, vidéos et captures de cette recette sont désactivées pour éviter de conserver des jetons.
- Axe : aucune violation détectée sur les sept vues connectées claires et les réglages sombres, dans les deux configurations Chrome ; tests existants de la démo conservés. Pas de débordement à 320 px sur accueil, demandes, mémoire et services. Capture mobile sombre des services inspectée.
- Python ciblé : `python -m pytest -q tests/test_stage4_voice.py tests/test_stage4_sessions.py tests/test_control.py --junitxml=artifacts/web-backend-contracts.xml` : **50 réussites**, aucun échec/exclusion, 11,35 s. Dépréciation Starlette/httpx déjà connue. Cela ne répète pas la suite cumulative ni les recettes de crash historiques.
- Prettier, `git diff --check` et `record_evidence.py --check-source` passent. Relecture des frontières : bearer uniquement dans les en-têtes, aucun stockage navigateur persistant, pas de redirection HTTP avec credentials, identifiants d’objets encodés, rendu React échappé, révisions/idempotence et step-up inchangés côté serveur ; origin WebSocket explicitement autorisée, aucune clé privée ni identité AWS dans le bundle.

## Environnement et reproduction

```powershell
$env:KOYORI_WEB_LIVE = '1'
$env:KOYORI_WEB_COMPOSE_ENV = '.local/web-integration.env'
$env:KOYORI_API_TARGET = 'http://127.0.0.1:8089'
npm test --prefix apps/web -- --workers=2
```

La stack isolée `koyori-web-integration` utilise l’image reconstruite `koyori-web-integration:local`, API 8089, voix 8100, DynamoDB Local 8801 et ElasticMQ 9325, réseau `10.253.46.0/24`. Le fichier local ignoré contient uniquement les noms et ports. L’image a été construite depuis les sources courantes avec le certificat public approuvé du poste monté comme secret BuildKit ; TLS et versions verrouillées conservés. Services/volumes locaux et fixtures conservés pour inspection. `docker compose --env-file .local/web-integration.env down` les arrête en conservant les volumes ; la recette n’efface pas les foyers créés. Aucun appel fournisseur ou ressource AWS, aucun coût AWS observé.

Les premières tentatives contre l’ancien environnement ont créé des fixtures synthétiques sous `alex` avant de révéler l’absence du module vocal dans son image historique. Le service vocal essayé sur cet environnement a été arrêté ; ses autres services et volumes n’ont pas été remplacés. La nouvelle recette n’utilise plus le quota de ce profil partagé.

## Limites réelles

- Chrome ordinateur et mobile émulé ; pas Safari/iOS ni appareil/microphone physique. Nova/Polly, AgentCore et Alexa réels non qualifiés. Le test PCM ne prouve ni qualité de transcription, ni latence distante, ni qualité conversationnelle.
- Jeton d’accès et preuve ID fournis explicitement ; aucun login Cognito/PKCE interactif. La production nécessite HTTPS, reverse proxy et configuration explicite des origines/runtime. Pas de déploiement effectué.
- Création de routines et connexion de nouveaux comptes restent des opérations API ; l’interface contrôle/affiche les objets existants. Activité actualisée par polling, sans AppSync. La mémoire se filtre dans les enregistrements chargés, sans écran de recherche lexicale d’archives.
- Les résultats backend, Lambda, CDK et recettes de reprise historiques de `artifact-evidence.json` restent historiques. Son empreinte source est actualisée pour Compose/CI avec une section `webIntegrationVerification` séparée ; elle ne requalifie pas ces artefacts.
- La CI frontend exécute les scénarios interceptés/audio et la démo. La recette Docker reste opt-in et est validée localement ; résultats GitHub à lire sur la PR, aucune fusion automatique.
