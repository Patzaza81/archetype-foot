"""
resolution_betpawa_precalcul.py -- Branche resolution_betpawa.py +
cache_betpawa.py dans la fenêtre J+1/J+2/J+3 de precalcul.py, pour que
chaque match cherche automatiquement sa correspondance Betpawa et
récupère ses vraies cotes/marchés, au lieu de retomber sur Bet365 par
défaut.

RÈGLE RESPECTÉE : ne modifie aucune ligne de resolution_betpawa.py
(moteur à 3 tamis) ni de cache_betpawa.py -- pure orchestration autour
de ces deux modules, exactement comme test_scraping_betpawa_liste.py le
faisait pour son test isolé.

CORRECTIF 06/09/2026 (bug #37) -- la ligne ci-dessous affirmait "JAMAIS
EXÉCUTÉ EN CONDITIONS RÉELLES au moment où ce fichier est écrit", ce qui
est devenu faux : cache_betpawa.json contient 380 entrées réelles au
06/09/2026, preuve directe que ce module a bien tourné en production.
Corrigée ici, sans toucher à l'affirmation adjacente sur le volume complet
(600-800 matchs/nuit) faute de preuve sur cette échelle précise.

Testé en conditions réelles depuis son premier déploiement (voir
cache_betpawa.json, 380 entrées réelles au 06/09/2026) -- betpawa.cm
reste inaccessible depuis l'environnement où ce fichier est modifié (même
blocage réseau que matchendirect.fr), donc toute modification de ce
fichier ne peut être vérifiée qu'après déploiement réel (GitHub Actions),
jamais localement -- voir diagnostic_precalcul_betpawa.txt (généré à
chaque run) pour la trace complète.

Comportement en cas d'échec, à chaque étape : le match concerné garde
son comportement ACTUEL (cotes Bet365 via matchendirect, url_match déjà
présente) -- rien n'est jamais dégradé, seulement potentiellement
enrichi. Aucune exception ne doit pouvoir remonter jusqu'à precalcul.py.
"""
import os
import time

from resolution_betpawa import resoudre_match
from cache_betpawa import cherche_dans_cache, enregistre_correspondance, invalide_entree
from scraper_betpawa import recupere_page, meilleur_parsing, _noms_correspondent
from parse_betpawa_url import extrait_meta

FICHIER_DIAGNOSTIC = "diagnostic_precalcul_betpawa.txt"

# Limite optionnelle du nombre de matchs à faire passer par la résolution
# Betpawa lors d'un run -- utile pour les premiers tests réels sur GitHub
# Actions avant de lâcher le plein volume (600-800 matchs/nuit, jamais
# testé à cette échelle à ce jour). Vide/absent = pas de limite (volume
# complet). Réglé via l'input "limite_betpawa" du workflow (voir
# pipeline.yml).
VARIABLE_ENV_LIMITE = "PRECALCUL_LIMITE_BETPAWA"


def _limite_configuree():
    brute = os.environ.get(VARIABLE_ENV_LIMITE, "").strip()
    if not brute:
        return None
    try:
        n = int(brute)
        return n if n > 0 else None
    except ValueError:
        return None


