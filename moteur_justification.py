"""
moteur_justification.py

MOTEUR DE JUSTIFICATION — Archetype Foot
========================================

Rôle
----
Ce module explique un pronostic DEJA VALIDÉ par le système principal.

Il ne choisit pas le pronostic.
Il ne calcule pas la probabilité du modèle.
Il ne calcule pas l'EV.
Il ne calcule pas Kelly.
Il ne compare pas les marchés.
Il ne filtre pas les marchés.
Il ne modifie jamais le pronostic reçu.

Il reçoit :
    1. un pronostic déjà validé ;
    2. les valeurs déjà calculées par le moteur principal ;
    3. des statistiques factuelles déjà préparées et vérifiées.

Il produit :
    - un bloc "Pourquoi ce pronostic ?" ;
    - 2 à 3 justifications maximum ;
    - des statistiques correctement formulées ;
    - une indication de contexte/surface de données.

IMPORTANT
---------
Les statistiques utilisées ici doivent provenir d'une source réelle.
Aucune valeur ne doit être inventée pour compléter une justification.

Pour respecter strictement le contrat "ne calcule rien",
les ratios et moyennes doivent être fournis à ce module déjà calculés,
par exemple :

    {
        "type": "frequence_marche",
        "contexte": "domicile",
        "libelle": "Over 2.5",
        "occurrences": 7,
        "total": 8,
        "pourcentage": 87.5,
        "source": "historique_equipe_domicile",
        "verifie": True
    }

Le moteur formate et sélectionne ces faits explicatifs.
Il ne fabrique pas le 87.5 % à partir de 7/8.

Version : 1.0
"""


from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 1. TYPES DE PREUVES AUTORISÉS
# ---------------------------------------------------------------------------

TYPE_FREQUENCE_MARCHE = "frequence_marche"
TYPE_MOYENNE_BUTS_MARQUES = "moyenne_buts_marques"
TYPE_MOYENNE_BUTS_TOTAUX = "moyenne_buts_totaux"
TYPE_BTTS = "frequence_btts"
TYPE_CLEAN_SHEET = "frequence_clean_sheet"
TYPE_SANS_BUT = "frequence_sans_but"
TYPE_SERIE_RESULTAT = "serie_resultat"
TYPE_H2H_RESULTAT = "h2h_resultat"
TYPE_H2H_BUTS = "h2h_buts"
TYPE_H2H_MARCHE = "h2h_marche"
TYPE_H2H_SERIE = "h2h_serie"
TYPE_HANDICAP = "frequence_handicap"
TYPE_PARITE = "frequence_parite"
TYPE_SCORE_EXACT = "frequence_score_exact"
TYPE_STAT_REMARQUABLE = "stat_remarquable"


# ---------------------------------------------------------------------------
# 2. STRUCTURES DE DONNÉES
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PronosticValide:
    """
    Pronostic déjà choisi par le système principal.

    Ces valeurs sont LUES uniquement.
    """

    marche: str
    probabilite_modele: Optional[float] = None
    cote: Optional[float] = None
    ev: Optional[float] = None
    verdict: Optional[str] = None


@dataclass(frozen=True)
class PreuveStatistique:
    """
    Fait statistique déjà préparé et vérifié.

    Le moteur ne recalcule pas 'pourcentage'.
    Il affiche la valeur reçue.
    """

    type: str
    contexte: str
    libelle: str

    occurrences: Optional[int] = None
    total: Optional[int] = None
    pourcentage: Optional[float] = None

    moyenne: Optional[float] = None
    valeur: Optional[str] = None

    source: Optional[str] = None
    verifie: bool = False

    equipe: Optional[str] = None
    adversaire: Optional[str] = None

    priorite: int = 999
    texte: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Justification:
    """
    Une phrase explicative affichable.
    """

    texte: str
    type: str
    contexte: str
    source: Optional[str] = None


@dataclass(frozen=True)
class ResultatJustification:
    """
    Résultat final du moteur.

    Le champ 'pronostic' est exactement celui reçu en entrée.
    """

    pronostic: PronosticValide
    titre: str
    justifications: List[Justification]
    solidite_donnees: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. NOMENCLATURE DES MARCHÉS DU SYSTÈME
# ---------------------------------------------------------------------------

MARCHES = {
    "1X2",
    "DOUBLE_CHANCE",
    "BTTS",
    "OVER_UNDER_MATCH",
    "OVER_UNDER_EQUIPE",
    "HANDICAP",
    "PAIR_IMPAIR",
    "CLEAN_SHEET",
    "SANS_BUT",
    "SCORE_EXACT",
    "NOMBRE_EXACT_BUTS",
}


# ---------------------------------------------------------------------------
# 4. PRIORITÉS DES JUSTIFICATIONS
#
# Ces priorités servent UNIQUEMENT à choisir les faits à afficher.
# Elles ne servent jamais à choisir un pari.
# ---------------------------------------------------------------------------

