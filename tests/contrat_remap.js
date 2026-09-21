// Charge archetype.js dans un contexte sans navigateur (documents factices) et applique remappeEnOngletsApp à des sélections lues sur stdin.
const fs = require("fs"), vm = require("vm");
const code = fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
const doc = { addEventListener: noop, getElementById: () => null, createElement: () => ({ style: {}, classList: { add: noop, toggle: noop }, setAttribute: noop, appendChild: noop, addEventListener: noop }), querySelector: () => null, querySelectorAll: () => [], body: { classList: { contains: () => false, add: noop, remove: noop, toggle: noop } } };
const ctx = { document: doc, window: {}, localStorage: { getItem: () => null, setItem: noop }, console, fetch: noop, setTimeout: noop, ...{ traduitMarche: (m) => m, traduitNiveau: () => ({ etoiles: 1, texte: "" }), traduitRobustesse: () => "", ICONES_ANALYSE: {}, PREUVE_META: {}, PREUVE_META_INCONNUE: {} } };
vm.createContext(ctx);
vm.runInContext(code + "\n;globalThis.__remap = remappeEnOngletsApp; globalThis.__seuils = [SEUIL_COUP_DE_POKER_COTE, SEUIL_COUP_DE_POKER_PROBA];", ctx);
const entrees = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify({ seuils: ctx.__seuils, sorties: entrees.map((sel) => { const r = ctx.__remap(sel); return { P1: r.P1 ? r.P1.marche : null, P2: r.P2 ? r.P2.marche : null, P3: r.P3 ? r.P3.marche : null }; }) }));
