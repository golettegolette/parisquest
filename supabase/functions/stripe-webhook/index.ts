// Parisquest : reçoit les événements Stripe et crédite les achats (écus, Pass PariGo).
// Déploiement : supabase functions deploy stripe-webhook --no-verify-jwt
// Secrets requis : STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
// Dans Stripe : Developers → Webhooks → endpoint https://<projet>.supabase.co/functions/v1/stripe-webhook
//   événements : checkout.session.completed, invoice.paid
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

// Ce que crédite chaque offre à paiement unique
const GOODS: Record<string, { ecus?: number; packs?: number; parigo?: number }> = {
  e500: { ecus: 500 }, e1200: { ecus: 1200 }, e3500: { ecus: 3500 }, e8000: { ecus: 8000 },
  p10: { packs: 10 }, parigo: { parigo: 1 },
};
const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const enc = new TextEncoder();

// Vérifie la signature Stripe (HMAC-SHA256 de "horodatage.corps"), tolérance 5 minutes.
async function verify(body: string, header: string | null, secret: string): Promise<boolean> {
  if (!header) return false;
  const parts = Object.fromEntries(header.split(",").map((kv) => kv.split("=", 2)).filter((x) => x.length === 2).map(([k, v]) => [k, v]));
  const t = Number(parts["t"]);
  const sigs = header.split(",").filter((kv) => kv.startsWith("v1=")).map((kv) => kv.slice(3));
  if (!t || !sigs.length || Math.abs(Date.now() / 1000 - t) > 300) return false;
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(`${t}.${body}`)));
  const hex = Array.from(mac, (b) => b.toString(16).padStart(2, "0")).join("");
  return sigs.some((s) => s.length === hex.length && [...s].reduce((d, c, i) => d | (c.charCodeAt(0) ^ hex.charCodeAt(i)), 0) === 0);
}
async function stripe(path: string) {
  const r = await fetch(`https://api.stripe.com/v1/${path}`, { headers: { Authorization: `Bearer ${Deno.env.get("STRIPE_SECRET_KEY")}` } });
  if (!r.ok) throw new Error(`Stripe ${path} ${r.status}`);
  return r.json();
}
// Fin de période d'un abonnement (champ déplacé sur les lignes dans les versions récentes de l'API)
const periodEnd = (sub: any) => sub.current_period_end ?? sub.items?.data?.[0]?.current_period_end;
async function credit(user: string, ref: string, g: { ecus?: number; packs?: number; parigo?: number }, passUntilSec?: number) {
  const { error } = await admin.rpc("credit_purchase", {
    p_user: user, p_ref: ref, p_ecus: g.ecus ?? 0, p_packs: g.packs ?? 0, p_parigo: g.parigo ?? 0,
    p_pass_until: passUntilSec ? new Date(passUntilSec * 1000).toISOString() : null,
  });
  if (error) throw new Error(error.message);
}

Deno.serve(async (req) => {
  const body = await req.text();
  if (!(await verify(body, req.headers.get("Stripe-Signature"), Deno.env.get("STRIPE_WEBHOOK_SECRET")!))) return new Response("signature invalide", { status: 400 });
  const ev = JSON.parse(body);
  try {
    if (ev.type === "checkout.session.completed") {
      const s = ev.data.object;
      const user = s.client_reference_id ?? s.metadata?.user_id;
      if (!user) return new Response("sans joueur", { status: 200 });
      if (s.mode === "payment" && s.payment_status === "paid") {
        const g = GOODS[s.metadata?.sku];
        if (g) await credit(user, s.id, g);
      } else if (s.mode === "subscription" && s.subscription) {
        const sub = await stripe(`subscriptions/${s.subscription}`);
        await credit(user, s.id, {}, periodEnd(sub));
      }
    } else if (ev.type === "invoice.paid") {
      // Renouvellement mensuel du Pass
      const inv = ev.data.object;
      const subId = inv.subscription ?? inv.parent?.subscription_details?.subscription;
      if (subId) {
        const sub = await stripe(`subscriptions/${subId}`);
        const user = sub.metadata?.user_id;
        if (user) await credit(user, inv.id, {}, periodEnd(sub));
      }
    }
    return new Response("ok", { status: 200 });
  } catch (e) {
    console.error(e);
    return new Response("erreur", { status: 500 }); // Stripe réessaiera ; credit_purchase est idempotente
  }
});
