# Étude des indicateurs affichés — V2 et V3

Date : 22/10/2026. Pour chaque pari proposé par le moteur (gelé avant le match) : l'indice de performance affiché (x/4), le pourcentage affiché, le nombre d'étoiles affiché, et le résultat réel (gagné / perdu).

**Sources** : V2 = `moteur_en_production.choix` de `data/archive_test` ; V3 = `data/v3/journal` (dernier calcul avant le coup d'envoi) ; scores finaux de l'archive. Reproductible : `python evaluation/etude_affichage_v2_v3.py`. Liste complète des paris : `docs/etude_affichage_v2_v3_paris.csv`.

**Indice** : calcul du moteur (`moteur_v3/performance.py`) sur les séries d'avant-match ; 4/4 pour un marché à deux équipes, 2/2 pour un marché d'une seule équipe (le maximum dans les deux cas, regroupé ci-dessous sous « indice maximal »).
**Pourcentage** : la probabilité affichée du pari. **Étoiles V2** : catégorie du moteur (A = 3, B = 2, C = 1) recalculée avec la règle exacte `categorie_value` ; l'artefact « données issues du classement uniquement » n'est pas archivé et n'est pas pris en compte. **Étoiles V3** : taille de l'échantillon au même lieu de l'équipe la moins fournie (moins de 5 matchs = 1 ; 5 à 7 = 2 ; 8 à 9 = 3 ; 10 et plus = 4).


---

## V2

**1207 paris**, 723 matchs, du 2026-09-28 au 2026-10-21. Gagnés : 579. Perdus : 628. Réussite : 48.0 %.

### 1. Par indice affiché

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 0/2 | 70 | 33 | 37 | 47.1 % | 36–59 % |
| 0/4 | 257 | 62 | 195 | 24.1 % | 19–30 % |
| 1/2 | 128 | 68 | 60 | 53.1 % | 45–62 % |
| 1/4 | 202 | 90 | 112 | 44.6 % | 38–51 % |
| 2/2 | 70 | 41 | 29 | 58.6 % | 47–69 % |
| 2/4 | 185 | 102 | 83 | 55.1 % | 48–62 % |
| 3/4 | 197 | 124 | 73 | 62.9 % | 56–69 % |
| 4/4 | 97 | 59 | 38 | 60.8 % | 51–70 % |
| sans indice | 1 | 0 | 1 | 0.0 % | 0–79 % |

### 2. Par pourcentage affiché

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 501 | 162 | 339 | 32.3 % | 28–37 % |
| 60–69 % | 198 | 103 | 95 | 52.0 % | 45–59 % |
| 70–79 % | 308 | 180 | 128 | 58.4 % | 53–64 % |
| 80–89 % | 195 | 130 | 65 | 66.7 % | 60–73 % |
| 90 % et + | 5 | 4 | 1 | 80.0 % | 38–96 % |

### 3. Par nombre d'étoiles affiché

| Étoiles | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1 ★ | 364 | 148 | 216 | 40.7 % | 36–46 % |
| 2 ★ | 122 | 33 | 89 | 27.0 % | 20–36 % |
| 3 ★ | 721 | 398 | 323 | 55.2 % | 52–59 % |

### 4. Indice × pourcentage

**Indice sans indice**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 1 | 0 | 1 | 0.0 % | 0–79 % |

**Indice 4/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 2 | 0 | 2 | 0.0 % | 0–66 % |
| 60–69 % | 10 | 6 | 4 | 60.0 % | 31–83 % |
| 70–79 % | 34 | 20 | 14 | 58.8 % | 42–74 % |
| 80–89 % | 48 | 30 | 18 | 62.5 % | 48–75 % |
| 90 % et + | 3 | 3 | 0 | 100.0 % | 44–100 % |

**Indice 3/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 12 | 3 | 9 | 25.0 % | 9–53 % |
| 60–69 % | 26 | 19 | 7 | 73.1 % | 54–86 % |
| 70–79 % | 83 | 50 | 33 | 60.2 % | 49–70 % |
| 80–89 % | 74 | 51 | 23 | 68.9 % | 58–78 % |
| 90 % et + | 2 | 1 | 1 | 50.0 % | 9–91 % |

**Indice 2/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 39 | 22 | 17 | 56.4 % | 41–71 % |
| 60–69 % | 38 | 18 | 20 | 47.4 % | 32–63 % |
| 70–79 % | 68 | 36 | 32 | 52.9 % | 41–64 % |
| 80–89 % | 40 | 26 | 14 | 65.0 % | 50–78 % |

**Indice 2/2**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 9 | 3 | 6 | 33.3 % | 12–65 % |
| 60–69 % | 9 | 4 | 5 | 44.4 % | 19–73 % |
| 70–79 % | 34 | 22 | 12 | 64.7 % | 48–79 % |
| 80–89 % | 18 | 12 | 6 | 66.7 % | 44–84 % |

**Indice 1/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 106 | 41 | 65 | 38.7 % | 30–48 % |
| 60–69 % | 55 | 25 | 30 | 45.5 % | 33–58 % |
| 70–79 % | 33 | 18 | 15 | 54.5 % | 38–70 % |
| 80–89 % | 8 | 6 | 2 | 75.0 % | 41–93 % |

**Indice 1/2**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 28 | 8 | 20 | 28.6 % | 15–47 % |
| 60–69 % | 46 | 25 | 21 | 54.3 % | 40–68 % |
| 70–79 % | 49 | 30 | 19 | 61.2 % | 47–74 % |
| 80–89 % | 5 | 5 | 0 | 100.0 % | 57–100 % |

**Indice 0/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 250 | 60 | 190 | 24.0 % | 19–30 % |
| 60–69 % | 4 | 1 | 3 | 25.0 % | 5–70 % |
| 70–79 % | 3 | 1 | 2 | 33.3 % | 6–79 % |

**Indice 0/2**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 54 | 25 | 29 | 46.3 % | 34–59 % |
| 60–69 % | 10 | 5 | 5 | 50.0 % | 24–76 % |
| 70–79 % | 4 | 3 | 1 | 75.0 % | 30–95 % |
| 80–89 % | 2 | 0 | 2 | 0.0 % | 0–66 % |

### 5. Étoiles × pourcentage

**3 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 167 | 66 | 101 | 39.5 % | 32–47 % |
| 60–69 % | 148 | 77 | 71 | 52.0 % | 44–60 % |
| 70–79 % | 253 | 153 | 100 | 60.5 % | 54–66 % |
| 80–89 % | 150 | 99 | 51 | 66.0 % | 58–73 % |
| 90 % et + | 3 | 3 | 0 | 100.0 % | 44–100 % |

**2 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 122 | 33 | 89 | 27.0 % | 20–36 % |

**1 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| moins de 60 % | 212 | 63 | 149 | 29.7 % | 24–36 % |
| 60–69 % | 50 | 26 | 24 | 52.0 % | 39–65 % |
| 70–79 % | 55 | 27 | 28 | 49.1 % | 36–62 % |
| 80–89 % | 45 | 31 | 14 | 68.9 % | 54–80 % |
| 90 % et + | 2 | 1 | 1 | 50.0 % | 9–91 % |

### 6. Indice × étoiles

**3 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 0/2 | 22 | 13 | 9 | 59.1 % | 39–77 % |
| 0/4 | 39 | 11 | 28 | 28.2 % | 17–44 % |
| 1/2 | 93 | 54 | 39 | 58.1 % | 48–68 % |
| 1/4 | 146 | 66 | 80 | 45.2 % | 37–53 % |
| 2/2 | 54 | 36 | 18 | 66.7 % | 53–78 % |
| 2/4 | 141 | 77 | 64 | 54.6 % | 46–63 % |
| 3/4 | 158 | 101 | 57 | 63.9 % | 56–71 % |
| 4/4 | 68 | 40 | 28 | 58.8 % | 47–70 % |

**2 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 0/2 | 11 | 5 | 6 | 45.5 % | 21–72 % |
| 0/4 | 88 | 23 | 65 | 26.1 % | 18–36 % |
| 1/2 | 9 | 0 | 9 | 0.0 % | 0–30 % |
| 1/4 | 8 | 4 | 4 | 50.0 % | 22–78 % |
| 2/2 | 1 | 0 | 1 | 0.0 % | 0–79 % |
| 2/4 | 4 | 1 | 3 | 25.0 % | 5–70 % |
| sans indice | 1 | 0 | 1 | 0.0 % | 0–79 % |

**1 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 0/2 | 37 | 15 | 22 | 40.5 % | 26–57 % |
| 0/4 | 130 | 28 | 102 | 21.5 % | 15–29 % |
| 1/2 | 26 | 14 | 12 | 53.8 % | 35–71 % |
| 1/4 | 48 | 20 | 28 | 41.7 % | 29–56 % |
| 2/2 | 15 | 5 | 10 | 33.3 % | 15–58 % |
| 2/4 | 40 | 24 | 16 | 60.0 % | 45–74 % |
| 3/4 | 39 | 23 | 16 | 59.0 % | 43–73 % |
| 4/4 | 29 | 19 | 10 | 65.5 % | 47–80 % |

### 7. Combinaisons les plus regardées

| Combinaison | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| Indice maximal (4/4 ou 2/2) | 167 | 100 | 67 | 59.9 % | 52–67 % |
| Indice 4/4 | 97 | 59 | 38 | 60.8 % | 51–70 % |
| Pourcentage 80 % et + | 200 | 134 | 66 | 67.0 % | 60–73 % |
| Indice maximal et pourcentage 80 % et + | 69 | 45 | 24 | 65.2 % | 53–75 % |
| Indice maximal et 3 étoiles | 122 | 76 | 46 | 62.3 % | 53–70 % |
| Pourcentage 80 % et + et 3 étoiles | 153 | 102 | 51 | 66.7 % | 59–74 % |
| Indice maximal, 80 % et +, 3 étoiles | 47 | 31 | 16 | 66.0 % | 52–78 % |
| Indice maximal, 80 % et +, 3 étoiles ou plus | 47 | 31 | 16 | 66.0 % | 52–78 % |

### 8. Par type de marché

| Marché | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| Buts d'une équipe | 246 | 134 | 112 | 54.5 % | 48–61 % |
| Cage inviolée / encaisse | 22 | 8 | 14 | 36.4 % | 20–57 % |
| Double chance | 91 | 44 | 47 | 48.4 % | 38–58 % |
| Handicap | 249 | 135 | 114 | 54.2 % | 48–60 % |
| Les deux équipes marquent | 48 | 19 | 29 | 39.6 % | 27–54 % |
| Total de buts : moins de | 170 | 106 | 64 | 62.4 % | 55–69 % |
| Total de buts : plus de | 204 | 74 | 130 | 36.3 % | 30–43 % |
| Victoire / nul | 177 | 59 | 118 | 33.3 % | 27–41 % |


---

## V3

**158 paris**, 146 matchs, du 2026-10-04 au 2026-10-20. Gagnés : 101. Perdus : 57. Réussite : 63.9 %.

### 1. Par indice affiché

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1/2 | 8 | 4 | 4 | 50.0 % | 22–78 % |
| 1/4 | 25 | 16 | 9 | 64.0 % | 45–80 % |
| 2/2 | 26 | 16 | 10 | 61.5 % | 43–78 % |
| 2/4 | 22 | 11 | 11 | 50.0 % | 31–69 % |
| 3/4 | 36 | 26 | 10 | 72.2 % | 56–84 % |
| 4/4 | 41 | 28 | 13 | 68.3 % | 53–80 % |

### 2. Par pourcentage affiché

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 8 | 5 | 3 | 62.5 % | 31–86 % |
| 70–79 % | 70 | 43 | 27 | 61.4 % | 50–72 % |
| 80–89 % | 76 | 51 | 25 | 67.1 % | 56–77 % |
| 90 % et + | 4 | 2 | 2 | 50.0 % | 15–85 % |

### 3. Par nombre d'étoiles affiché

| Étoiles | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1 ★ | 106 | 68 | 38 | 64.2 % | 55–73 % |
| 2 ★ | 22 | 11 | 11 | 50.0 % | 31–69 % |
| 3 ★ | 1 | 1 | 0 | 100.0 % | 21–100 % |
| 4 ★ | 29 | 21 | 8 | 72.4 % | 54–85 % |

### 4. Indice × pourcentage

**Indice 4/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 1 | 1 | 0 | 100.0 % | 21–100 % |
| 70–79 % | 13 | 8 | 5 | 61.5 % | 36–82 % |
| 80–89 % | 23 | 17 | 6 | 73.9 % | 54–87 % |
| 90 % et + | 4 | 2 | 2 | 50.0 % | 15–85 % |

**Indice 3/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 2 | 1 | 1 | 50.0 % | 9–91 % |
| 70–79 % | 17 | 12 | 5 | 70.6 % | 47–87 % |
| 80–89 % | 17 | 13 | 4 | 76.5 % | 53–90 % |

**Indice 2/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 3 | 2 | 1 | 66.7 % | 21–94 % |
| 70–79 % | 11 | 5 | 6 | 45.5 % | 21–72 % |
| 80–89 % | 8 | 4 | 4 | 50.0 % | 22–78 % |

**Indice 2/2**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 70–79 % | 7 | 5 | 2 | 71.4 % | 36–92 % |
| 80–89 % | 19 | 11 | 8 | 57.9 % | 36–77 % |

**Indice 1/4**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 2 | 1 | 1 | 50.0 % | 9–91 % |
| 70–79 % | 16 | 10 | 6 | 62.5 % | 39–82 % |
| 80–89 % | 7 | 5 | 2 | 71.4 % | 36–92 % |

**Indice 1/2**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 70–79 % | 6 | 3 | 3 | 50.0 % | 19–81 % |
| 80–89 % | 2 | 1 | 1 | 50.0 % | 9–91 % |

### 5. Étoiles × pourcentage

**4 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 1 | 1 | 0 | 100.0 % | 21–100 % |
| 70–79 % | 10 | 9 | 1 | 90.0 % | 60–98 % |
| 80–89 % | 18 | 11 | 7 | 61.1 % | 39–80 % |

**3 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 80–89 % | 1 | 1 | 0 | 100.0 % | 21–100 % |

**2 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 1 | 1 | 0 | 100.0 % | 21–100 % |
| 70–79 % | 11 | 4 | 7 | 36.4 % | 15–65 % |
| 80–89 % | 10 | 6 | 4 | 60.0 % | 31–83 % |

**1 ★**

| Pourcentage | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 60–69 % | 6 | 3 | 3 | 50.0 % | 19–81 % |
| 70–79 % | 49 | 30 | 19 | 61.2 % | 47–74 % |
| 80–89 % | 47 | 33 | 14 | 70.2 % | 56–81 % |
| 90 % et + | 4 | 2 | 2 | 50.0 % | 15–85 % |

### 6. Indice × étoiles

**4 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1/2 | 2 | 1 | 1 | 50.0 % | 9–91 % |
| 1/4 | 13 | 10 | 3 | 76.9 % | 50–92 % |
| 2/2 | 1 | 1 | 0 | 100.0 % | 21–100 % |
| 2/4 | 8 | 5 | 3 | 62.5 % | 31–86 % |
| 3/4 | 4 | 4 | 0 | 100.0 % | 51–100 % |
| 4/4 | 1 | 0 | 1 | 0.0 % | 0–79 % |

**3 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 3/4 | 1 | 1 | 0 | 100.0 % | 21–100 % |

**2 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1/4 | 4 | 1 | 3 | 25.0 % | 5–70 % |
| 2/2 | 4 | 2 | 2 | 50.0 % | 15–85 % |
| 2/4 | 4 | 1 | 3 | 25.0 % | 5–70 % |
| 3/4 | 7 | 5 | 2 | 71.4 % | 36–92 % |
| 4/4 | 3 | 2 | 1 | 66.7 % | 21–94 % |

**1 ★**

| Indice | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| 1/2 | 6 | 3 | 3 | 50.0 % | 19–81 % |
| 1/4 | 8 | 5 | 3 | 62.5 % | 31–86 % |
| 2/2 | 21 | 13 | 8 | 61.9 % | 41–79 % |
| 2/4 | 10 | 5 | 5 | 50.0 % | 24–76 % |
| 3/4 | 24 | 16 | 8 | 66.7 % | 47–82 % |
| 4/4 | 37 | 26 | 11 | 70.3 % | 54–83 % |

### 7. Combinaisons les plus regardées

| Combinaison | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| Indice maximal (4/4 ou 2/2) | 67 | 44 | 23 | 65.7 % | 54–76 % |
| Indice 4/4 | 41 | 28 | 13 | 68.3 % | 53–80 % |
| Pourcentage 80 % et + | 80 | 53 | 27 | 66.2 % | 55–76 % |
| Indice maximal et pourcentage 80 % et + | 46 | 30 | 16 | 65.2 % | 51–77 % |
| Indice maximal et 3 étoiles | 0 | 0 | 0 | — | — |
| Pourcentage 80 % et + et 3 étoiles | 1 | 1 | 0 | 100.0 % | 21–100 % |
| Indice maximal, 80 % et +, 3 étoiles | 0 | 0 | 0 | — | — |
| Indice maximal, 80 % et +, 3 étoiles ou plus | 2 | 1 | 1 | 50.0 % | 9–91 % |

### 8. Par type de marché

| Marché | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |
|---|---:|---:|---:|---:|---:|
| Buts d'une équipe | 30 | 19 | 11 | 63.3 % | 46–78 % |
| Cage inviolée / encaisse | 4 | 1 | 3 | 25.0 % | 5–70 % |
| Double chance | 8 | 4 | 4 | 50.0 % | 22–78 % |
| Handicap | 19 | 12 | 7 | 63.2 % | 41–81 % |
| Les deux équipes marquent | 7 | 4 | 3 | 57.1 % | 25–84 % |
| Total de buts : moins de | 50 | 40 | 10 | 80.0 % | 67–89 % |
| Total de buts : plus de | 35 | 19 | 16 | 54.3 % | 38–70 % |
| Victoire / nul | 5 | 2 | 3 | 40.0 % | 12–77 % |


---

## Limites de lecture

- Période courte (V2 : 24 jours, V3 : 17 jours) : les sous-groupes de moins de 30 paris sont à lire avec prudence ; l'intervalle 95 % (Wilson) donne la marge.
- Plusieurs paris d'un même match sont possibles : les intervalles réels sont un peu plus larges.
- Les paris V2 sont ceux du moteur de production de l'archive (versions 2.6.9 et 2.6.10).
- Archive de test : aucun pari réel n'est engagé.
