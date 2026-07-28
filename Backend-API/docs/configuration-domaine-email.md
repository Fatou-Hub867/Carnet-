# Configurer un domaine pour l'envoi d'emails (Resend)

Guide pas-à-pas pour passer du **mode test** (`onboarding@resend.dev`, envoi limité à ta propre adresse) à un **envoi vers n'importe quel destinataire** (patients, médecins), en vérifiant un domaine dans Resend.

> **Pourquoi c'est nécessaire :** Resend n'autorise l'envoi à des destinataires arbitraires que depuis une adresse d'un **domaine que tu as vérifié**. C'est ce qui prouve à Resend (et aux boîtes mail des destinataires) que tu es autorisé à envoyer pour ce domaine.

---

## Prérequis

- [ ] Un **compte Resend** (déjà fait — la clé API est dans `.env`).
- [ ] Un **nom de domaine que tu possèdes** (ex. `mon-cabinet.com`).
  - Si tu n'en as pas : en acheter un chez un registrar (OVH, Namecheap, Gandi, Cloudflare…). Coût : ~1 à 15 €/an.
  - Note l'endroit où tu gères le **DNS** du domaine (souvent le registrar lui-même, ou Cloudflare si tu y as délégué le domaine).

---

## Étape 1 — Ajouter le domaine dans Resend

1. Connecte-toi sur **https://resend.com/domains**.
2. Clique sur **Add Domain**.
3. Saisis ton domaine, ex. `mon-cabinet.com` (sans `www`, sans `@`).
4. Choisis une **région** d'envoi si demandé (peu importe pour commencer).
5. Resend affiche alors une **liste d'enregistrements DNS à créer**. Garde cette page ouverte pour l'étape 2.

Les enregistrements sont généralement de 3 types :

| Type | Rôle | Exemple de nom (host) |
|---|---|---|
| **SPF** (`TXT` ou `MX`) | Autorise les serveurs de Resend à envoyer pour ton domaine | `send.mon-cabinet.com` |
| **DKIM** (`TXT` ou `CNAME`) | Signe cryptographiquement chaque email (anti-falsification) | `resend._domainkey.mon-cabinet.com` |
| **DMARC** (`TXT`, parfois optionnel) | Politique anti-usurpation, améliore la délivrabilité | `_dmarc.mon-cabinet.com` |

> Les valeurs exactes (nom + contenu) sont **générées par Resend et propres à ton domaine**. Ne recopie pas d'exemples trouvés ailleurs — utilise **uniquement** ce que Resend t'affiche.

---

## Étape 2 — Créer les enregistrements DNS chez ton registrar

1. Va dans l'interface **DNS / Zone DNS** de ton domaine (chez ton registrar ou Cloudflare).
2. Pour **chaque** enregistrement fourni par Resend, crée une entrée en recopiant **exactement** :
   - le **Type** (`TXT`, `CNAME` ou `MX`),
   - le **Nom / Host** (ex. `resend._domainkey`),
   - la **Valeur / Content** (la longue chaîne fournie),
   - la **priorité** (uniquement pour les `MX`).
3. Points d'attention fréquents :
   - Certains hébergeurs **ajoutent automatiquement le domaine** au champ « nom ». Si Resend demande `resend._domainkey.mon-cabinet.com` et que ton interface complète déjà `.mon-cabinet.com`, ne saisis que `resend._domainkey`.
   - Ne mets **pas de guillemets** en trop dans la valeur (l'interface les gère).
   - Si tu utilises **Cloudflare**, mets les enregistrements DKIM/SPF en mode **DNS only** (nuage gris), pas « proxied ».

---

## Étape 3 — Vérifier dans Resend

1. Retourne sur la page du domaine dans Resend.
2. Clique sur **Verify** (ou attends la vérification automatique).
3. La **propagation DNS** peut prendre de quelques minutes à quelques heures (parfois jusqu'à 24-48 h selon le registrar).
4. Quand chaque enregistrement passe au vert et que le domaine affiche **Verified ✅**, tu peux envoyer.

> Astuce : tu peux vérifier la propagation d'un enregistrement avec `dig` :
> ```bash
> dig TXT resend._domainkey.mon-cabinet.com +short
> ```

---

## Étape 4 — Mettre à jour le projet

Aucune modification de code n'est nécessaire — l'adresse d'expédition est lue depuis `.env`.

1. Dans **`.env`**, remplace :
   ```
   EMAIL_FROM_ADDRESS=onboarding@resend.dev
   ```
   par une adresse **de ton domaine vérifié**, ex. :
   ```
   EMAIL_FROM_ADDRESS=no-reply@mon-cabinet.com
   ```
2. **Redémarre l'application** (la valeur est lue au démarrage) :
   ```bash
   uv run uvicorn app:app --port 8010 --reload
   ```

> ⚠️ L'adresse `from` **doit appartenir au domaine vérifié**. Si tu as vérifié `mon-cabinet.com`, tu ne peux pas mettre `from = ...@gmail.com`. Le préfixe (`no-reply`, `contact`, `notifications`…) est libre.

---

## Étape 5 — Tester l'envoi vers un destinataire externe

**Option A — test direct de l'API Resend** (indépendant de l'app) :
```bash
curl -s -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer $(grep '^RESEND_API_KEY=' .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"from":"no-reply@mon-cabinet.com","to":"UN_AUTRE_EMAIL@example.com","subject":"Test domaine","html":"<p>Envoi externe OK ✅</p>"}'
```
- Réponse `{"id":"..."}` = envoi accepté vers un destinataire externe 🎉
- `403` = domaine pas (encore) vérifié, ou l'adresse `from` n'appartient pas au domaine.

**Option B — test via l'app** : crée un compte patient avec un email **différent** du tien → l'email de bienvenue doit maintenant arriver.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `You can only send testing emails to your own email address` | Toujours sur `onboarding@resend.dev` | Passer `EMAIL_FROM_ADDRESS` sur le domaine vérifié + redémarrer |
| `403` avec le domaine | Domaine pas encore `Verified`, ou `from` hors domaine | Attendre la propagation / vérifier les enregistrements DNS |
| Domaine reste « Pending » | Enregistrement DNS manquant ou mal recopié | Recontrôler nom/valeur exacts ; retirer un éventuel `.domaine` en trop dans le champ nom |
| Email part mais arrive en **spam** | DMARC/DKIM incomplet | Ajouter l'enregistrement DMARC, attendre la « réputation » d'expéditeur |

---

## Checklist rapide

- [ ] Domaine possédé
- [ ] Domaine ajouté dans resend.com/domains
- [ ] Enregistrements SPF + DKIM (+ DMARC) créés chez le registrar
- [ ] Statut **Verified ✅** dans Resend
- [ ] `EMAIL_FROM_ADDRESS=no-reply@<domaine>` dans `.env`
- [ ] Application redémarrée
- [ ] Test d'envoi vers un email externe réussi

---

*Une fois ces étapes faites, tous les emails de l'app (bienvenue patient, validation/refus médecin, suspension, reset de mot de passe) partiront vers de vrais destinataires, sans autre changement de code.*
