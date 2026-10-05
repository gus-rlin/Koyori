# Revue de l'étape 2 — 2026-10-06

## Correctifs de la PR #2 — PASS : 9,4/10

Revue indépendante en lecture seule du sous-agent `review_stage2`, après les cinq constats transmis par l'utilisateur. Aucun constat P1/P2/P3 confirmé ne reste ouvert. Le code est modifié uniquement par l'agent principal. Base : `2c7542741b15503fb78245b90c8acd3570c1ab2d` ; branche `gus-rlin/koyori-etape2`. Empreinte examinée : `8d9f8807e64aacc060643b11fe00c4fae738a2c1fff553e155044fb9afa4b5d2`.

| Critère | Note | Résultat |
| --- | --- | --- |
| Correction | 2,9/3 | PATCH fusionné, unicité des clés dans les deux ordres de course, purge à expiration |
| Validation | 1,8/2 | Régressions, transactions DynamoDB Local et nouvelles recettes réussies |
| Sécurité | 2,8/3 | Preuve liée aux champs fournis, relecture canonique et gardes transactionnelles |
| Effets et compatibilité | 0,9/1 | Anciens index DONE réparés au rappel, premier rappel potentiellement vide jusqu'au worker |
| Maintenabilité | 1/1 | Primitives existantes, aucune nouvelle dépendance, empreinte explicite et portable |

Les cinq corrections conservent les champs omis par PATCH, permettent de remplacer une clé expirée, privilégient les partitions UTC récentes sous la borne de 500 références, planifient une purge durable des vecteurs expirés et rendent l'empreinte source indépendante de LF/CRLF et du tri de chemins Windows. La revue a aussi reproduit puis vérifié la correction de deux cas : anciens vecteurs déjà DONE sans calendrier de purge ; renouvellement préparé avant expiration committant après remplacement de la clé. Les gardes préservent maintenant la nouvelle clé et l'intention d'un renouvellement gagnant.

Le reviewer a exécuté indépendamment **37 tests ciblés** et **135 tests hors intégration**, avec 14 intégrations volontairement désélectionnées pendant les reconstructions du principal. Ruff, format, contrôle du diff et `--check-source` passent. Il a recalculé l'empreinte depuis les **59 blobs de l'index Git**, identique au checkout et à la preuve JSON staged, et vérifié la concordance des sources Lambda, bundle, template, lock et image runtime.

Le principal a exécuté **149 tests réussis, zéro échec/erreur/exclusion**, dont les 14 intégrations DynamoDB Local, les deux nouvelles recettes Docker **PASS**, ainsi que l'audit runtime sans vulnérabilité connue. Ces preuves ont été relues par le reviewer. [Rapport d'artefacts](artifact-evidence.json), [procédure et limites](stage2.md), [journal JRN-016](../../JOURNAL.md).

Le seuil demandé est atteint pour le code, la validation locale et la préparation AWS. Google, Titan, S3 Vectors réels et IAM exécuté restent non qualifiés ; aucun déploiement AWS. La CI du nouveau commit n'est pas encore observée au moment de cette revue.

## Revue initiale — résultat historique avant les constats de la PR

Le rapport ci-dessous est conservé comme historique. Sa note ne couvre pas les défauts signalés ensuite. Son empreinte désignait le checkout Windows et ne concordait pas avec les octets publiés après normalisation Git : correction factuelle dans JRN-016, nouvelle convention et preuve ci-dessus.

**PASS : 9,3/10**, revue indépendante du sous-agent `review_stage2`, en lecture seule. Aucun constat P1/P2/P3 confirmé ne reste ouvert. Le code est implémenté par l'agent principal uniquement.

Branche : `gus-rlin/koyori-etape2`, base `5865d95c56c532d49799b2b797f7515137a5c6b3`. Empreinte des sources et fichiers de construction examinés, selon `scripts/record_evidence.py` : `1adbd296685194580166ad3569a31f95b28eb4b88903dba4365e8ee7e339ae86`. [Rapport d'artefacts](artifact-evidence.json).

| Critère | Note | Résultat |
| --- | --- | --- |
| Correction | 2,8/3 | Réparation durable des projections, révocation et reprise isolée |
| Validation | 1,8/2 | Régressions de concurrence, interruption, quotas et erreurs fournisseur |
| Sécurité | 2,8/3 | Autorisation canonique, chiffrement, logs et plafond des requêtes |
| Effets et compatibilité | 0,9/1 | Socle, membres anciens, budgets et redémarrage couverts |
| Maintenabilité | 1/1 | Primitives existantes, composants et limites explicites |

La première revue avait conclu **FAIL : 7,3/10**. Sept défauts reproduits ont été corrigés avec régressions : effet vectoriel ancien après correction/effacement ; révocation répétée et réponse perdue ; logs HTTPX privés ; famine après vingt échecs ; retries Bedrock hors compteur ; jeton conservé après perte d'accès ; compteur de backoff remis à zéro après panne S3. Les tests couvrent aussi le retour d'un effet ancien après réparation déjà terminée et l'arrêt avant réparation.

Le principal a exécuté **135 tests réussis, zéro échec/erreur/exclusion**, les deux recettes Docker avec résultat PASS et l'audit du bundle sans vulnérabilité connue. Le reviewer a rejoué indépendamment **116 tests hors intégration**, les **6 tests CDK**, Ruff, format et contrôle du diff. Il a vérifié le JUnit complet, les nouvelles preuves de recette, le SBOM et la concordance des sources du bundle. Les recettes prouvent l'arrêt d'un processus vivant après commit fournisseur, la réservation conservée et le rapprochement de la même opération après redémarrage.

La note couvre le code, la validation locale et la préparation AWS. Google, Titan, S3 Vectors réels, IAM exécuté, coûts AWS et workflow GitHub distant restent non qualifiés. Les émulateurs et doubles fournisseur ne constituent pas ces preuves ; aucun déploiement n'a été effectué. [Configuration et limites](../stage2.md), [journal JRN-013](../../JOURNAL.md).
