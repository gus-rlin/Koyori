# Vérification de l’interface compagnon

Date : **2026-10-06**, Europe/Paris. Travail local sur `gus-rlin/koyori-interface`, issu de `f81df40`, dans le worktree isolé `koyori-interface/Koyori`. Voir JRN-026 (identifiant corrigé lors de la réunion JRN-027).

Ce rapport décrit la démonstration historique, maintenant accessible avec `?demo=1`. Le raccordement du 2026-10-07 est qualifié séparément dans [web-backend.md](web-backend.md). Les anciennes mesures Lighthouse ne qualifient pas la version connectée.

## Résultats observés

| Contrôle | Résultat | Portée |
| --- | --- | --- |
| `npm run build` | Réussi | TypeScript strict et bundle Vite de production |
| `npm test -- --workers=2` | 16 tests réussis en 13,1 s | 8 parcours rejoués en Chrome ordinateur et mobile émulé, contre le build de production servi sur 4178 |
| Axe WCAG 2 A/AA et 2.1 AA | Aucune violation détectée | Accueil clair/sombre et panier sombre sur les deux configurations Playwright |
| Axe sur les six autres vues | Aucune violation détectée dans les 12 combinaisons | Ordinateur, chaque vue en clair et sombre ; rapport brut local `artifacts/interface-accessibility.json` |
| Largeur 320 px | Pas de débordement horizontal détecté | Sept vues ; navigation mobile exercée à 390 px |
| Revue visuelle | Captures ordinateur/mobile et clair/sombre inspectées | Photographie, hiérarchie, navigation, cartes et compositions responsive |
| Lighthouse mobile | Performance **99**, accessibilité **100**, bonnes pratiques **100** | Mesure locale sur le build de production, pas une mesure terrain |
| FCP / LCP / CLS / TBT Lighthouse | **1,5 s / 2,1 s / 0 / 0 ms** | Émulation mobile Lighthouse ; pas de mesure d’INP réelle |
| `npm audit` | Aucune vulnérabilité connue signalée | 149 paquets installés, runtime et développement |

Lighthouse est exécuté avec `npx lighthouse http://127.0.0.1:4178 --chrome-flags='--headless --no-sandbox' --output=json --output-path=../../artifacts/interface-lighthouse.json --only-categories=performance,accessibility,best-practices --quiet` depuis `apps/web`. Le flag sandbox concerne uniquement le processus Chrome de mesure locale. Le rapport brut et les captures Playwright sont ignorés par Git ; ils ne sont pas nécessaires au build.

## Corrections issues des contrôles

- Les textes secondaires manquaient de contraste sur certains fonds clairs : le token a été assombri.
- Les couleurs du document ne reprenaient pas les tokens sombres : correction à la racine.
- L’analyse initiale pouvait mesurer l’opacité transitoire d’entrée : contrôle Axe avec mouvement réduit, afin d’évaluer le contenu stabilisé ; les animations restent vérifiées visuellement et désactivables.
- La navigation pouvait couper « Mes demandes » sur deux lignes : espacements ajustés.
- La première mesure Lighthouse signalait le favicon absent et une image trop lourde : favicon Phosphor, variante responsive WebP et préchargement. Scores passés de 96/100/96 à 99/100/100, LCP de 2,7 à 2,1 secondes dans ces deux mesures locales.
- Après mise de côté d’un panier, reprendre la demande réouvre la possibilité de vérifier le panier. La régression est couverte par le parcours de refus/reprise.

## Limites explicites

Aucun test Safari réel, lecteur d’écran humain, appareil physique ou réseau distant. Aucune intégration HTTP au backend, aucune authentification et aucun achat. Les suites Python et Docker ne sont pas répétées : aucun fichier de leur exécution n’est modifié. Le build est un frontend de démonstration ; les contrats de sécurité du backend ne sont pas validés par ces tests.

La relecture des entrées utilisateur confirme un rendu texte React, sans HTML injecté, URL fournisseur, token, stockage persistant ni transport réseau métier. Cette observation concerne uniquement ce frontend local et ne constitue pas un audit de sécurité du produit complet.
