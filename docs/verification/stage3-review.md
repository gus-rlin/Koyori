# Revue de l'étape 3 — 2026-10-06

État final : **PASS, 9,2/10**, sans constat matériel ouvert, après trois passages indépendants et corrections. Le score porte sur le code, la validation locale et la préparation AWS ; il ne qualifie pas le modèle réel ni les services distants. Le code est implémenté par l'agent principal seul. Le sous-agent `stage3_review` intervient en lecture seule, selon `senior-code-basics`.

Branche : `gus-rlin/koyori-etape3`, baseline de l'étape 2 `fb5f310`. Première revue du diff staged SHA-256 `dd98fd99c3b490b9c5c8c28e8a4245e3d405b02a05103d89415e6c7abba4345a` : **FAIL, 7,3/10**. Cette note reste attachée au premier état et ne vaut pas validation des corrections.

| Critère | Première note | Observation du reviewer |
| --- | --- | --- |
| Correction | 2,1/3 | Progression, intentions et reprises solides ; défauts de sources et quotas reproduits |
| Validation | 1,6/2 | 47 tests ciblés rejoués passent ; cinq scénarios manquent |
| Sécurité | 2,0/3 | Autorisations, budgets, IAM et logs encadrés ; dépendance périmée atteignant le fournisseur |
| Effets et compatibilité | 0,7/1 | Générations séparées ; réadmission et historique des connexions fragiles |
| Maintenabilité | 0,9/1 | Contrats stricts, primitives réutilisées et documentation utile |

| Constat confirmé | Correction de l'agent principal | Régression |
| --- | --- | --- |
| P1 : source découverte par le lecteur non surveillée après checkpoint ; achat confirmé après effacement | Union bornée des références, révisions inchangées, contrôle et nouvelles dépendances dans la même transaction ; contrôle avant réserve/dispatch | `test_reader_source_outside_prompt_remains_a_live_dependency`, correction et effacement, événement ou absence d'événement |
| P2 : routine en pause conservant son quota après révocation/expiration | Intention indépendante `RULECHECK`, relecture conditionnelle des droits et de l'horizon ; quota libéré une fois | `test_paused_routine_releases_quota_without_an_occurrence_wake` |
| P2 : réadmission avant sweep conservant l'ancienne tâche en attention et son quota | Terminalisation explicite de l'époque révoquée, fermeture du dispatch et quota libéré ; actions séparées | `test_readmission_does_not_keep_an_old_goal_quota_or_authority` |
| P2 : compte actif masqué par 101 anciennes connexions | Pagination jusqu'à 500 lignes, comptes du propriétaire/époque filtrés, huit au maximum, troncature explicite et décision adaptée | `test_account_discovery_pages_past_history_or_reports_its_bound`, 101 et 501 lignes |
| P2 : fuseau inconnu produisant HTTP 503 | Conversion de `ZoneInfoNotFoundError` en erreur de validation | `test_unknown_timezone_is_an_input_error`, deux routes HTTP 422 |

Les huit premières régressions, après correction de deux fixtures (devis puis réservation sur deux passes ; nom de la méthode de retrait du membre), échouent sur le comportement produit avant modification. Après corrections, les quatorze cas de `tests/test_stage3_review.py` passent. La limite des sources est aussi vérifiée sur deux lecteurs parallèles : refus explicite, aucun checkpoint partiel.

Le reviewer a relu JUnit (186 réussites sans exclusion avant corrections), les trois recettes Docker PASS et le SBOM de 52 composants sans vulnérabilité déclarée. La qualification Nova/AWS reste NOT_RUN ; modèle réel, IAM exécuté, Google et comportement distribué distant ne sont pas validés par cette revue. [Limites](../stage3.md), [journal JRN-018](../../JOURNAL.md).

## Deuxième passage

**FAIL, 8,1/10**, diff staged SHA-256 `c45439cd3c5af727e448476ba6f95b207fed3fa320c5cd7e002763d006337b0d`. Le reviewer confirme la correction des cinq constats initiaux et rejoue 36 tests ciblés réussis. Notes : correction 2,4/3 ; validation 1,8/2 ; sécurité 2,2/3 ; effets/compatibilité 0,8/1 ; maintenabilité 0,9/1. Trois défauts supplémentaires sont reproduits ; ce verdict ne couvre pas les corrections suivantes.

