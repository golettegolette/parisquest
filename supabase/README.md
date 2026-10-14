# Serveur Parisquest (Supabase)

Le serveur rend les paquets impossibles à tromper. Le téléphone affiche, le serveur décide :

| Qui | Fait quoi |
|---|---|
| Serveur | donne l'heure, compte les paquets (1 toutes les 5 min, 10 au maximum), tire les 5 cartes, enregistre la collection, valide les visites (distance, une par jour) |
| Téléphone | affiche le compte à rebours, demande l'ouverture, montre les cartes |

Changer l'heure du téléphone, modifier la page ou rejouer une requête ne change rien : le serveur recalcule tout avec sa propre horloge, verrouille le compte pendant chaque ouverture, et les tables sont en lecture seule pour les joueurs.

## Mise en place (15 minutes)

1. Créer un compte sur [supabase.com](https://supabase.com), puis **New project** (région : Paris ou Francfort). Noter le mot de passe de la base.
2. **SQL Editor → New query** : coller tout `schema.sql`, cliquer **Run**.
3. **Table Editor → places → Insert → Import data from CSV** : choisir `places.csv`.
4. **Authentication → URL Configuration** : *Site URL* = `https://golettegolette.github.io/parisquest/`.
5. **Project Settings → API** : copier *Project URL* et la clé *anon public*, et les envoyer à Claude (cette clé est faite pour être publique ; ne jamais envoyer la clé *service_role*).

Claude crée alors `supabase/config.json`, reconstruit le site et le publie. Les joueurs se connectent avec un lien reçu par e-mail.

## Paiements (Stripe), dans un second temps

1. Créer un compte [Stripe](https://stripe.com) (en mode test d'abord) et renseigner l'entreprise qui encaisse.
2. **Produits** : créer 7 prix. Pass PariGo, 4 € par mois (récurrent). Paiement unique : 10 paquets à 0,99 €, Pack PariGo à 1,99 €, écus 500 à 0,99 €, 1 200 à 1,99 €, 3 500 à 4,99 €, 8 000 à 9,99 €. Noter les identifiants `price_…`.
3. Installer la [CLI Supabase](https://supabase.com/docs/guides/cli), puis dans le dossier `supabase/` :
   - `supabase functions deploy checkout`
   - `supabase functions deploy stripe-webhook --no-verify-jwt`
   - `supabase secrets set STRIPE_SECRET_KEY=sk_… SITE_URL=https://golettegolette.github.io/parisquest/ STRIPE_PRICE_PASS=price_… STRIPE_PRICE_P10=price_… STRIPE_PRICE_PARIGO=price_… STRIPE_PRICE_E500=price_… STRIPE_PRICE_E1200=price_… STRIPE_PRICE_E3500=price_… STRIPE_PRICE_E8000=price_…`
4. **Stripe → Developers → Webhooks** : point d'arrivée `https://<projet>.supabase.co/functions/v1/stripe-webhook`, événements `checkout.session.completed` et `invoice.paid`. Copier le secret `whsec_…` puis `supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_…`.
5. Ajouter `"payments": true` dans `config.json` : la boutique bascule sur le vrai paiement.

Le webhook vérifie la signature de Stripe, et `credit_purchase` ne crédite jamais deux fois le même paiement.

## Fichiers

- `schema.sql` : tables, sécurité (Row Level Security) et les fonctions : `pack_state`, `open_pack`, `open_parigo_pack`, `visit_place`, `credit_purchase` (réservée au webhook).
- `functions/checkout` et `functions/stripe-webhook` : paiement Stripe Checkout et crédit des achats.
- `places.csv` : les 17 919 lieux (identifiant, type, rareté, position, rayon de visite). Régénéré par `pipeline/build_server.py`.

## Ce qui reste possible

- Créer plusieurs comptes avec plusieurs adresses e-mail (comme sur WikiMasters). Parade possible plus tard : connexion Google ou Apple uniquement, ou numéro de téléphone.
- Simuler sa position GPS avec une application de triche : cela ne touche que les visites, pas les paquets. Les vrais jeux géolocalisés détectent ces cas par des vitesses de déplacement impossibles ; c'est une étape ultérieure.
