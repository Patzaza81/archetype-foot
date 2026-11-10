"""Marqueur « donnees_du_jour » : test qui lit un fichier de data/ réécrit par les workflows (nuit). Un tel test ne doit jamais bloquer
le pipeline (voir pipeline.yml : étape bloquante = code seul, étape non bloquante mais visible = données du jour)."""
def pytest_configure(config):
    config.addinivalue_line("markers", "donnees_du_jour: lit des données générées chaque nuit (non bloquant dans le pipeline, erreur visible)")
