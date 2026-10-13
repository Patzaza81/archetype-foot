// drapeaux.js — drapeau du PAYS DU CHAMPIONNAT, lu uniquement dans le libellé de la compétition (« Pays : Nom »).
// Jamais le pays d'une équipe : un club anglais en Ligue des champions reçoit le symbole de la compétition (Europe),
// pas le drapeau anglais. Pays inconnu ou sans drapeau officiel (Irlande du Nord) : pas de drapeau, le texte reste.
(function (global) {
  "use strict";
  var ISO = {
    "Afrique du Sud": "ZA", "Albanie": "AL", "Algérie": "DZ", "Allemagne": "DE", "Angola": "AO",
    "Antigua-et-Barbuda": "AG", "Arabie Saoudite": "SA", "Argentine": "AR", "Arménie": "AM", "Australie": "AU",
    "Autriche": "AT", "Azerbaïdjan": "AZ", "Bahreïn": "BH", "Bangladesh": "BD", "Belgique": "BE", "Bolivie": "BO",
    "Bosnie-Herzégovine": "BA", "Botswana": "BW", "Brésil": "BR", "Bulgarie": "BG", "Burundi": "BI", "Bélarus": "BY",
    "Cameroun": "CM", "Canada": "CA", "Chili": "CL", "Chine": "CN", "Chypre": "CY", "Colombie": "CO",
    "Corée du Sud": "KR", "Costa Rica": "CR", "Croatie": "HR", "Côte d'Ivoire": "CI", "Danemark": "DK",
    "El Salvador": "SV", "Espagne": "ES", "Estonie": "EE", "Etats-Unis": "US", "États-Unis": "US", "Finlande": "FI",
    "France": "FR", "Géorgie": "GE", "Ghana": "GH", "Gibraltar": "GI", "Grèce": "GR", "Guadeloupe": "GP",
    "Guatemala": "GT", "Guyane Française": "GF", "Honduras": "HN", "Hong Kong": "HK", "Hongrie": "HU", "Inde": "IN",
    "Indonésie": "ID", "Iran": "IR", "Iraq": "IQ", "Irak": "IQ", "Irlande": "IE", "Islande": "IS", "Israël": "IL",
    "Italie": "IT", "Jamaïque": "JM", "Japon": "JP", "Jordanie": "JO", "Kazakhstan": "KZ", "Kenya": "KE",
    "Kirghizistan": "KG", "Kosovo": "XK", "Koweït": "KW", "Lettonie": "LV", "Liban": "LB", "Lituanie": "LT",
    "Luxembourg": "LU", "Malaisie": "MY", "Maldives": "MV", "Malte": "MT", "Maroc": "MA", "Martinique": "MQ",
    "Mexique": "MX", "Moldavie": "MD", "Mongolie": "MN", "Monténégro": "ME", "Mozambique": "MZ", "Myanmar": "MM",
    "Nicaragua": "NI", "Nigeria": "NG", "Norvège": "NO", "Nouvelle-Calédonie": "NC", "Nouvelle-Zélande": "NZ",
    "Ouganda": "UG", "Ouzbékistan": "UZ", "Panama": "PA", "Paraguay": "PY", "Pays-Bas": "NL", "Pologne": "PL",
    "Portugal": "PT", "Pérou": "PE", "Qatar": "QA", "Roumanie": "RO", "Russie": "RU", "Rwanda": "RW",
    "République Tchèque": "CZ", "Saint-Kitts-et-Nevis": "KN", "Serbie": "RS", "Sierra Leone": "SL",
    "Singapour": "SG", "Slovaquie": "SK", "Slovénie": "SI", "Suisse": "CH", "Suriname": "SR", "Suède": "SE",
    "Sénégal": "SN", "Tadjikistan": "TJ", "Tanzanie": "TZ", "Thaïlande": "TH", "Tunisie": "TN",
    "Turkménistan": "TM", "Turquie": "TR", "Ukraine": "UA", "Uruguay": "UY", "Venezuela": "VE", "Viêt-Nam": "VN",
    "Zambie": "ZM", "ÉAU": "AE", "Égypte": "EG", "Équateur": "EC", "Éthiopie": "ET", "Îles Caïmans": "KY",
    "Îles Féroé": "FO"
  };
  // Nations du Royaume-Uni : drapeaux à séquence d'étiquettes (affichés par iOS, Android récent, Windows 11).
  var NATIONS = { "Angleterre": "gbeng", "Écosse": "gbsct", "Pays de Galles": "gbwls" };
  // Zones (compétitions continentales ou mondiales) : un globe, jamais un drapeau de pays.
  var ZONES = { "Europe": "🌍", "Afrique": "🌍", "Asie": "🌏", "Océanie": "🌏", "Amérique du Nord": "🌎",
                "Amérique du Sud": "🌎", "Monde": "🌐" };

  function pays(competition) {
    var c = String(competition || "").replace(/\s+/g, " ").trim();
    var i = c.indexOf(":");
    return i > 0 ? c.slice(0, i).trim() : null;   // pas de « Pays : » -> pas de pays (jamais deviné)
  }
  function depuisIso(code) {
    return String.fromCodePoint.apply(null, code.toUpperCase().split("").map(function (ch) { return 0x1F1E6 + ch.charCodeAt(0) - 65; }));
  }
  function depuisNation(tag) {
    return String.fromCodePoint(0x1F3F4) + tag.split("").map(function (ch) { return String.fromCodePoint(0xE0000 + ch.charCodeAt(0)); }).join("") + String.fromCodePoint(0xE007F);
  }
  function drapeauCompetition(competition) {
    var p = pays(competition);
    if (!p) return { pays: null, symbole: "", type: "aucun" };
    if (ISO[p]) return { pays: p, symbole: depuisIso(ISO[p]), type: "pays" };
    if (NATIONS[p]) return { pays: p, symbole: depuisNation(NATIONS[p]), type: "pays" };
    if (ZONES[p]) return { pays: p, symbole: ZONES[p], type: "zone" };
    return { pays: p, symbole: "", type: "aucun" };
  }
  global.drapeauCompetition = drapeauCompetition;
  global.paysCompetition = pays;
})(typeof window !== "undefined" ? window : this);
