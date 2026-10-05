# Vérification de l'étape 1

**Livraison validée le 2026-10-05 : PASS, 9,3/10 en revue indépendante**, sans constat actionnable restant observé. 65 tests passés sans exclusion, recette Docker de reprise PASS, bundle Linux reconstruit, synthèse CDK et audit runtime réalisés. Les trois constats de la première revue à 8,1/10 sont levés. Le backend local et la préparation AWS constituent le périmètre validé ; les services AWS distants restent à qualifier.

## Retouches avant PR — 2026-10-05

Deux corrections ciblées des réponses d'erreur HTTP sont consignées dans JRN-008 : en-têtes et trace communs pour les rejets précoces `413/422`, et conservation d'`Allow` pour les `405`. **68 tests passent sans exclusion**, Ruff et format passent ; les trois réponses sont aussi vérifiées sur l'API en conteneur. Image et bundle Lambda reconstruits, recette Docker de reprise PASS, synthèse CDK et ses cinq tests réussis. Les [empreintes](artifact-evidence.json) correspondent à cette version ; l'audit des dépendances de la livraison initiale reste applicable au lock inchangé. La note **9,3/10** ci-dessus porte sur la revue initiale, qui n'a pas été rejouée pour ces retouches.

## Recettes et preuves

| Exigence | Preuve executable |
| --- | --- |
| Isolation entre foyers et privé/partagé | `tests/test_control.py` : lecture privée refusée à un autre membre et à l'admin ; contexte et ressource d'un autre foyer refusés |
| Authentification et appareil partagé | Tokens invalides/expirés, ID token, mauvais client/audience/scope/issuer/algorithme ; type de canal dérivé du serveur |
| Expansions et délégations | Nonce, identité, fraîcheur, expiration, hash et usage unique ; contrôle du propriétaire, révocation et générations d'accès |
| Transaction et idempotence | Recette API, conflits HTTP, quota et dernier admin ; `tests/test_integration.py` provoque un échec de condition avec rollback de l'ensemble |
| Reprise et fencing | `tests/test_durability.py` : checkpoint conservé, bail expiré, ancien propriétaire et ancien snapshot refusés, pause/annulation |
| Réveil en cours et réparation | Wake pendant un run, intention suivante persistée, sweep équitable entre shards |
| Publication et doublons | Crash injecté après envoi, outbox encore pending, publication répétée ; déduplication dans de vraies files ElasticMQ |
| Perte de file et livraison ancienne | Purge réelle d'une file après publication `SENT`, réparation sans consommation ; première livraison après quinze jours ; intentions à l'acceptation, reprise et amendement ; tâche suspendue ou terminale conservée |
| Activité autorisée | Inbox et compteur atomiques, doublons sans seconde entrée, ACL canonique après retrait du partage, curseurs non transférables |
| Restaurer tâches et droits | Export hors ligne, empreinte, namespace neuf et reprise d'une tâche au premier checkpoint sur DynamoDB Local |
| API et worker en conteneurs | `scripts/verify_local.py` : tuer un worker vivant, redémarrer stockage/API et retrouver la même tâche |
| Préparation AWS | Bundle Linux verrouillé, synthèse CDK et assertions chiffrement, PITR, rétention, IAM, MFA/code flow, Cognito Essentials/managed login v2/branding, DLQ, limites et échecs partiels |
| Dépendances | Audit du bundle runtime avec `pip-audit`, SBOM CycloneDX généré dans `artifacts` |
| Revue finale | Sous-agent de revue après les recettes ; seuil demandé : au moins 9/10, sans défaut critique ou élevé restant |

## Portée des preuves

Les rapports JUnit, bundle Lambda, SBOM, template CDK et rapport Docker sont générés sous `artifacts`/`cdk.out`. Les essais ne font appel à aucun compte AWS ou fournisseur. DynamoDB Local ne reproduit pas toutes les garanties transactionnelles distribuées ; une injection de conflit teste le rechargement des droits. ElasticMQ et la preuve d'identité synthétique restent identifiés comme tels.

[Empreintes et résultats observés](artifact-evidence.json) lie sources, lock, image, bundle et template. [Historique des revues](review-stage1.md) conserve les constats et leurs corrections ; une note de revue ne remplace pas la qualification des services distants.

La CI est préparée dans `.github/workflows/verify.yaml`, avec actions vérifiées et fixées par commit. Une exécution locale ne prouve pas une exécution GitHub ; aucune publication ni exécution distante n'est annoncée.

## Sources techniques

Sources primaires consultées le 2026-10-05 : [transactions DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html), [access tokens Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html), [ElasticMQ](https://github.com/softwaremill/elasticmq), [publication ElasticMQ 1.7.1](https://github.com/softwaremill/elasticmq/releases/tag/v1.7.1), [source SQS pour Lambda dans CDK](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda_event_sources/SqsEventSource.html). Elles expliquent les limites et contrats utilisés ; elles ne remplacent pas une qualification AWS.
