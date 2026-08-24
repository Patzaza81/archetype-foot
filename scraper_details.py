name: Pipeline quotidien Archetype Foot

on:
  schedule:
    - cron: "0 7 * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Installer les dépendances
        run: pip install requests beautifulsoup4 pandas lxml

      - name: Lancer le scraper matchendirect (dump brut pour diagnostic)
        run: |
          python scraper.py --sortie /tmp/matches_debug.json
          echo "--- Aperçu des matchs extraits (matchendirect) ---"
          cat /tmp/matches_debug.json

      - name: Lancer le scraper d'enrichissement (classement, H2H, cotes)
        run: |
          python -c "
          from scraper_details import recupere_classement, recupere_20_derniers_resultats, recupere_h2h, recupere_cotes_marches, recupere_details_match
          import json

          url_classement = 'https://www.matchendirect.fr/classement-foot/france/classement-ligue-1.html'
          url_match_defaut = 'https://www.matchendirect.fr/live-score/fulham-chelsea_3zanwwudms3ktzt5y7te4auqc.html'
          url_faf = url_match_defaut + '?p=face-a-face'

          try:
              details = recupere_details_match(url_match_defaut)
              print('--- details_match (résout le blocage URL statistique) : OK ---')
              print(json.dumps(details, indent=2, ensure_ascii=False))
              url_stat = details['url_statistique'] or 'https://www.matchendirect.fr/statistique/chelsea-contre-fulham.html'
          except Exception as e:
              print('--- details_match : ÉCHEC ---', e)
              url_stat = 'https://www.matchendirect.fr/statistique/chelsea-contre-fulham.html'

          for nom, fn, args in [
              ('classement', recupere_classement, (url_classement,)),
              ('20 derniers resultats', recupere_20_derniers_resultats, (url_stat, 'Chelsea', 'Fulham')),
              ('H2H', recupere_h2h, (url_faf,)),
              ('cotes', recupere_cotes_marches, (url_faf,)),
          ]:
              try:
                  resultat = fn(*args)
                  print(f'--- {nom} : OK ---')
                  print(json.dumps(resultat, indent=2, ensure_ascii=False)[:1500])
              except Exception as e:
                  print(f'--- {nom} : ÉCHEC ---', e)
          "
        continue-on-error: true

      - name: Lancer le pipeline complet
        run: python run_pipeline.py

      - name: Commit et push du résultat
        run: |
          git config user.name "archetype-foot-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data.json
          git diff --staged --quiet || git commit -m "Mise à jour quotidienne des données"
          git pull --rebase origin main
          git push
