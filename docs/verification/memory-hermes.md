# Vérification de la mémoire inspirée de Hermes

Travail terminé le 2026-10-06, base `e0f967b`, branche `gus-rlin/koyori-memory-hermes`, worktree géré `koyori-memory-hermes/Koyori`. [Contrats et références Hermes datées](../memory-hermes.md). Synthèse d'exécution et revues conservées dans [JRN-028](../../JOURNAL.md) ; les rapports bruts restent sous `artifacts/` ignoré.

## Preuves finales et contrôles intermédiaires

| Contrôle | Résultat observé | Portée |
| --- | --- | --- |
| Suite cumulative avec `KOYORI_INTEGRATION=1`, DynamoDB Local 8910 et ElasticMQ 9354 | **344 réussites, zéro échec/erreur/exclusion**, 143,81 s | Domaine, SDK interceptés, intégrations émulateurs et assertions CDK/IAM |
| Ruff check / format | Réussite, 108 fichiers Python formatés | `src tests scripts infrastructure` |
| Synthèse CDK et activation par contexte booléen/CLI | Réussite ; 14 Lambdas, activation exacte `True` ou `"true"` | Aucune connexion à un compte AWS |
| Bundle Lambda Linux verrouillé | Reconstruit, 50 modules applicatifs identiques au checkout | Empreinte complète dans le rapport de livraison |
| Images locale et AgentCore AMD64 | Reconstruites, sources identiques, imports voix/MCP/SDK/CRT réussis | Aucun appel fournisseur |
| Image AgentCore ARM64 | Construite et inspectée `arm64`, exécution non qualifiée | Import refusé `exec format error` sur ce poste, limite déjà décrite en JRN-024 |
| Audit des dépendances du bundle | Aucune vulnérabilité connue signalée | `pip_audit`, SBOM CycloneDX locale |
| Cinq recettes Docker sur l'image finale | **PASS** pour les étapes 1, 2, 3, 4 et mémoire | Projet `koyori-memory-hermes`, fixtures et planification/commerce/apprentissage simulés |

Empreinte commune des 50 sources applicatives du checkout et des deux images AMD64 : `8d31edd3a8b164a0f1de965efe365d30554f5750ab127d82e459ec150835b0eb`. Elle porte sur les modules Python et ne remplace pas l'empreinte complète de livraison. Les rapports bruts de tests et SBOM restent dans `artifacts/`, ignoré.

[Empreintes de livraison](artifact-evidence.json) : source `c41d70cc4bbbf41d1b27eb74d57d96cbfc6c297ddb65bc8541abe5caa442a6f4`, lock, bundle Lambda, template CDK, image runtime et contrôles des cinq recettes. `record_evidence.py --check-source` confirme la correspondance avec le checkout. [Manifeste compatible](deployment-manifest.json) préparé, état `PREPARED_NOT_DEPLOYED`, architecture ARM64 et qualifications distantes conservées comme non qualifiées. Workflow GitHub non exécuté par cette tâche.

Recettes renouvelées séquentiellement avec `KOYORI_MEMORY_ENV=1` : `verify_local.py` (crash/reprise), `verify_stage2.py` (mémoire sourcée et réconciliation commerciale), `verify_stage3.py` (coordination, préférence acceptée, routine, notification), `verify_stage4.py` (MCP/REST/voix, reconnexion et rattrapage), `verify_memory.py` (core distinct du jour, archive ancienne/accents, outil MCP commun, absence de mémorisation avant acceptation et effacement complet des propositions). Résultats respectifs dans `artifacts/local-recovery.json`, `stage2-recovery.json`, `stage3-recovery.json`, `stage4-recovery.json` et `memory-hermes.json`, repris sans textes ni identifiants de fixture dans le rapport durable.

Les quatre anciens scripts ont été corrigés après les 344 tests uniquement pour choisir leur fixture ; aucun runtime ni test métier n'a changé ensuite. Ruff et les cinq recettes ont été renouvelés sur cet état final. 78 références Markdown locales contrôlées, puis les liens de preuve ajoutés relus. Le checkout principal est resté propre sur `e0f967b`.

- État initial : 40 tests ciblés réussis, dépôt propre.
- 48 contrôles ciblés nouveaux/existants mémoire, apprentissage et confidentialité réussis en 10,01 s.
- 6 intégrations DynamoDB Local mémoire/canaux/restauration réussies en 13,75 s.
- 77 contrôles mémoire/planification/SDK réussis en 20,33 s après ajout des gardes de données envoyées au planificateur.

Ces séries se recouvrent ; elles ne s'ajoutent pas aux 344 contrôles finaux. Première suite cumulative : 334 réussites, trois échecs (timeout d'une assertion ancienne, contexte vide annoncé incomplet, contrat des échanges explicitement référencés perdu). Corrigés et revérifiés, puis 340 réussites ; les quatre nouvelles régressions de la troisième revue portent la dernière suite à 344. Warning Starlette/httpx préexistant uniquement. Aucun résultat distant n'est inféré de ces chiffres.

## Couverture observable

