"""
archetype_model/learning/archive.py — Registre historique d'Archetype Foot.

Pourquoi ce module existe : le moteur archetype_model doit conserver, après
sa sélection finale, les observations nécessaires à la vérification réelle,
à la matrice comportementale et à la calibration. L'archive est donc une
couche de persistance uniquement : elle ne calcule aucun pronostic, ne modifie
aucun seuil et ne participe jamais à la décision.

Décision verrouillée le 13/09/2026 :
- catégorie B : aucun archivage détaillé ; les compteurs existants de
  precalcul.py restent la seule trace de ces exclusions ;
- une observation PENDING peut changer de catégorie entre COUNTERFACTUAL et
  SELECTED tant qu'elle n'est pas résolue ;
- une observation RESOLVED est immuable : toute tentative d'écriture est
  refusée techniquement, avant modification du fichier ;
- les résultats absents restent None ; aucune donnée réelle n'est inventée ;
- l'archive est écrite mensuellement sous archive/YYYY-MM.json ;
- les écritures sont atomiques afin d'éviter un JSON partiellement écrit.
"""

from __future__ import annotations

import copy
import datetime as _datetime
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

CATEGORIE_SELECTED = "SELECTED"
CATEGORIE_COUNTERFACTUAL = "COUNTERFACTUAL"
CATEGORIES_AUTORISEES = frozenset({CATEGORIE_SELECTED, CATEGORIE_COUNTERFACTUAL})

STATUT_PENDING = "PENDING"
STATUT_RESOLVED = "RESOLVED"
STATUT_NON_RESOLU_DEFINITIF = "NON_RESOLU_DEFINITIF"
STATUTS_RESULTAT = frozenset({
    STATUT_PENDING,
    STATUT_RESOLVED,
    STATUT_NON_RESOLU_DEFINITIF,
})

SCHEMA_VERSION = 1

CHAMPS_IDENTITE = ("match_id", "marche", "scenario")
CHAMPS_OBLIGATOIRES = (
    "match_id",
    "date_match",
    "equipe_dom",
    "equipe_ext",
    "marche",
    "categorie",
    "model_version",
    "config_version",
    "resultat_statut",
)

# Champs métier pouvant être présents sur les candidats du moteur. Ils sont
# recopiés sans transformation ; leur absence reste autorisée lorsqu'elle est
# normale pour un type de marché donné.
CHAMPS_CANDIDAT = (
    "market_family",
    "exposure_group",
    "niveau",
    "robustesse",
    "probabilite",
    "probabilite_centrale",
    "cote",
    "edge",
    "edv",
    "h2h_palier",
    "signal_direction",
    "signal_frequence",
    "justification",
    "scenario",
    "rang",
)

CHAMPS_RESULTAT = (
    "buts_marques",
    "buts_encaisses",
    "resultat_marche",
    "date_resolution",
)


class ArchiveError(Exception):
    """Erreur fonctionnelle explicite du registre d'archive."""


class ArchiveValidationError(ArchiveError):
    """Enregistrement incomplet ou incohérent."""


class ArchiveOverwriteError(ArchiveError):
    """Tentative de modification d'un enregistrement déjà résolu."""


def _copie_profonde(valeur: Any) -> Any:
    return copy.deepcopy(valeur)


def _texte_non_vide(valeur: Any, nom: str) -> None:
    if not isinstance(valeur, str) or not valeur.strip():
        raise ArchiveValidationError(f"champ obligatoire invalide : {nom}")


def construire_record_id(
    match_id: Any,
    marche: Any,
    scenario: Any = None,
) -> str:
    """Construit une identité stable pour une observation de marché.

    Le rang P1/P2/P3 n'entre volontairement pas dans l'identité : un même
    marché d'un même match doit rester une seule observation lorsque son rang
    ou sa catégorie évolue avant résolution.
    """
    _texte_non_vide(str(match_id) if match_id is not None else None, "match_id")
    _texte_non_vide(marche, "marche")
    scenario_normalise = "" if scenario is None else str(scenario).strip()
    return "|".join((str(match_id).strip(), marche.strip(), scenario_normalise))


def _valider_identite(record: Mapping[str, Any]) -> None:
    for champ in CHAMPS_IDENTITE[:2]:
        _texte_non_vide(record.get(champ), champ)


