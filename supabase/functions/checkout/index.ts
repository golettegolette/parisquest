// Parisquest : crée une session de paiement Stripe Checkout pour le joueur connecté.
// Déploiement : supabase functions deploy checkout
// Secrets requis : STRIPE_SECRET_KEY, SITE_URL, STRIPE_PRICE_PASS, STRIPE_PRICE_P10, STRIPE_PRICE_PARIGO, STRIPE_PRICE_E500, STRIPE_PRICE_E1200, STRIPE_PRICE_E3500, STRIPE_PRICE_E8000, STRIPE_PRICE_ARR
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const OFFERS: Record<string, { mode: "payment" | "subscription"; env: string }> = {
  pass: { mode: "subscription", env: "STRIPE_PRICE_PASS" },
  p10: { mode: "payment", env: "STRIPE_PRICE_P10" },
  parigo: { mode: "payment", env: "STRIPE_PRICE_PARIGO" },
  e500: { mode: "payment", env: "STRIPE_PRICE_E500" },
  e1200: { mode: "payment", env: "STRIPE_PRICE_E1200" },
  e3500: { mode: "payment", env: "STRIPE_PRICE_E3500" },
  e8000: { mode: "payment", env: "STRIPE_PRICE_E8000" },
};
// Pack Arrondissement : un seul prix Stripe (2,49 €), l'arrondissement voyage dans les métadonnées (sku « arr1 » à « arr20 »)
const ARR_OFFER = { mode: "payment" as const, env: "STRIPE_PRICE_ARR" };
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "méthode non autorisée" }, 405);

  // Joueur connecté (jeton de session transmis par supabase-js)
  const supa = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
  });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) return json({ error: "non connecté" }, 401);

  const { sku } = await req.json().catch(() => ({}));
  const arr = /^arr([1-9]|1[0-9]|20)$/.test(String(sku)) ? Number(String(sku).slice(3)) : 0;
  const offer = arr ? ARR_OFFER : OFFERS[sku as string];
  const price = offer && Deno.env.get(offer.env);
  if (!offer || !price) return json({ error: "offre inconnue" }, 400);

  // Retour toujours vers le site du jeu (jamais vers une adresse fournie par le client)
  const site = Deno.env.get("SITE_URL")!;
  const form = new URLSearchParams({
    mode: offer.mode,
    "line_items[0][price]": price,
    "line_items[0][quantity]": "1",
    client_reference_id: user.id,
    success_url: `${site}?achat=ok`,
    cancel_url: `${site}?achat=annule`,
    "metadata[user_id]": user.id,
    "metadata[sku]": arr ? "arr" : sku,
    ...(arr ? { "metadata[arr]": String(arr) } : {}),
    locale: "fr",
  });
  if (user.email) form.set("customer_email", user.email);
  if (offer.mode === "subscription") form.set("subscription_data[metadata][user_id]", user.id);
  else form.set("payment_intent_data[metadata][user_id]", user.id);

  const r = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: { Authorization: `Bearer ${Deno.env.get("STRIPE_SECRET_KEY")}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  const s = await r.json();
  if (!r.ok) return json({ error: s?.error?.message ?? "Stripe indisponible" }, 502);
  return json({ url: s.url });
});