def resout_cotes_betpawa(fenetre):
    """Modifie 'fenetre' EN PLACE : ajoute cotes_manuelles + betpawa_url
    aux matchs pour lesquels une correspondance Betpawa CERTAINE a été
    trouvée (cache ou résolution fraîche) ET dont les cotes ont pu être
    extraites. Ne touche à rien pour les autres -- ils gardent leur
    comportement actuel (Bet365 via matchendirect).

    Retourne un dict de compteurs, jamais une simple affirmation de
    succès -- à lire dans les logs et dans precalcul.json après chaque
    run."""
    compteurs = {
        "betpawa_tentes": 0,
        "betpawa_cache_hit": 0,
        "betpawa_trouves_frais": 0,
        "betpawa_ambigus": 0,
        "betpawa_non_trouves": 0,
        "betpawa_titre_mismatch": 0,
        "betpawa_cotes_extraites": 0,
        "betpawa_cotes_vides": 0,
        "betpawa_erreurs": 0,
        "betpawa_ignore_sans_playwright": False,
        "betpawa_duree_secondes": 0,
    }
    etapes = []
    limite = _limite_configuree()
    if limite is not None:
        etapes.append(f"Limite active : {limite} matchs maximum passeront "
                      f"par la résolution Betpawa sur ce run "
                      f"({VARIABLE_ENV_LIMITE}).")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        etapes.append("Playwright non installé -- résolution Betpawa "
                      "entièrement sautée, tous les matchs restent sur "
                      "Bet365 par défaut.")
        compteurs["betpawa_ignore_sans_playwright"] = True
        _ecrit_diagnostic(etapes, compteurs)
        return compteurs

    debut = time.time()

    try:
        with sync_playwright() as p:
            navigateur = p.chromium.launch()
            appareil = p.devices["iPhone 13"]
            contexte = navigateur.new_context(**appareil)
            page = contexte.new_page()

            for m in fenetre:
                if limite is not None and compteurs["betpawa_tentes"] >= limite:
                    etapes.append(f"Limite de {limite} atteinte -- arrêt, "
                                  f"matchs restants inchangés (Bet365).")
                    break

                domicile, exterieur = m.get("domicile"), m.get("exterieur")
                date_iso = m.get("date")
                if not (domicile and exterieur and date_iso):
                    continue

                compteurs["betpawa_tentes"] += 1

                hit = cherche_dans_cache(domicile, exterieur, date_iso)
                if hit is not None:
                    url = hit["event_id"]
                    compteurs["betpawa_cache_hit"] += 1
                    etapes.append(f"CACHE HIT [{domicile} - {exterieur}] -> {url}")
                else:
                    try:
                        resultat = resoudre_match(page, domicile, exterieur, date_iso, etapes)
                    except Exception as e:
                        etapes.append(f"ERREUR résolution [{domicile} - {exterieur}] : {e}")
                        compteurs["betpawa_erreurs"] += 1
                        continue

                    if resultat == "AMBIGU":
                        compteurs["betpawa_ambigus"] += 1
                        continue
                    if resultat is None:
                        compteurs["betpawa_non_trouves"] += 1
                        continue

                    url = resultat
                    compteurs["betpawa_trouves_frais"] += 1
                    enregistre_correspondance(
                        domicile, exterieur, date_iso, event_id_url=url,
                        competition=m.get("competition"), tamis="precalcul",
                    )

                try:
                    texte, titre = recupere_page(page, url)
                except Exception as e:
                    etapes.append(f"ERREUR récupération cotes "
                                  f"[{domicile} - {exterieur}] ({url}) : {e}")
                    compteurs["betpawa_erreurs"] += 1
                    continue

                # CORRECTIF 06/09/2026 (bug #6) : le titre de la page était
                # récupéré puis jeté (`_titre`), jamais revérifié contre
                # domicile/exterieur avant d'extraire les cotes -- risque
                # concentré sur les cache hits antérieurs au correctif
                # tamis 1 (#12, réserve/jeunes). meilleur_parsing() est
                # générique par conception (1X2/BTTS/Over-Under ne
                # dépendent d'aucun nom d'équipe dans le texte capturé) :
                # une mauvaise URL renvoie donc de VRAIES cotes, juste
                # pour le mauvais match, jamais un résultat vide qui
                # alerterait tout seul. meta_titre=None (titre imparsable)
                # laisse le comportement identique à avant ce correctif --
                # jamais démontré comme un risque, pas de dégradation du
                # taux de résolution actuel sur une hypothèse non vérifiée.
                meta_titre = extrait_meta(titre)
                if meta_titre is not None and not (
                    _noms_correspondent(domicile, meta_titre["domicile"])
                    and _noms_correspondent(exterieur, meta_titre["exterieur"])
                ):
                    etapes.append(
                        f"TITRE NE CORRESPOND PAS [{domicile} - {exterieur}] -- page "
                        f"chargée : '{meta_titre['domicile']} - {meta_titre['exterieur']}' "
                        f"({url}) -- cotes NON extraites, match laissé sur Bet365 par défaut."
                    )
                    compteurs["betpawa_titre_mismatch"] += 1
                    if hit is not None and invalide_entree(domicile, exterieur, date_iso):
                        etapes.append(
                            f"  Entrée cache invalidée pour [{domicile} - {exterieur} / "
                            f"{date_iso}] -- une résolution fraîche sera retentée au "
                            f"prochain run."
                        )
                    continue

                cotes = meilleur_parsing(texte, domicile, exterieur)

                if cotes:
                    m["cotes_manuelles"] = cotes
                    m["betpawa_url"] = url
                    compteurs["betpawa_cotes_extraites"] += 1
                    etapes.append(f"COTES OK [{domicile} - {exterieur}] "
                                  f"{len(cotes)} marché(s) depuis {url}")
                else:
                    compteurs["betpawa_cotes_vides"] += 1
                    etapes.append(f"COTES VIDES [{domicile} - {exterieur}] "
                                  f"({url}) -- match laissé sur Bet365 par défaut.")

            navigateur.close()
    except Exception as e:
        # Filet de sécurité ultime : si Playwright plante au niveau du
        # navigateur lui-même (pas d'un match précis), on ne doit jamais
        # faire échouer tout precalcul.py pour autant.
        etapes.append(f"ERREUR FATALE navigateur Playwright : {e} -- "
                      f"résolution Betpawa interrompue, matchs non encore "
                      f"traités restent sur Bet365 par défaut.")
        compteurs["betpawa_erreurs"] += 1

    compteurs["betpawa_duree_secondes"] = round(time.time() - debut)
    _ecrit_diagnostic(etapes, compteurs)
    return compteurs


def _ecrit_diagnostic(etapes, compteurs):
    resume = [f"{cle} : {valeur}" for cle, valeur in compteurs.items()]
    with open(FICHIER_DIAGNOSTIC, "w", encoding="utf-8") as f:
        f.write("--- Résumé ---\n" + "\n".join(resume) +
                "\n\n--- Détail ---\n" + "\n".join(etapes))