def _valider_record(record: Mapping[str, Any]) -> None:
    if not isinstance(record, Mapping):
        raise ArchiveValidationError("un enregistrement doit être un objet mapping")

    for champ in CHAMPS_OBLIGATOIRES:
        if champ not in record:
            raise ArchiveValidationError(f"champ obligatoire absent : {champ}")

    _valider_identite(record)
    _texte_non_vide(record.get("date_match"), "date_match")
    _texte_non_vide(record.get("equipe_dom"), "equipe_dom")
    _texte_non_vide(record.get("equipe_ext"), "equipe_ext")
    _texte_non_vide(record.get("model_version"), "model_version")
    _texte_non_vide(record.get("config_version"), "config_version")

    if record["categorie"] not in CATEGORIES_AUTORISEES:
        raise ArchiveValidationError(
            f"catégorie interdite : {record['categorie']!r}"
        )
    if record["resultat_statut"] not in STATUTS_RESULTAT:
        raise ArchiveValidationError(
            f"statut de résultat interdit : {record['resultat_statut']!r}"
        )

    # Une observation non résolue ne doit jamais contenir un résultat présenté
    # comme réel. Les quatre champs sont normalisés explicitement à None lors
    # de la création ; la résolution les remplira ensuite.
    if record["resultat_statut"] != STATUT_RESOLVED:
        if any(record.get(champ) is not None for champ in CHAMPS_RESULTAT):
            raise ArchiveValidationError(
                "un enregistrement non résolu ne peut pas contenir de résultat réel"
            )
    else:
        if not isinstance(record.get("buts_marques"), int) or record["buts_marques"] < 0:
            raise ArchiveValidationError("buts_marques invalide pour un résultat résolu")
        if not isinstance(record.get("buts_encaisses"), int) or record["buts_encaisses"] < 0:
            raise ArchiveValidationError("buts_encaisses invalide pour un résultat résolu")
        _texte_non_vide(record.get("date_resolution"), "date_resolution")
        if record.get("resultat_marche") not in {"WIN", "LOSS"}:
            raise ArchiveValidationError("resultat_marche doit être WIN ou LOSS")


def _nouveau_record(
    candidat: Mapping[str, Any],
    *,
    categorie: str,
    match: Mapping[str, Any],
    model_version: str,
    config_version: str,
) -> dict[str, Any]:
    if categorie not in CATEGORIES_AUTORISEES:
        raise ArchiveValidationError(f"catégorie interdite : {categorie!r}")

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_id": construire_record_id(
            match.get("match_id"), candidat.get("marche"), candidat.get("scenario")
        ),
        "match_id": str(match.get("match_id")).strip(),
        "date_match": match.get("date_match", match.get("date")),
        "heure_match": match.get("heure_match", match.get("heure")),
        "equipe_dom": match.get("equipe_dom", match.get("domicile")),
        "equipe_ext": match.get("equipe_ext", match.get("exterieur")),
        "competition": match.get("competition"),
        "marche": candidat.get("marche"),
        "categorie": categorie,
        "model_version": model_version,
        "config_version": config_version,
        "resultat_statut": STATUT_PENDING,
        "buts_marques": None,
        "buts_encaisses": None,
        "resultat_marche": None,
        "date_resolution": None,
        "archivee_le": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
    }

    for champ in CHAMPS_CANDIDAT:
        if champ in candidat:
            record[champ] = _copie_profonde(candidat[champ])

    # La valeur canonique de la probabilité est `probabilite`. Certaines
    # sorties historiques portent `probabilite_centrale`; on conserve les deux
    # si elles existent et ne fabrique aucune valeur si elles sont absentes.
    if "probabilite" not in record and "probabilite_centrale" in record:
        record["probabilite"] = record["probabilite_centrale"]

    # Le scénario est facultatif : il n'est renseigné que si le moteur le
    # transmet réellement.
    _valider_record(record)
    return record


def _lire_archive(chemin: Path) -> list[dict[str, Any]]:
    if not chemin.exists():
        return []
    try:
        with chemin.open("r", encoding="utf-8") as fichier:
            contenu = json.load(fichier)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"archive illisible : {chemin} : {exc}") from exc

    if isinstance(contenu, list):
        return contenu
    if isinstance(contenu, dict) and isinstance(contenu.get("records"), list):
        return contenu["records"]
    raise ArchiveError(f"format d'archive invalide : {chemin}")