| Constat confirmé | Correction de l'agent principal | Régression |
| --- | --- | --- |
| P1 : référence déclarée à un troisième agenda acceptée mais absente des dépendances | Union de toutes les références acceptées avec les sources du prompt ; contrôle de révisions, borne, gardes et surveillance persistante | `test_declared_third_calendar_is_guarded_even_outside_prompt_snapshots`, changement avec/sans événement |
| P2 : contrôle d'expiration supprimant le dernier réveil dû après panne jusqu'au lendemain | Livraison canonique du dernier réveil persistant d'une règle active encore autorisée ; quota et occurrence atomiques | `test_restart_after_last_routine_day_preserves_the_persisted_occurrence`, reprise et course contrôle/livraison |
| P2 : nouveau compte simulé invisible après réadmission | `memberEpoch` enregistré à la création ; ancien compte exclu, nouveau utilisable ; valeur historique 1 conservée pour les anciens comptes | `test_new_simulated_account_after_readmission_uses_current_member_epoch` |

Les cinq nouvelles régressions échouent avant ces corrections. Les 200 tests complets du second état avaient passé sans exclusion ; ils ne constituent pas la validation du troisième état. Artefacts et suite seront régénérés avant clôture.

## Troisième passage — verdict final

**PASS, 9,2/10**, sur le diff staged SHA-256 `dc52a1d8da966d402e25081f3b481d384c6b4b58c35f796e2207952eb3f6d0d6`. Les huit constats des passages précédents sont corrigés ; aucun constat matériel ouvert n'est signalé. Les ajouts documentaires de clôture enregistrent ensuite ce verdict, sans modification du code examiné.

| Critère | Note finale | Portée de la vérification |
| --- | --- | --- |
| Correction | 2,9/3 | Sources persistantes, droits, générations, quotas et dernier réveil contrôlés |
| Validation | 1,8/2 | 66 tests ciblés rejoués, deux courses supplémentaires et preuves cumulatives vérifiées ; distant non qualifié |
| Sécurité | 2,7/3 | Sources périmées et révocation bloquent l'autorité ; budgets, isolation et secrets encadrés |
| Effets et compatibilité | 0,9/1 | Rapprochement indépendant et comptes réadmis vérifiés sur la base isolée |
| Maintenabilité | 0,9/1 | Contrats bornés, composants existants, documentation et régressions reproductibles |

Le reviewer rejoue **66 tests ciblés**, dont les 19 régressions ajoutées après les deux premières revues : tous passent. Deux courses forcées supplémentaires passent également : révocation avant livraison d'un réveil tardif et correction de mémoire avant lecture, sans intention ni occurrence indue. Il contrôle le JUnit final : **205 réussites, zéro échec, erreur ou exclusion** ; les trois rapports de reprise Docker frais sont **PASS**.

Les 37 modules du bundle Lambda correspondent octet pour octet aux sources. Le reviewer recalcule les empreintes du code, du lock, du bundle et du template ; elles correspondent à [artifact-evidence.json](artifact-evidence.json). Empreinte source : `e3ee48b93f552dd6500a87ab0b0ffd6b7be980eb8318122bb1548adde4d967d1`. L'image inspectée est `sha256:46bc5fecbcff75d372512350fe7f6c14140c8586ff2731b866d900af6b22486d`. Le SBOM contient 52 composants et aucune vulnérabilité connue signalée ; le contrôle du diff staged réussit.

Les tests et recettes utilisent DynamoDB Local et des fournisseurs commerciaux simulés. Nova/AWS reste [NOT_RUN](nova-qualification.json), faute d'identifiants ; qualité du modèle réel, IAM exécuté, Google et comportement distribué distant restent à qualifier. Le checkout d'origine a évolué pendant la tâche : comparer ses corrections de l'étape 2 avant intégration et résoudre la numérotation des entrées de journal concurrentes. Le verdict atteint le seuil de revue demandé sur le périmètre implémenté et vérifié, sans transformer ces limites en capacités opérationnelles.
