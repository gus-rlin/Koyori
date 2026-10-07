# Interface compagnon Koyori

Application React/TypeScript/Vite en français, **connectée au backend par défaut**. Les demandes, souvenirs, routines, connexions et activités viennent de l’API. La démonstration autonome reste accessible uniquement avec `?demo=1` ; elle ne sert jamais de repli réseau.

## Démarrer

Depuis la racine, reconstruire le backend courant puis démarrer les services :

```powershell
docker compose build api
docker compose up -d --no-build
```

Depuis `apps/web`, avec Node 24 :

```powershell
npm ci
npm run dev
```

Ouvrir [l’interface locale](http://127.0.0.1:5178). Le proxy Vite transmet `/v1` à `http://127.0.0.1:8088`. Pour une autre API, définir `KOYORI_API_TARGET` avant de démarrer Vite (variable serveur, jamais jeton `VITE_*`). `vite preview` utilise le même proxy sur 4178. En hébergement de production, servir le bundle avec un reverse proxy `/v1` vers l’API, en HTTPS ; le serveur Vite de développement n’est pas le déploiement de production.

Les origines vocales locales autorisées dans Compose sont `http://127.0.0.1:5178`, `http://127.0.0.1:4178` et l’ancien port 5173. Définir `KOYORI_ALLOWED_ORIGINS` explicitement pour d’autres origines, puis recréer API/voix. Aucun wildcard ni désactivation du contrôle Origin.

Sur ce poste, `NODE_USE_SYSTEM_CA=1` résout le certificat npm. Pour Docker, voir le secret BuildKit `trusted_ca` dans [l’exploitation](../../docs/operations.md). TLS reste vérifié.

## Identité et opérations

L’écran de connexion accepte un **jeton d’accès** signé par l’émetteur configuré et charge uniquement ses foyers autorisés. Il n’implémente pas encore la redirection interactive Cognito/PKCE. Jeton et données restent en mémoire ; pas de localStorage, sessionStorage, URL contenant un bearer ou connexion automatique au rechargement. Le serveur conserve les données métier. Pour les fixtures locales, générer le jeton puis le copier dans le champ, sans le committer :

```powershell
docker compose run --rm --no-deps demo python -m koyori.demo token alex
```

Les commandes portent `Idempotency-Key` et, pour les objets existants, `If-Match`. Après coupure réseau, réessayer la même opération conserve sa clé. Après conflit de révision, fermer le dialogue, actualiser et examiner la nouvelle version. Les confirmations sont affichées après réponse serveur. Les listes sont paginées, puis actualisées toutes les dix secondes lorsque l’onglet est visible ; ce n’est pas un abonnement AppSync. Une session expirée efface l’espace privé et demande une reconnexion.

Parcours : demandes (création, filtre, plan, pause/reprise/annulation), panier issu du devis serveur, souvenirs (recherche dans la liste chargée, correction et suppression confirmée), routines existantes (pause/reprise), services existants (lecture) et activité. Aucun agenda inventé. La création de routines et la connexion de nouveaux comptes ne sont pas proposées par ces écrans.

### Approbation d’un panier

Le frontend affiche conditions, montant, livraison et expiration du devis. « Vérifier mon identité pour approuver » crée un challenge lié à `POST /v1/approvals` et au hash du corps normalisé. Fournir ensuite un **jeton ID frais lié au nonce affiché**, émis pour le même utilisateur. Le serveur vérifie cette preuve puis accorde une autorisation à usage unique. Le frontend crée l’approbation, puis transmet la décision à la révision exacte de l’objectif ; il conserve le résultat du premier appel si le second échoue.

Pour un environnement local synthétique uniquement, remplacer `NONCE_AFFICHE` par le nonce du dialogue :

```powershell
docker compose run --rm --no-deps demo python -c "from koyori.config import Settings; from koyori.demo import token; print(token(Settings.from_env(), 'alex', nonce='NONCE_AFFICHE'))"
```

Aucune clé privée ne rejoint le frontend. Un compte réel doit obtenir sa preuve auprès de son émetteur ; aucun endpoint de fabrication de jeton n’est ajouté. Un panier simulé reste simulé après approbation et son reçu ne prouve pas un achat réel.

## Voix et microphone

« Démarrer la voix » admet une session personnelle via `/v1/sessions`, ouvre l’URL WebSocket retournée et envoie le ticket unique dans le premier message. Aucun bearer n’est mis dans l’URL ; les URL AgentCore présignées restent en mémoire. Les URL non chiffrées ne sont acceptées qu’en boucle locale.

- **Backend simulé (Compose)** : aucun accès microphone, champ « Tour vocal simulé » explicite. Le texte traverse réellement le WebSocket, est enregistré et devient une demande dans le domaine. L’annonce audio du simulateur n’est pas une synthèse Polly réelle.
- **Backend vocal réel configuré** : consentement navigateur, capture mono via AudioWorklet, conversion PCM16 à 16 kHz, trames avec séquence et génération, lecture du PCM serveur via Web Audio. Une interruption purge la file audio ; arrêt, erreur, déconnexion et sortie de page libèrent les pistes et le contexte. Aucun redémarrage automatique du micro.

HTTPS ou boucle locale sont nécessaires. Nova/Polly et les identifiants AWS doivent être configurés/qualifiés côté serveur conformément à [l’étape 4](../../docs/stage4.md). Le frontend ne contient pas d’identifiants AWS et ne transforme pas le mode simulé en voix réelle. Pas d’intégration Alexa native.

## Vérifier

```powershell
npm run build
npm test -- --workers=2
npx prettier --check src tests public/pcm-capture.js index.html vite.config.ts
```

Chrome installé est utilisé sur ordinateur et en mobile émulé (pas Safari/iOS). Les tests réseau interceptent des contrats synthétiques ; les tests audio utilisent le véritable graphe Web Audio et un périphérique Chrome synthétique. Le [rapport de raccordement](../../docs/verification/web-backend.md) sépare ces preuves de la recette Docker.

Recette opt-in contre une stack locale active, depuis `apps/web` :

```powershell
$env:KOYORI_WEB_LIVE = '1'
npm test -- --workers=1 backend
```

Pour une stack isolée, fournir `KOYORI_API_TARGET` et `KOYORI_WEB_COMPOSE_ENV` (chemin depuis la racine du dépôt). La recette crée une identité et un foyer synthétiques distincts par exécution, des souvenirs et demandes, puis approuve un panier du simulateur. Elle conserve ces fixtures côté serveur et désactive les traces/captures/vidéos contenant les jetons. Aucun compte externe ni fournisseur facturable n’est appelé. Les tests Docker sont explicitement exclus de la CI frontend sans backend ; ils ont été exécutés localement.

## Organisation

- `src/App.tsx` : connexion, navigation et vues alimentées par l’API.
- `src/api.ts` : contrats HTTP, pagination, délais, révisions et idempotence.
- `src/QuoteApproval.tsx` : challenge, preuve fraîche et décision sur le panier.
- `src/voice.ts`, `public/pcm-capture.js` : transport WebSocket, capture PCM et lecture.
- `src/DemoApp.tsx`, `src/Overview.tsx`, `src/demo.ts` : ancienne démonstration explicite.
- `src/Dialog.tsx`, `src/components.tsx`, `src/styles.css` : primitives visuelles partagées.

Aucune dépendance ajoutée. React, dialogues natifs et Web Audio suffisent ; Manrope et Phosphor restent servis localement. Les contrats serveur restent l’autorité. Références AudioWorklet consultées le 2026-10-07 : [traitement dans un worklet](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Using_AudioWorklet), [fréquence du contexte](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletGlobalScope/sampleRate).

### Visuel

Les fichiers `public/home.webp` et `public/home-small.webp` proviennent d’une image produite avec l’outil intégré `image_gen`, inspectée puis transcodée à 1200 et 800 pixels de large avec Sharp. Aucune photographie de foyer réel n’a été utilisée. Le favicon est rendu depuis `WaveformIcon` de Phosphor.

Prompt utilisé :

> Use case: editorial interior photography. Asset type: photographic banner for Koyori, a calm personal home assistant web app. Create a beautifully composed photorealistic wide 3:2 image of an inhabited contemporary Japanese-inspired living room opening onto a lush green courtyard, a low muted sage green fabric sofa on the right, pale silver plaster wall, oak side table with small ceramic teacup and a book, one sculptural leafy branch, dappled soft late morning daylight across the floor. Quiet real domestic atmosphere, refined architectural magazine photography, shot on 35mm, subtle film texture, natural greens and silver neutrals, low saturation, no overly yellow or beige color cast. Perspective from inside looking out, lush green foliage visible through large window along upper center. No people, no electronics, no text, no watermarks, no UI, no logos. The center and right side will be used in a landscape cropped panel, so keep furnishings in that area.
