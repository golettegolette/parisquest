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

## Fichiers

- `schema.sql` : tables, sécurité (Row Level Security) et les trois fonctions appelables : `pack_state`, `open_pack`, `visit_place`.
- `places.csv` : les 17 919 lieux (identifiant, type, rareté, position, rayon de visite). Régénéré par `pipeline/build_server.py`.

## Ce qui reste possible

- Créer plusieurs comptes avec plusieurs adresses e-mail (comme sur WikiMasters). Parade possible plus tard : connexion Google ou Apple uniquement, ou numéro de téléphone.
- Simuler sa position GPS avec une application de triche : cela ne touche que les visites, pas les paquets. Les vrais jeux géolocalisés détectent ces cas par des vitesses de déplacement impossibles ; c'est une étape ultérieure.
