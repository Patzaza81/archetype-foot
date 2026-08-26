name: Test scraping Betpawa (ponctuel)

# Déclenchement UNIQUEMENT manuel -- pas de "schedule", ce n'est pas un
# pipeline régulier, juste un test à lancer une fois pour répondre à une
# question précise (26/08 : une requête HTTP classique obtient-elle le
# même contenu que l'outil de récupération de Claude sur betpawa.cm ?).
on:
  workflow_dispatch: {}

jobs:
  test-scraping:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Installer les dépendances
        run: pip install requests

      - name: Lancer le test
        run: python test_scraping_betpawa.py
