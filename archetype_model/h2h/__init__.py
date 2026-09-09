"""archetype_model.h2h — module indépendant (v3 §10). Paliers de
fiabilité (h2h_stats.py) et statut corrobore/contredit/neutre par
marché (h2h_markets.py). Ne modifie JAMAIS λ (invariant explicite du
v3, page 1) -- lu uniquement en aval, au moment du filtre de
candidature et de la sélection (§12).
"""
