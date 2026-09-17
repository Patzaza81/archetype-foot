"""Tests du disjoncteur d'intégrité (archetype_model/audit/circuit_breaker.py).

Vérifie que le module est bien PASSIF (ne modifie jamais les fenêtres ou
les cotes reçues) et que les trois motifs de dégradation se déclenchent
exactement aux bornes documentées, ni avant ni après.
"""

from archetype_model.audit import circuit_breaker as cb


def _fenetre(n_brut, n_utilisable):
    return {
        "n_brut": n_brut,
        "matchs_retenus": [{"buts_marques": 1, "buts_encaisses": 1}] * n_utilisable,
    }


# ----------------------------------------------------------------------
# ECHANTILLON_INSUFFISANT
# ----------------------------------------------------------------------

def test_echantillon_insuffisant_sous_le_seuil():
    verdict = cb.evalue_integrite(_fenetre(4, 4), _fenetre(10, 10))
    assert verdict["statut"] == cb.STATUT_INSUFFICIENT_DATA
    motifs = {m["motif"] for m in verdict["motifs"]}
    assert cb.MOTIF_ECHANTILLON_INSUFFISANT in motifs


def test_echantillon_juste_au_seuil_est_accepte():
    """N_MIN_ECHANTILLON = 5 -- 5 doit passer (limite documentée dans
    data.validation.N_MIN_UTILISABLE : N < 5 rejeté, 5 <= N accepté)."""
    verdict = cb.evalue_integrite(_fenetre(5, 5), _fenetre(10, 10))
    assert verdict["statut"] == cb.STATUT_OK
    assert verdict["motifs"] == []


# ----------------------------------------------------------------------
# TAUX_DONNEES_MANQUANTES_ELEVE
# ----------------------------------------------------------------------

def test_taux_manquant_au_dessus_du_seuil_est_corrompu():
    # 20 bruts, seulement 15 utilisables -> 25% manquant > 15%
    verdict = cb.evalue_integrite(_fenetre(20, 15), _fenetre(20, 20))
    assert verdict["statut"] == cb.STATUT_DATA_CORRUPTED
    motifs = {m["motif"] for m in verdict["motifs"]}
    assert cb.MOTIF_TAUX_MANQUANT_ELEVE in motifs


def test_taux_manquant_juste_sous_le_seuil_est_ok():
    # 20 bruts, 17 utilisables -> 15% pile, pas strictement > 15%
    verdict = cb.evalue_integrite(_fenetre(20, 17), _fenetre(20, 20))
    assert verdict["statut"] == cb.STATUT_OK


def test_fenetre_sans_n_brut_ne_plante_pas():
    """n_brut à 0 : rien à mesurer, jamais une division par zéro ni un
    taux inventé."""
    verdict = cb.evalue_integrite(_fenetre(0, 0), _fenetre(10, 10))
    assert verdict["statut"] == cb.STATUT_INSUFFICIENT_DATA  # échantillon 0 < 5
    motifs = {m["motif"] for m in verdict["motifs"]}
    assert cb.MOTIF_TAUX_MANQUANT_ELEVE not in motifs


# ----------------------------------------------------------------------
# VARIATION_COTE_BRUTALE
# ----------------------------------------------------------------------

def test_premiere_vue_d_une_cote_n_est_jamais_une_variation(tmp_path):
    fichier = str(tmp_path / "snapshots.json")
    motif = cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 1.50, fichier)
    assert motif is None


def test_variation_au_dela_du_seuil_est_detectee(tmp_path):
    fichier = str(tmp_path / "snapshots.json")
    cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 1.50, fichier)
    # 1.50 -> 1.80 = +20% > 15%
    motif = cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 1.80, fichier)
    assert motif is not None
    assert motif["motif"] == cb.MOTIF_VARIATION_COTE
    assert motif["variation"] > cb.SEUIL_VARIATION_COTE


def test_variation_sous_le_seuil_nest_pas_signalee(tmp_path):
    fichier = str(tmp_path / "snapshots.json")
    cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 1.50, fichier)
    # 1.50 -> 1.60 = +6.7%, sous 15%
    motif = cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 1.60, fichier)
    assert motif is None


def test_cote_invalide_nest_jamais_enregistree(tmp_path):
    fichier = str(tmp_path / "snapshots.json")
    motif = cb.verifie_variation_cote("match_1", ("1x2", "domicile"), None, fichier)
    assert motif is None
    motif = cb.verifie_variation_cote("match_1", ("1x2", "domicile"), 0, fichier)
    assert motif is None
    # aucun fichier ne doit avoir été créé pour une cote invalide
    import os
    assert not os.path.exists(fichier)


def test_evalue_integrite_integre_la_variation_de_cote(tmp_path):
    fichier = str(tmp_path / "snapshots.json")
    fa, fb = _fenetre(10, 10), _fenetre(10, 10)

    # premier scan : rien à comparer, doit rester OK
    verdict_1 = cb.evalue_integrite(
        fa, fb, match_id="match_1", cotes={("1x2", "domicile"): 1.50},
        fichier_snapshots=fichier,
    )
    assert verdict_1["statut"] == cb.STATUT_OK

    # second scan, cote très différente -> DATA_CORRUPTED
    verdict_2 = cb.evalue_integrite(
        fa, fb, match_id="match_1", cotes={("1x2", "domicile"): 2.00},
        fichier_snapshots=fichier,
    )
    assert verdict_2["statut"] == cb.STATUT_DATA_CORRUPTED


# ----------------------------------------------------------------------
# Passivité : les entrées ne sont JAMAIS modifiées par ce module.
# ----------------------------------------------------------------------

def test_le_module_ne_modifie_jamais_les_fenetres_recues():
    fa = _fenetre(3, 3)
    fb = _fenetre(10, 10)
    fa_avant = dict(fa)
    fb_avant = dict(fb)
    cb.evalue_integrite(fa, fb)
    assert fa == fa_avant
    assert fb == fb_avant


def test_le_module_ne_touche_jamais_les_seuils_de_production():
    """Garde-fou explicite : ce module n'importe RIEN depuis
    signals.convergence ni main.py (SEUIL_PEAGE1, COTE_MIN/MAX,
    EDV_MIN_*) -- ses propres seuils (SEUIL_TAUX_MANQUANT,
    SEUIL_VARIATION_COTE, N_MIN_ECHANTILLON) sont indépendants."""
    import archetype_model.audit.circuit_breaker as module
    noms_importes = dir(module)
    assert "SEUIL_PEAGE1" not in noms_importes
    assert "COTE_MIN" not in noms_importes
    assert "COTE_MAX" not in noms_importes
