# Interface compagnon Koyori

Application React/TypeScript/Vite autonome, en français. **Démonstration interactive avec données fictives**, sans connexion à l’API Python, à Alexa, à Google ou à un commerçant. Les modifications vivent uniquement dans l’onglet et disparaissent au rechargement. Aucun microphone n’est demandé et aucun achat n’est envoyé.

## Démarrer

Depuis ce répertoire, avec Node.js 22.12+ ou 24 :

```powershell
npm ci
npm run dev
```

Ouvrir [l’interface locale](http://127.0.0.1:5178). Le serveur écoute uniquement sur la boucle locale, avec port strict pour ne pas remplacer silencieusement une autre application.

Si Node refuse le certificat du registre sur ce poste Windows, utiliser les certificats système approuvés (Node 24), sans désactiver TLS :

```powershell
$env:NODE_USE_SYSTEM_CA = '1'
npm ci
```

## Parcours disponibles

- Vue du jour, agenda fictif et historique des attentions.
- Création, filtrage, pause, reprise et annulation d’une demande locale.
- Panier avec détail du montant et accord explicitement simulé. Le refus met la demande en pause ; la reprise permet de revoir le panier. Un accord n’est jamais présenté comme une confirmation du commerçant.
- Recherche, correction et suppression confirmée des préférences fictives.
- Interrupteurs de routines, sans programmation d’un réveil réel.
- Fiches de services indiquant les limites de connexion.
- Thèmes clair/sombre, navigation mobile, dialogues natifs accessibles, prise en compte du mouvement réduit.

La navigation utilise des fragments (`#today`, `#tasks`, `#memory`, `#routines`, `#services`, `#activity`, `#settings`) pour permettre liens directs et historique sans configuration de réécriture serveur.

## Vérifier

```powershell
npm run build
npm test -- --workers=2
npx prettier --check src tests index.html package.json vite.config.ts playwright.config.ts tsconfig.json
npm audit
```

Les tests Playwright utilisent Chrome installé, avec deux configurations : ordinateur 1440 × 1000 et mobile Chromium émulant les dimensions/toucher d’un iPhone 13. **Ce n’est pas un test Safari/iOS réel.** Le serveur de test démarre sur 4178 ; s’il existe déjà, il est réutilisé hors CI. Pour tester le build de production, démarrer préalablement `npm run preview` sur ce port après un build réussi.

Les tests couvrent les parcours observables, le retour de focus après fermeture d’un dialogue, la validation du formulaire, les états vides, les changements locaux, le contraste automatisé, les deux thèmes et l’absence de débordement jusqu’à 320 px. Les captures sont dans `test-results/` (ignoré par Git).

Le [rapport de vérification](../../docs/verification/interface.md) décrit les résultats et leur portée. Aucun contrôle automatisé ne remplace une évaluation complète avec lecteurs d’écran et appareils physiques.

## Organisation

- `src/App.tsx` : état local, navigation, actions et vues secondaires.
- `src/Overview.tsx` : composition de la vue du jour.
- `src/components.tsx` : cartes de demandes, chronologie et état vide.
- `src/Dialog.tsx` : dialogue HTML natif, focus et touche Échap.
- `src/demo.ts` : fixtures synthétiques et types métier de la démonstration.
- `src/styles.css` : tokens, composants, thèmes et adaptations responsive.
- `public/` : images WebP générées puis optimisées et favicon issu de Phosphor.

CSS natif et dialogues HTML ont été retenus plutôt qu’un système de composants complet : le nombre de primitives est réduit, les interactions reposent sur le navigateur et le design reste cohérent. Aucune bibliothèque d’animation ou de gestion d’état globale n’est nécessaire ici. Manrope est auto-hébergée via Fontsource (OFL-1.1), les icônes proviennent de Phosphor (MIT). Le code conserve la licence Apache-2.0 du dépôt.

## Limites et raccordement suivant

L’interface n’est pas encore une PWA hors ligne et n’inclut ni authentification, ni autorisations multi-utilisateur, ni persistance serveur. Les badges personnel/partagé décrivent des fixtures, pas une isolation effective dans ce frontend. Il n’y a pas de résultat réseau à charger et donc pas de faux état de chargement.

Le raccordement doit utiliser les contrats de [l’API](../../docs/api.md) et de [coordination](../../docs/stage3.md), puis le transport vocal de l’étape 4. Les autorisations, devis, reçus et changements de mémoire doivent rester validés par le backend ; les données de cet onglet ne constituent aucune autorité d’exécution. Ne pas brancher directement les boutons d’approbation sur un fournisseur.

### Visuel

Les fichiers `public/home.webp` et `public/home-small.webp` proviennent d’une image produite avec l’outil intégré `image_gen`, inspectée puis transcodée à 1200 et 800 pixels de large avec Sharp. Aucune photographie de foyer réel n’a été utilisée. Le favicon est rendu depuis `WaveformIcon` de Phosphor.

Prompt utilisé :

> Use case: editorial interior photography. Asset type: photographic banner for Koyori, a calm personal home assistant web app. Create a beautifully composed photorealistic wide 3:2 image of an inhabited contemporary Japanese-inspired living room opening onto a lush green courtyard, a low muted sage green fabric sofa on the right, pale silver plaster wall, oak side table with small ceramic teacup and a book, one sculptural leafy branch, dappled soft late morning daylight across the floor. Quiet real domestic atmosphere, refined architectural magazine photography, shot on 35mm, subtle film texture, natural greens and silver neutrals, low saturation, no overly yellow or beige color cast. Perspective from inside looking out, lush green foliage visible through large window along upper center. No people, no electronics, no text, no watermarks, no UI, no logos. The center and right side will be used in a landscape cropped panel, so keep furnishings in that area.