PRIORITES = {
    "OVER_UNDER_MATCH": [
        TYPE_FREQUENCE_MARCHE,
        TYPE_MOYENNE_BUTS_TOTAUX,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "OVER_UNDER_EQUIPE": [
        TYPE_FREQUENCE_MARCHE,
        TYPE_MOYENNE_BUTS_MARQUES,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "BTTS": [
        TYPE_BTTS,
        TYPE_MOYENNE_BUTS_TOTAUX,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "1X2": [
        TYPE_SERIE_RESULTAT,
        TYPE_H2H_RESULTAT,
        TYPE_STAT_REMARQUABLE,
    ],
    "DOUBLE_CHANCE": [
        TYPE_SERIE_RESULTAT,
        TYPE_H2H_RESULTAT,
        TYPE_STAT_REMARQUABLE,
    ],
    "HANDICAP": [
        TYPE_HANDICAP,
        TYPE_SERIE_RESULTAT,
        TYPE_H2H_RESULTAT,
        TYPE_STAT_REMARQUABLE,
    ],
    "CLEAN_SHEET": [
        TYPE_CLEAN_SHEET,
        TYPE_SANS_BUT,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "SANS_BUT": [
        TYPE_SANS_BUT,
        TYPE_CLEAN_SHEET,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "PAIR_IMPAIR": [
        TYPE_PARITE,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "SCORE_EXACT": [
        TYPE_SCORE_EXACT,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
    "NOMBRE_EXACT_BUTS": [
        TYPE_FREQUENCE_MARCHE,
        TYPE_MOYENNE_BUTS_TOTAUX,
        TYPE_H2H_MARCHE,
        TYPE_STAT_REMARQUABLE,
    ],
}


# ---------------------------------------------------------------------------
# 5. IDENTIFICATION DU TYPE DE MARCHÉ
# ---------------------------------------------------------------------------

def identifie_type_marche(marche: str) -> str:
    """
    Transforme le libellé du pronostic en famille de marché.

    Cette fonction n'évalue pas le pronostic.
    Elle sert uniquement à savoir quelles statistiques descriptives
    sont pertinentes pour l'affichage.
    """

    texte = marche.lower()

    if texte.startswith("1x2"):
        return "1X2"

    if texte.startswith("double chance"):
        return "DOUBLE_CHANCE"

    if texte.startswith("btts"):
        return "BTTS"

    if "handicap" in texte:
        return "HANDICAP"

    if "pair" in texte or "impair" in texte:
        return "PAIR_IMPAIR"

    if "score exact" in texte:
        return "SCORE_EXACT"

    if "nombre exact" in texte:
        return "NOMBRE_EXACT_BUTS"

    if "cage inviolée" in texte or "cages inviolées" in texte:
        return "CLEAN_SHEET"

    if "sans but" in texte:
        return "SANS_BUT"

    if "plus de" in texte or "moins de" in texte:
        if "domicile" in texte or "extérieur" in texte:
            return "OVER_UNDER_EQUIPE"
        return "OVER_UNDER_MATCH"

    return "STAT_REMARQUABLE"


# ---------------------------------------------------------------------------
# 6. CONTRÔLES DE VALIDITÉ
# ---------------------------------------------------------------------------

def preuve_utilisable(preuve: PreuveStatistique) -> bool:
    """
    Une preuve est affichable seulement si elle est explicitement vérifiée.

    Aucun remplacement par une valeur approximative.
    """

    if not preuve.verifie:
        return False

    if preuve.texte:
        return True

    if preuve.pourcentage is not None:
        return (
            preuve.occurrences is not None
            and preuve.total is not None
            and preuve.total > 0
        )

    if preuve.moyenne is not None:
        return True

    if preuve.valeur:
        return True

    return False


def trie_preuves(
    preuves: List[PreuveStatistique],
    type_marche: str,
) -> List[PreuveStatistique]:
    """
    Ordonne les faits selon une priorité FIXE.

    Ce classement ne représente pas une force de pari.
    Il détermine uniquement l'ordre d'affichage des explications.
    """

    priorites = PRIORITES.get(type_marche, [TYPE_STAT_REMARQUABLE])
    index_priorite = {type_: index for index, type_ in enumerate(priorites)}

    return sorted(
        [p for p in preuves if preuve_utilisable(p)],
        key=lambda p: (
            index_priorite.get(p.type, len(priorites)),
            p.priorite,
        ),
    )


# ---------------------------------------------------------------------------
# 7. FORMATAGE DES PREUVES
# ---------------------------------------------------------------------------

def formate_preuve(preuve: PreuveStatistique) -> Optional[str]:
    """
    Transforme un fait déjà calculé en phrase lisible.

    Aucun calcul statistique n'est effectué ici.
    """

    if not preuve_utilisable(preuve):
        return None

    prefixe = f"{preuve.equipe} : " if preuve.equipe else ""

    if preuve.texte:
        return prefixe + preuve.texte

    if preuve.pourcentage is not None:
        if preuve.occurrences is None or preuve.total is None:
            return None

        return (
            f"{prefixe}{preuve.libelle} : "
            f"{preuve.occurrences}/{preuve.total} "
            f"({preuve.pourcentage:.1f} %)"
        )

    if preuve.moyenne is not None:
        return (
            f"{prefixe}{preuve.libelle} : "
            f"{preuve.moyenne:.2f} par match"
        )

    if preuve.valeur:
        return prefixe + f"{preuve.libelle} : {preuve.valeur}"

    return None


# ---------------------------------------------------------------------------
# 8. CONSTRUCTION DES MODÈLES DE JUSTIFICATION
# ---------------------------------------------------------------------------

def construit_justification(
    pronostic: PronosticValide,
    preuves: List[PreuveStatistique],
    maximum: int = 3,
) -> ResultatJustification:
    """
    Construit uniquement l'explication du pronostic reçu.

    Le pronostic n'est jamais recalculé, remplacé ou réévalué.
    """

    if maximum < 1:
        raise ValueError("maximum doit être supérieur ou égal à 1.")

    type_marche = identifie_type_marche(pronostic.marche)

    preuves_triees = trie_preuves(preuves, type_marche)

    justifications: List[Justification] = []

    for preuve in preuves_triees:
        texte = formate_preuve(preuve)

        if texte is None:
            continue

        justifications.append(
            Justification(
                texte=texte,
                type=preuve.type,
                contexte=preuve.contexte,
                source=preuve.source,
            )
        )

        if len(justifications) >= maximum:
            break

    return ResultatJustification(
        pronostic=pronostic,
        titre="Pourquoi ce pronostic ?",
        justifications=justifications,
        solidite_donnees=construit_solidite_donnees(preuves),
    )


# ---------------------------------------------------------------------------
# 9. SOLIDITÉ DES DONNÉES
# ---------------------------------------------------------------------------

def construit_solidite_donnees(
    preuves: List[PreuveStatistique],
) -> Optional[str]:
    """
    Décrit la présence de données sans donner un score de confiance au pari.

    Exemple :
        "Historique domicile : 8 matchs | H2H : 6 confrontations"

    Ce bloc n'est PAS la confiance du modèle.
    """

    contextes = []

    for preuve in preuves:
        if not preuve_utilisable(preuve):
            continue

        contexte = preuve.contexte.strip()

        if contexte and contexte not in contextes:
            contextes.append(contexte)

    if not contextes:
        return None

    return " | ".join(contextes)


# ---------------------------------------------------------------------------
# 10. CONVERSION POUR L'INTERFACE
# ---------------------------------------------------------------------------

def vers_dict(resultat: ResultatJustification) -> Dict[str, Any]:
    """
    Produit une structure JSON simple pour le frontend.
    """

    return {
        "titre": resultat.titre,
        "pronostic": {
            "marche": resultat.pronostic.marche,
            "probabilite_modele": resultat.pronostic.probabilite_modele,
            "cote": resultat.pronostic.cote,
            "ev": resultat.pronostic.ev,
            "verdict": resultat.pronostic.verdict,
        },
        "justifications": [
            {
                "texte": justification.texte,
                "type": justification.type,
                "contexte": justification.contexte,
                "source": justification.source,
            }
            for justification in resultat.justifications
        ],
        "solidite_donnees": resultat.solidite_donnees,
    }


# ---------------------------------------------------------------------------
# 11. EXEMPLE D'UTILISATION
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pronostic = PronosticValide(
        marche="Plus de 2.5 buts",
        probabilite_modele=0.684,
        cote=1.72,
        ev=0.176,
        verdict="GO",
    )

    preuves = [
        PreuveStatistique(
            type=TYPE_FREQUENCE_MARCHE,
            contexte="Domicile — 8 derniers matchs",
            libelle="Over 2.5 buts",
            occurrences=7,
            total=8,
            pourcentage=87.5,
            source="historique_equipe_domicile",
            verifie=True,
            equipe="Équipe A",
        ),
        PreuveStatistique(
            type=TYPE_FREQUENCE_MARCHE,
            contexte="Extérieur — 8 derniers matchs",
            libelle="Over 2.5 buts",
            occurrences=6,
            total=8,
            pourcentage=75.0,
            source="historique_equipe_exterieure",
            verifie=True,
            equipe="Équipe B",
        ),
        PreuveStatistique(
            type=TYPE_MOYENNE_BUTS_TOTAUX,
            contexte="Matchs récents — échantillon de 16 matchs",
            libelle="Moyenne totale de buts",
            moyenne=3.05,
            source="historique_combine",
            verifie=True,
        ),
        PreuveStatistique(
            type=TYPE_H2H_MARCHE,
            contexte="6 dernières confrontations",
            libelle="Over 2.5 buts",
            occurrences=5,
            total=6,
            pourcentage=83.3,
            source="h2h",
            verifie=True,
        ),
        PreuveStatistique(
            type=TYPE_STAT_REMARQUABLE,
            contexte="Saison en cours",
            libelle="Série sans défaite",
            valeur="10 matchs sans défaite",
            source="historique_equipe",
            verifie=True,
            equipe="Équipe A",
        ),
    ]

    resultat = construit_justification(
        pronostic=pronostic,
        preuves=preuves,
        maximum=3,
    )

    import json

    print(json.dumps(vers_dict(resultat), ensure_ascii=False, indent=2))