[tests/test_memory_hermes.py](../../tests/test_memory_hermes.py) : préférence après plus de 500 échanges, core distinct du jour, clé explicite, archive ancienne, Unicode décomposé/accents/casse, AND, curseurs privés/partagés, buffer non consommé, page vide avec continuation à 500, jour DST de 25 heures, réindexation interrompue puis correction/purge, budgets multioctets et garde d'effacement sur core seul. La régression de frontière mesure les nouvelles clés manquantes après chaque retrait du payload.

[tests/test_auto_learning.py](../../tests/test_auto_learning.py) : absence de souvenir avant acceptation, trois propositions atomiques et notifications groupées, déduplication et refus, corrections avec partage/expiration conservés, courses sur source/cible nouvelle ou supprimée/effacement, lectures et export expurgés y compris après refus, deux requêtes à vie, quota quotidien commun aux foyers d'une personne, éligibilité sept jours, crash après réservation, reprise de bail, concurrence et goal `SUCCEEDED`, y compris checkpoint confirmé pendant effacement. Adaptateur Strands/Botocore réel avec HTTP intercepté : sortie typée, réparation invalide, throttling, absence de retries cachés et fragments privés exclus des logs. Fournisseur distant non utilisé.

[tests/test_memory_hermes_integration.py](../../tests/test_memory_hermes_integration.py) : index et suppressions conditionnelles dans DynamoDB Local, pagination sans perte, acquisition concurrente et publication atomique de trois propositions, sauvegarde 1.0 antérieure à un effacement, registre 2.0 et fence absent inséré, anciennes propositions/jobs non réapparus, objectif `SUCCEEDED` conservé sans réanalyse, reconstruction des seuls survivants avant levée locale contrôlée de quarantaine.

[tests/test_memory_hermes_infrastructure.py](../../tests/test_memory_hermes_infrastructure.py) : rôle modèle séparé sans credentials, exécution ou index vectoriel ; mode désactivé par défaut et activation explicite booléenne/CLI ; suppression limitée aux dérivés lexicaux ; lecture/conditionnement du fence de restauration. La synthèse et ces assertions ne prouvent pas l'exécution IAM sur AWS.

## Revues indépendantes

Plan : trois passages, 8,3/10 puis 9/10 et 9/10, avant implémentation.

Code, premier passage : **7,5/10 provisoire**. Défauts confirmés : booléen d'effacement absent, état commercial erroné, migration sans compteur lexical, exposition d'une proposition aux révisions périmées, cible déterminée après génération. Corrections et régressions ajoutées ; la note du plan ne vaut pas celle du code.

Code, deuxième passage : **8,5/10**. Checkpoint final d'un objectif confirmé pendant effacement et lecture d'une proposition refusée dont la cible a changé : corrigés avec régressions. Troisième passage : **8,8/10**, 40 contrôles indépendants réussis ; recalcul des clés manquantes après retrait et activation CDK par contexte CLI à corriger. Les deux corrections sont faites ; quatre régressions de budget et synthèse passent en 32,67 s.

Code, quatrième passage : **9/10, aucun défaut bloquant ni constat matériel restant identifié**. Le reviewer a personnellement renouvelé `git diff --check` et la régression du budget ; sa passe précédente couvre 40 tests d'apprentissage, mémoire et restauration. Les trois synthèses paramétrées ont été exécutées par l'agent principal et relues par le reviewer. La note porte sur l'implémentation locale ; l'agent principal a confirmé ensuite les 344 tests cumulatifs et les cinq recettes. Aucun fichier modifié par le reviewer.

Lecture complémentaire des derniers scripts : **9/10 maintenu**. Une recette avait sélectionné un nouveau foyer de qualification où Sam n'est pas membre (403), au lieu de tester l'objectif privé du foyer synthétique A (404). Le helper commun `demo_household` choisit maintenant l'unique fixture du bootstrap, indépendamment de l'ordre des foyers, et échoue si absente ou ambiguë. Les assertions et droits sont conservés. Le reviewer a exécuté `git diff --check` et relu ces quatre usages ; renouvellement des recettes effectué par l'agent principal.

## Limites de qualification

La démonstration utilise des données synthétiques, un commerce simulé et un filtre/apprentissage local FR/EN limité. Nova réel, exactitude des inférences, IAM exécuté, GSI distant, coûts, PITR AWS, voix réelle et raccordement frontend restent non qualifiés. L'activation automatique AWS est explicite ; le modèle ne reçoit aucun outil d'exécution. Aucun push, déploiement, achat, coût AWS observé ni contribution Open Source complémentaire publié.

## Publication ultérieure

Le 2026-10-06, à la demande de l'utilisateur, la branche est poussée et la [PR #5](https://github.com/gus-rlin/Koyori/pull/5) ouverte vers `main` ; actions consignées dans JRN-029. La PR inclut la base intégrée `e0f967b`, dont l'interface compagnon héritée, en plus du commit mémoire `d5b5015`. L'état « aucun push » ci-dessus décrit la livraison locale précédente. Les validations et empreintes locales restent celles de JRN-028 ; les checks GitHub sont déclenchés, leur résultat final reste à confirmer. Aucun code modifié ni fusion effectuée lors de cette publication.
