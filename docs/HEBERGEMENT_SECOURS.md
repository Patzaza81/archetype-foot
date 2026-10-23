# Hébergement de secours (Cloudflare Pages)

Le site est statique (aucune page n'appelle la fonction Netlify `trigger`). Il peut donc être servi par un autre hébergeur à partir du même dépôt GitHub, sans rien modifier.

Réglages Cloudflare Pages (Workers & Pages → Create → Pages → Connect to Git → `Patzaza81/archetype-foot`) :
- Branche de production : `main`
- Commande de build : `python3 betpawa_validation.py --input data/tickets.json --output data/betpawa_validation.json`
- Dossier de sortie : `/` (racine)
- Variable d'environnement : `PYTHON_VERSION` = `3.12`

Chaque commit du pipeline redéploie le site tout seul. L'adresse sera `https://<nom-du-projet>.pages.dev`.
Un nom de domaine personnel peut ensuite être ajouté (Custom domains) sur Cloudflare Pages ou sur Netlify.
