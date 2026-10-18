# Serveur Parisquest (Supabase)

Le serveur rend les paquets impossibles à tromper. Le téléphone affiche, le serveur décide :

| Qui | Fait quoi |
|---|---|
| Serveur | donne l'heure, compte les paquets (1 toutes les 10 min, 10 au maximum), tire les 5 cartes, enregistre la collection, valide les visites (distance, une par jour) |
| Téléphone | affiche le compte à rebours, demande l'ouverture, montre les cartes |

Changer l'heure du téléphone, modifier la page ou rejouer une requête ne change rien : le serveur recalcule tout avec sa propre horloge, verrouille le compte pendant chaque ouverture, et les tables sont en lecture seule pour les joueurs.

## Mise en place (15 minutes)

1. Créer un compte sur [supabase.com](https://supabase.com), puis **New project** (région : Paris ou Francfort). Noter le mot de passe de la base.
2. **SQL Editor → New query** : coller tout `schema.sql`, cliquer **Run**. Puis une nouvelle requête avec tout `social.sql`, **Run**.
   Puis, **après** l'import de l'étape 3, dans cet ordre : `direction_a.sql` (capture sur place, classements), `places_arr.sql` (arrondissement de chaque lieu), `quetes.sql` (paquets à 10 minutes, quêtes), `ponts_doublons.sql` (ponts en double : on garde la version rue), `acces.sql` (capture selon l'accès public), `places_arr.sql` à nouveau (arrondissements corrigés) et `quests_data.sql` (les 159 quêtes).
   Facultatif mais conseillé : **Database → Extensions → pg_cron** activé avant `social.sql`, pour clôturer les enchères chaque minute (sinon elles se clôturent à chaque consultation du Marché).
3. **Table Editor → places → Insert → Import data from CSV** : choisir `places.csv` (colonnes id, kind, family, tier, lat, lon, reach_m).
   **Database → Publications → supabase_realtime** : vérifier que `messages` et `guild_messages` y figurent (messages en direct).
4. **Authentication → URL Configuration** : *Site URL* = `https://golettegolette.github.io/parisquest/`.
5. **Project Settings → API** : copier *Project URL* et la clé *anon public*, et les envoyer à Claude (cette clé est faite pour être publique ; ne jamais envoyer la clé *service_role*).

Claude crée alors `supabase/config.json`, reconstruit le site et le publie. Les joueurs se connectent avec un lien reçu par e-mail.

## Paiements (Stripe), dans un second temps

1. Créer un compte [Stripe](https://stripe.com) (en mode test d'abord) et renseigner l'entreprise qui encaisse.
2. **Produits** : créer 7 prix. Pass PariGo, 4 € par mois (récurrent). Paiement unique : 10 paquets à 0,99 €, Pack PariGo à 1,49 €, écus 500 à 0,99 €, 1 200 à 1,99 €, 3 500 à 4,99 €, 8 000 à 9,99 €. Noter les identifiants `price_…`.
3. Installer la [CLI Supabase](https://supabase.com/docs/guides/cli), puis dans le dossier `supabase/` :
   - `supabase functions deploy checkout`
   - `supabase functions deploy stripe-webhook --no-verify-jwt`
   - `supabase secrets set STRIPE_SECRET_KEY=sk_… SITE_URL=https://golettegolette.github.io/parisquest/ STRIPE_PRICE_PASS=price_… STRIPE_PRICE_P10=price_… STRIPE_PRICE_PARIGO=price_… STRIPE_PRICE_E500=price_… STRIPE_PRICE_E1200=price_… STRIPE_PRICE_E3500=price_… STRIPE_PRICE_E8000=price_…`
4. **Stripe → Developers → Webhooks** : point d'arrivée `https://<projet>.supabase.co/functions/v1/stripe-webhook`, événements `checkout.session.completed` et `invoice.paid`. Copier le secret `whsec_…` puis `supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_…`.
5. Ajouter `"payments": true` dans `config.json` : la boutique bascule sur le vrai paiement.

Le webhook vérifie la signature de Stripe, et `credit_purchase` ne crédite jamais deux fois le même paiement.

## Fichiers

- `direction_a.sql` : version 1 « Collectionne Paris en le parcourant » : `game_state`, `open_daily_pack` (5 lieux à découvrir près du joueur, un paquet par jour), `visit_place` (capture de n'importe quel lieu sur place, 60 visites par jour, contrôle de vitesse), `collectors` (classements Paris, arrondissement, amis), `arr_masters`, `my_stats`. Désactive les anciens paquets toutes les 5 minutes.
- `places_arr.sql` : arrondissement de chaque lieu (généré par `pipeline/build_server.py`).
- `quetes.sql` : paquets toutes les 10 minutes (2 avec le Pass), fin du paquet du jour, quêtes : `claim_quest` (vérifie la progression et crédite les PQ une seule fois), `quest_board`, `my_titles`, `quest_leaders`.
- `ponts_doublons.sql` : retire les 49 ponts en double (version « pont » de Wikidata) et reporte les cartes déjà possédées sur la version « rue » (généré par `pipeline/ponts.py`). Peut être relancé sans risque.
- `acces.sql` : voies privées fermées placées à leur entrée, rayons de capture allongés pour les lieux loin de la rue (généré par `pipeline/build_server.py` après `pipeline/acces.py`). Peut être relancé.
- `quests_data.sql` : les quêtes et leurs lieux (généré par `pipeline/quests.py`, après `pipeline/lines.py` pour les lignes de transport).

- `schema.sql` : tables, sécurité (Row Level Security) et les fonctions : `pack_state`, `open_pack`, `open_parigo_pack`, `visit_place`, `credit_purchase` (réservée au webhook).
- `social.sql` : pseudos, amis et blocages, messages privés, échanges, Marché aux enchères (séquestre des cartes et des écus, surenchère remboursée, anti-dernière seconde, 5 % de commission), classement, guildes, batailles entre amis, signalements. Règles : une carte cédée repart au niveau 1 sans sceau « Visité » ; toutes les cartes sont échangeables et vendables ; pseudo obligatoire et unique.
- `functions/checkout` et `functions/stripe-webhook` : paiement Stripe Checkout et crédit des achats.
- `places.csv` : les 17 919 lieux (identifiant, type, rareté, position, rayon de visite). Régénéré par `pipeline/build_server.py`.

## Tests

Tout a été vérifié sur PostgreSQL 16 avec une imitation de l'authentification Supabase, puis de bout en bout avec deux joueurs dans le navigateur : paquets, pseudos, amis, messages, échange accepté (cartes transférées, niveau remis à 1), vente aux enchères, surenchère, achat immédiat, clôtures, classement, guilde, bataille. Écritures directes dans les tables refusées, fonctions internes inaccessibles, enchères simultanées sans perte ni création d'écus, échange devenu impossible annulé sans aucun mouvement.

## Ce qui reste possible

- Créer plusieurs comptes avec plusieurs adresses e-mail (comme sur WikiMasters). Parade possible plus tard : connexion Google ou Apple uniquement, ou numéro de téléphone.
- Simuler sa position GPS avec une application de triche : cela ne touche que les visites, pas les paquets. Les vrais jeux géolocalisés détectent ces cas par des vitesses de déplacement impossibles ; c'est une étape ultérieure.
