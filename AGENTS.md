# Koyori — Consignes pour les agents de code

## Portée et contexte

Ces consignes s’appliquent à tout le dépôt. Respecter les instructions de l’utilisateur et les conventions du projet.

Avant de travailler, lire la [note de concept](<Koyori — L’agent personnel de la maison.md>) et les entrées récentes du [journal de développement](JOURNAL.md), notamment les décisions encore ouvertes et les difficultés non résolues.

Koyori est un agent personnel pour la maison : accès vocal, mémoire, apprentissage des préférences et des procédures, coordination autonome entre services. Préserver cette ambition dans les choix d’implémentation. Distinguer explicitement la vision, les simulations et les capacités réellement opérationnelles.

## Routine de développement

- Pour toute tâche qui écrit, modifie, corrige ou relit du code, appliquer le skill `$senior-code-basics` avant de travailler. Adapter les vérifications à la portée et aux risques réels.
- Comprendre le chemin concerné avant de modifier le code. Privilégier une solution simple et les composants existants ; justifier les dépendances et abstractions ajoutées.
- Vérifier le comportement observable avec les contrôles appropriés. Pour une modification documentaire ou mécanique, relire le résultat et vérifier les références ; ne pas créer de tests artificiels.
- Ne pas présenter un test non exécuté comme réussi, une simulation comme une intégration réelle ou une hypothèse comme une décision validée.
- Mettre à jour la note de concept lorsqu’une décision change le produit, son périmètre, son architecture générale ou la stratégie du concours. Conserver les détails d’exécution dans le journal.

## Journal obligatoire

Le fichier `JOURNAL.md` constitue l’historique durable du développement. Le tenir à jour pour chaque tâche significative : implémentation, correction, revue, expérimentation, recherche technique ou décision documentaire.

1. Au démarrage, consulter l’historique pertinent pour éviter de répéter un échec ou de contredire une décision sans explication.
2. Pendant une tâche longue, consigner les décisions et les résultats aux étapes significatives. Enregistrer un blocage avant de changer de piste.
3. Avant la réponse finale, ajouter ou compléter l’entrée de la tâche, y compris si elle est interrompue ou inachevée. Décrire l’état réel et les prochaines étapes.

Utiliser des identifiants croissants (`JRN-001`, `JRN-002`, etc.) et des dates au format `AAAA-MM-JJ`, fuseau `Europe/Paris`. Ajouter les nouvelles entrées à la fin. Préserver l’historique : une décision remplacée doit renvoyer à sa nouvelle entrée ; une correction factuelle doit être signalée comme telle. Compléter une entrée en cours est autorisé.

Documenter tous les choix significatifs et les difficultés utiles à la reprise du travail, avec une justification concise et factuelle. Ne pas transcrire le raisonnement interne ni accumuler des sorties brutes de commandes. Regrouper les petites opérations liées dans une même entrée.

### Structure de chaque entrée

- **Objectif et état** : demande traitée ; terminé, partiel ou bloqué.
- **Réalisations** : comportement obtenu, fichiers concernés, éléments simulés le cas échéant.
- **Choix et raisons** : décision, contraintes, alternatives réellement considérées, compromis et conséquences. Distinguer les propositions des décisions prises.
- **Difficultés et résolution** : symptôme, contexte, tentatives utiles, cause confirmée ou hypothèse, solution ou blocage restant.
- **Ce qui a bien fonctionné** : pratique, outil ou approche réutilisable, avec un résultat observé.
- **Vérifications** : commande ou contrôle réalisé, résultat et portée ; contrôles non exécutés et motif. Référencer les preuves pertinentes.
- **Retour sur les outils** : outils, API ou SDK effectivement utilisés, leur utilité et l’expérience observée.
- **Suite** : questions ouvertes, limites, risques concrets et prochaine action.

Indiquer « aucun problème observé » ou « non applicable » lorsqu’une rubrique ne comporte rien à signaler. Ne pas inventer d’incident, d’alternative étudiée, de mesure, de test ou de retour utilisateur pour remplir le journal.

## Retours exploitables pour le hackathon

La stratégie retenue est **Alexa+ comme piste principale, avec les deux mini-défis AWS Builder et Open Source**. Les conditions et sources sont dans la note de concept. Cette intention ne signifie pas que l’inscription ou l’admissibilité sont acquises.

Pour chaque outil, API ou SDK effectivement utilisé, conserver progressivement : usage réel, mise en route, réussites, limites observées et volonté de le réutiliser avec justification. Référencer une entrée existante lorsque le retour n’a pas changé.

Pour chaque friction significative, documenter :

- outil et version lorsqu’ils sont connus ;
- tâche tentée et étapes permettant de reproduire le problème ;
- résultat attendu et résultat observé ;
- gravité et impact concret ;
- contournement essayé, son résultat et l’état actuel ;
- suggestion d’amélioration actionnable.

Pour une demande de fonctionnalité, indiquer le besoin, son utilité pour Koyori et sa priorité : critique, importante ou souhaitable.

**AWS Builder** : relier chaque intégration retenue à son usage réel, aux fichiers concernés et à une validation. Documenter aussi les coûts observés et les ressources encore actives, lorsque cela s’applique. Ne pas attribuer à AWS une capacité seulement envisagée.

**Open Source** : identifier la contribution complémentaire, son utilité, la licence choisie, les dates, le dépôt et l’URL de contribution lorsqu’ils existent, ainsi que les validations réalisées. Distinguer travail local, publication, pull request et fusion. Ne pas assimiler automatiquement l’ouverture du dépôt principal à la contribution supplémentaire demandée.

Écrire le journal en français. Lors de la préparation de la candidature, produire une synthèse en anglais fondée sur ces observations. Ne pas inventer des retours après coup pour améliorer le dossier.

## Qualité des traces

- Relier les observations aux fichiers, tickets, commits, documentations ou résultats disponibles. Privilégier les chemins relatifs dans les documents du dépôt.
- Séparer faits observés, estimations et hypothèses. Dater les références externes susceptibles d’évoluer.
- Ne jamais enregistrer de secrets, jetons, identifiants de connexion ou données personnelles dans le journal. Masquer les valeurs sensibles dans les messages d’erreur et exemples.
- Documenter les limites utiles à la reprise du travail sans reproduire des conversations privées ou des journaux complets.
- Dans la réponse finale, résumer le résultat, les vérifications et les limites, puis signaler l’entrée du journal mise à jour.
