# Automatisation locale du coupon BetPawa

## But et limites

Ce composant ouvre un vrai navigateur Chromium contrôlé par Playwright sur l'ordinateur de l'utilisateur. Il lit les tickets produits par ARCHETYPE, ouvre les événements BetPawa connus et clique uniquement sur une cote dont le marché et l'issue peuvent être identifiés sans ambiguïté.

- Le mode par défaut est une prévisualisation sans navigateur ni clic.
- Les clics nécessitent l'option --click.
- Le navigateur est visible et utilise un profil local persistant : l'utilisateur se connecte lui-même si nécessaire.
- Le script ne lit pas les mots de passe, ne saisit aucune mise et ne clique jamais sur un bouton de confirmation ou de placement de pari.
- Les marchés non pris en charge, les liens invalides et les correspondances ambiguës provoquent un arrêt sans clic pour la sélection concernée.
- Les cotes peuvent changer. Le coupon doit être inspecté manuellement avant toute décision.
- Ce script n'a pas encore été validé contre toutes les variantes réelles de l'interface BetPawa. Un échec de reconnaissance doit être traité comme un blocage, pas contourné en choisissant une autre cote.

Le profil Chromium contient potentiellement une session BetPawa. Il est stocké dans .local/betpawa-profile/, exclu du dépôt. Ne partagez pas ce dossier.

## Prérequis

Ordinateur sous Windows, macOS ou Linux avec Python 3.10+ et accès Internet. Cette automatisation Playwright ne s'exécute pas directement dans Safari sur iPhone.

Depuis la racine du dépôt, installer les dépendances :

    python -m pip install playwright
    python -m playwright install chromium

## Prévisualisation

    python tools/betpawa_local_runner.py

La commande affiche les tickets encore valides et compatibles avec la passerelle de validation, sans ouvrir le navigateur ni effectuer de clic. Le script recalcule le statut depuis data/tickets.json : un ticket expiré ou rejeté ne peut pas être choisi.

## Exécution réelle

D'abord, inspecter le plan proposé. Puis, après avoir choisi l'identifiant affiché :

    python tools/betpawa_local_runner.py --ticket-id AX-IDENTIFIANT
    python tools/betpawa_local_runner.py --ticket-id AX-IDENTIFIANT --click

Avec --click, il faut taper exactement CLICK SELECTIONS. Le navigateur s'ouvre, puis l'utilisateur peut se connecter manuellement. Le script affiche chaque marché et la cote actuelle avant le clic. Après chaque sélection, il demande de vérifier le coupon avant de continuer. Tapez STOP pour interrompre la séquence.

À la fin, le coupon reste affiché dans le navigateur. Contrôlez chaque équipe, chaque marché, chaque cote et le nombre total de sélections. La validation ou la soumission du pari reste entièrement manuelle.

## Dépannage

- Marché non pris en charge : le libellé ne possède pas encore de correspondance sûre. Ne pas élargir les sélecteurs au hasard.
- 0 contrôle : BetPawa a peut-être changé son interface, la page n'a pas fini de charger, le marché est indisponible ou le site bloque l'automatisation.
- Plusieurs contrôles : le script refuse de deviner. Inspecter la page puis ajouter une correspondance ciblée et testée.
- Si la cote source et la cote visible diffèrent, le script l'indique. La cote affichée par BetPawa est celle qui serait ajoutée ; vérifiez-la avant de poursuivre.

Le générateur de tickets, le moteur statistique et le pipeline quotidien ne sont pas modifiés par cet outil.