def _ecrire_atomiquement(chemin: Path, records: list[dict[str, Any]]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = json.dumps(records, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    fd, temporaire = tempfile.mkstemp(
        prefix=f".{chemin.name}.", suffix=".tmp", dir=str(chemin.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, chemin)
    except Exception:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def charger_archive(chemin: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Charge une archive mensuelle et valide ses enregistrements."""
    path = Path(chemin)
    records = _lire_archive(path)
    for record in records:
        _valider_record(record)
    return records


def _index_records(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    index: dict[str, int] = {}
    for position, record in enumerate(records):
        rid = record.get("record_id")
        if not rid:
            rid = construire_record_id(
                record.get("match_id"), record.get("marche"), record.get("scenario")
            )
        if rid in index:
            raise ArchiveError(f"doublon d'identité dans l'archive : {rid}")
        index[rid] = position
    return index


def enregistrer_record(
    record: Mapping[str, Any],
    chemin: str | os.PathLike[str],
) -> str:
    """Insère ou met à jour une observation, avec verrou anti-écrasement."""
    nouveau = _copie_profonde(dict(record))
    _valider_record(nouveau)
    rid = nouveau.get("record_id") or construire_record_id(
        nouveau["match_id"], nouveau["marche"], nouveau.get("scenario")
    )
    nouveau["record_id"] = rid

    path = Path(chemin)
    records = _lire_archive(path)
    index = _index_records(records)

    if rid not in index:
        records.append(nouveau)
    else:
        position = index[rid]
        existant = records[position]

        # GARDE TECHNIQUE NON NÉGOCIABLE : un RESOLVED est immuable. Cette
        # vérification se trouve ici, dans le point d'écriture unique, afin
        # qu'aucun appelant ne puisse l'oublier ou la contourner par accident.
        if existant.get("resultat_statut") == STATUT_RESOLVED:
            raise ArchiveOverwriteError(
                f"enregistrement résolu immuable : {rid}"
            )

        # Un PENDING peut évoluer de COUNTERFACTUAL vers SELECTED, de SELECTED
        # vers COUNTERFACTUAL, ou simplement recevoir les nouvelles métadonnées
        # du run courant. Aucun résultat réel ne peut apparaître avant résolution.
        records[position] = nouveau

    for record_a_verifier in records:
        _valider_record(record_a_verifier)

    _ecrire_atomiquement(path, records)
    return rid


def enregistrer_selection(
    candidat: Mapping[str, Any],
    *,
    match: Mapping[str, Any],
    model_version: str,
    config_version: str,
    chemin: str | os.PathLike[str],
) -> str:
    """Archive un P1/P2/P3 sélectionné."""
    record = _nouveau_record(
        candidat,
        categorie=CATEGORIE_SELECTED,
        match=match,
        model_version=model_version,
        config_version=config_version,
    )
    return enregistrer_record(record, chemin)


def enregistrer_contrefactuel(
    candidat: Mapping[str, Any],
    *,
    match: Mapping[str, Any],
    model_version: str,
    config_version: str,
    chemin: str | os.PathLike[str],
) -> str:
    """Archive une observation de catégorie A proche du seuil."""
    record = _nouveau_record(
        candidat,
        categorie=CATEGORIE_COUNTERFACTUAL,
        match=match,
        model_version=model_version,
        config_version=config_version,
    )
    return enregistrer_record(record, chemin)


def enregistrer_selection_et_contrefactuels(
    *,
    match: Mapping[str, Any],
    selections: Iterable[Mapping[str, Any]],
    contrefactuels: Iterable[Mapping[str, Any]],
    model_version: str,
    config_version: str,
    chemin: str | os.PathLike[str],
) -> int:
    """Archive toutes les observations du match dans une seule écriture."""
    nouveaux: dict[str, dict[str, Any]] = {}
    for candidat in selections:
        record = _nouveau_record(
            candidat,
            categorie=CATEGORIE_SELECTED,
            match=match,
            model_version=model_version,
            config_version=config_version,
        )
        nouveaux[record["record_id"]] = record

    for candidat in contrefactuels:
        record = _nouveau_record(
            candidat,
            categorie=CATEGORIE_COUNTERFACTUAL,
            match=match,
            model_version=model_version,
            config_version=config_version,
        )
        # Une sélection gagne sur une observation contrefactuelle si le même
        # marché est transmis par erreur dans les deux populations du même run.
        nouveaux.setdefault(record["record_id"], record)

    if not nouveaux:
        return 0

    path = Path(chemin)
    records = _lire_archive(path)
    index = _index_records(records)

    for rid, nouveau in nouveaux.items():
        if rid not in index:
            records.append(nouveau)
            index[rid] = len(records) - 1
            continue

        position = index[rid]
        existant = records[position]
        if existant.get("resultat_statut") == STATUT_RESOLVED:
            raise ArchiveOverwriteError(f"enregistrement résolu immuable : {rid}")
        records[position] = nouveau

    for record_a_verifier in records:
        _valider_record(record_a_verifier)

    _ecrire_atomiquement(path, records)
    return len(nouveaux)


def mettre_a_jour_resultat(
    record_id: str,
    *,
    buts_marques: int,
    buts_encaisses: int,
    resultat_marche: str,
    date_resolution: str,
    chemin: str | os.PathLike[str],
) -> None:
    """Résout une observation PENDING ou la marque définitivement non résolue."""
    if not isinstance(buts_marques, int) or buts_marques < 0:
        raise ArchiveValidationError("buts_marques doit être un entier >= 0")
    if not isinstance(buts_encaisses, int) or buts_encaisses < 0:
        raise ArchiveValidationError("buts_encaisses doit être un entier >= 0")
    if resultat_marche not in {"WIN", "LOSS"}:
        raise ArchiveValidationError("resultat_marche doit être WIN ou LOSS")
    _texte_non_vide(date_resolution, "date_resolution")

    path = Path(chemin)
    records = _lire_archive(path)
    index = _index_records(records)
    if record_id not in index:
        raise ArchiveError(f"enregistrement introuvable : {record_id}")

    position = index[record_id]
    existant = records[position]

    # Même verrou que pour les autres écritures : un RESOLVED ne peut pas être
    # réécrit, même si la nouvelle écriture prétend fournir un autre score.
    if existant.get("resultat_statut") == STATUT_RESOLVED:
        raise ArchiveOverwriteError(f"enregistrement résolu immuable : {record_id}")

    maj = _copie_profonde(existant)
    maj.update({
        "resultat_statut": STATUT_RESOLVED,
        "buts_marques": buts_marques,
        "buts_encaisses": buts_encaisses,
        "resultat_marche": resultat_marche,
        "date_resolution": date_resolution,
    })
    _valider_record(maj)
    records[position] = maj
    _ecrire_atomiquement(path, records)


def marquer_non_resolu_definitif(
    record_id: str,
    *,
    chemin: str | os.PathLike[str],
) -> None:
    """Ferme une observation sans score après le délai réglementaire."""
    path = Path(chemin)
    records = _lire_archive(path)
    index = _index_records(records)
    if record_id not in index:
        raise ArchiveError(f"enregistrement introuvable : {record_id}")

    position = index[record_id]
    existant = records[position]
    if existant.get("resultat_statut") == STATUT_RESOLVED:
        raise ArchiveOverwriteError(f"enregistrement résolu immuable : {record_id}")

    maj = _copie_profonde(existant)
    maj["resultat_statut"] = STATUT_NON_RESOLU_DEFINITIF
    _valider_record(maj)
    records[position] = maj
    _ecrire_atomiquement(path, records)


def chemin_archive_mensuelle(
    date_match: str,
    repertoire: str | os.PathLike[str] = "archive",
) -> Path:
    """Retourne archive/YYYY-MM.json à partir d'une date ISO YYYY-MM-DD."""
    _texte_non_vide(date_match, "date_match")
    try:
        date = _datetime.date.fromisoformat(date_match[:10])
    except ValueError as exc:
        raise ArchiveValidationError(f"date_match invalide : {date_match!r}") from exc
    return Path(repertoire) / f"{date:%Y-%m}.json"
