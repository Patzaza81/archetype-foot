"""
archetype_model/poisson/lambda_estimators.py — Multi-λ, quatre scénarios
(ARCHETYPE_FOOT v3, §6), formules verrouillées (aucun débat à rouvrir) :

Pour un match A (domicile) contre B (extérieur) :

    λ_A^offensif = GF_{A,domicile}      λ_B^offensif = GF_{B,extérieur}
    λ_A^défensif = GA_{B,extérieur}     λ_B^défensif = GA_{A,domicile}
    λ_A^contextuel = (λ_A^offensif + λ_A^défensif) / 2   (idem B)
    λ_A^global = (GF_{A,global} + GA_{B,global}) / 2      (idem B)

Point à ne pas confondre pour λ_global (piège facile) : λ_A^global
mélange l'ATTAQUE globale de A avec la DÉFENSE globale de B (pas la
défense de A) -- même logique croisée attaque-propre/défense-adverse
que les scénarios offensif/défensif, juste appliquée aux stats "toutes
compétitions confondues" plutôt qu'aux stats domicile/extérieur.

Fonction PURE, agnostique de la source des GF/GA : prend des moyennes
déjà calculées (ex. via statistics.team_stats.stats_offensives(...)
["moyenne"]), ne fait aucun accès réseau, aucune connaissance de
data.loader. L'orchestration (aller chercher les stats des deux
équipes d'un match réel) est laissée à un futur main.py, non codé ici.

Aucune pondération entre les 4 scénarios (v3 §6, dernier paragraphe) --
chacun reste séparé, consommé indépendamment par distribution.py et
markets.py (pas encore codés).

GESTION DE L'ABSENT : n'importe quel GF/GA d'entrée peut être None (ex.
équipe INSUFFISANTE au sens de data.validation, ou stats globales pas
encore disponibles -- voir note ouverte dans statistics/team_stats.py).
Un None ne doit JAMAIS crasher ni se propager silencieusement en tant
que faux zéro : le scénario concerné devient None, isolément, sans
affecter les autres scénarios de la MÊME équipe ni ceux de l'AUTRE
équipe.
"""


def _moyenne_sure(*valeurs):
    """Moyenne arithmétique, ou None si UNE SEULE des valeurs est None
    -- ne jamais faire semblant qu'une valeur manquante vaut 0."""
    if any(v is None for v in valeurs):
        return None
    return sum(valeurs) / len(valeurs)


def estime_lambdas(
    gf_a_domicile, ga_a_domicile, gf_a_global, ga_a_global,
    gf_b_exterieur, ga_b_exterieur, gf_b_global, ga_b_global,
):
    """
    Calcule les 4 scénarios λ pour les deux équipes d'un match (A à
    domicile, B à l'extérieur), à partir de moyennes GF/GA déjà
    calculées en amont (statistics.team_stats).

    Retourne :
        {
            "A": {"offensif": ..., "defensif": ..., "contextuel": ..., "global": ...},
            "B": {"offensif": ..., "defensif": ..., "contextuel": ..., "global": ...},
        }
    Toute valeur peut être None si une entrée nécessaire était None --
    jamais une exception.
    """
    lambda_a_offensif = gf_a_domicile
    lambda_b_offensif = gf_b_exterieur

    lambda_a_defensif = ga_b_exterieur
    lambda_b_defensif = ga_a_domicile

    lambda_a_contextuel = _moyenne_sure(lambda_a_offensif, lambda_a_defensif)
    lambda_b_contextuel = _moyenne_sure(lambda_b_offensif, lambda_b_defensif)

    # ATTENTION à l'ordre : A croise avec la défense GLOBALE de B, B
    # croise avec la défense GLOBALE de A -- jamais la sienne propre.
    lambda_a_global = _moyenne_sure(gf_a_global, ga_b_global)
    lambda_b_global = _moyenne_sure(gf_b_global, ga_a_global)

    return {
        "A": {
            "offensif": lambda_a_offensif,
            "defensif": lambda_a_defensif,
            "contextuel": lambda_a_contextuel,
            "global": lambda_a_global,
        },
        "B": {
            "offensif": lambda_b_offensif,
            "defensif": lambda_b_defensif,
            "contextuel": lambda_b_contextuel,
            "global": lambda_b_global,
        },
    }
