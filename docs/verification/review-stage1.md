# Revues de l'étape 1 — 2026-10-05

Revue indépendante en lecture seule par le sous-agent `review_stage1`, appliquant `senior-code-basics`. Périmètre accepté : backend local complet et préparation AWS. Seuil demandé : au moins 9/10, sans défaut critique ou élevé restant. Aucun déploiement, aucune publication.

## Première révision : FAIL, 8,1/10

Diff stagé contre `81bb3d2505dcee08dc69dbb73e73cbf775422c5c`, branche `gus-rlin/koyori-etape1`. Empreinte des sources : `c7368732f13a2534b229f34fb2fd78b66351718ab5a12c8f542a9d4e79169f1c`. Le reviewer a rejoué les 53 tests, tous passés, et vérifié la concordance des artefacts. Il a inspecté la recette de crash Docker sans la rejouer.

| Priorité | Constat reproduit | Correction soumise |
| --- | --- | --- |
| P1 | Acceptation puis publication `SENT` et purge réelle d'ElasticMQ avant consommation : tâche `READY` sans `RUN`, réparation sans effet, quota retenu ; livraison après quinze jours également sans reprise | Intention atomique dès acceptation et transitions `READY`, clôture à la pause/annulation, réconciliation canonique des wakes anciens ; recettes unitaires et émulateurs dans `test_durability.py` et `test_integration.py` |
| P2 | Cognito Hosted UI classique préparé alors que la preuve fraîche documentée exige `prompt=login`, disponible dans managed login | Niveau Essentials explicite, managed login v2 et branding du client dans CDK ; assertions du template renforcées ; exécution Cognito toujours à qualifier |
| P3 | Réduire une appartenance non expirante à soixante secondes renvoie `STEP_UP_REQUIRED` | Expansion distinguée de la réduction ; preuve fraîche conservée pour prolongation, retrait d'expiration et réactivation ; tests API et génération d'accès |

| Catégorie | Note de première revue |
| --- | ---: |
| Correction | 2,0/3 |
| Validation | 1,6/2 |
| Sécurité | 2,8/3 |
| Effets et compatibilité | 0,8/1 |
| Maintenabilité | 0,9/1 |

## Seconde révision

**PASS, 9,3/10.** Aucun constat actionnable restant observé ; aucun défaut critique ou élevé restant. Le reviewer a confirmé la levée des trois constats sur le diff stagé contre le même commit de base. Empreinte des sources : `47056365fd20371e8ac97fbc314b78d5bfe0bb481a49fd989e81774982433f4a`, conservée dans les preuves de la livraison initiale au commit `4cb4393`. L'arbre de travail correspondait à l'index lors de la revue ; les modifications immédiatement suivantes complétaient uniquement les documents de livraison et le journal.

| Catégorie | Note finale | Limite ou observation |
| --- | ---: | --- |
| Correction | 2,8/3 | Intention atomique, reprise, fencing et quotas vérifiés ; concurrence distribuée hors des preuves locales |
| Validation | 1,8/2 | 65 tests rejoués, aucune exclusion ; quatre courses supplémentaires réussies |
| Sécurité | 2,8/3 | JWT, ACL, preuve fraîche et générations couverts ; IAM et Cognito contrôlés statiquement |
| Effets et compatibilité | 1/1 | Aucun effet indésirable observé sur transitions, droits et quotas |
| Maintenabilité | 0,9/1 | Intentions centralisées et adaptateurs séparés ; domaine encore dense |

Les injections indépendantes supplémentaires opposent réception à pause/annulation, checkpoint à pause et acquisition à amendement. Les écritures périmées sont refusées. Ruff et format passent ; les empreintes source, lock, bundle et template concordent ; les cinq services actifs utilisent l'image enregistrée.

La nouvelle recette Docker PASS et l'audit runtime ont été exécutés par le superviseur puis inspectés par le reviewer, qui ne les a pas rejoués. Aucun login Cognito, IAM exécuté, bus distant ou restauration AWS n'a été qualifié. Le workflow GitHub n'a pas été publié ni exécuté. Le reviewer n'a modifié aucun fichier.

Après cette livraison, les retouches HTTP de JRN-008 ont été vérifiées par l'agent principal : [résultats et empreintes actuels](stage1.md). Aucune nouvelle revue indépendante ni nouvelle note n'est attribuée à ces retouches ; le verdict ci-dessus conserve sa portée initiale.
