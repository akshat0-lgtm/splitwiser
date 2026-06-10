# Splitwise Voice

Snap a receipt, record a voice note saying who ate what, and it auto-creates an
itemized Splitwise expense.

```
receipt.jpg ─┐
             ├─► Groq Whisper      (voice note → transcript)
voice note ──┘
                  Llama 4 Scout     (receipt image → line items, OCR)
                  GPT-OSS 120B      (items + transcript → who owes what)
                       │
                       ▼
                  Splitwise API     → itemized expense in your group

---

# To do

## Next up
- [ ] **Capture quantity in OCR** — add a `quantity` field to the item schema in
  `OCR_PROMPT` so "2x Margherita" is read correctly. One-line prompt change.
- [ ] **Tighten the split prompt** — iterate on `SPLIT_PROMPT` now that OCR output
  is visible separately. Handle "shared", "wasn't there", and tax/service edge cases.
- [ ] **Anyone can pay** — add a "Who paid?" dropdown (group members) in the UI,
  pass `payer_id` to the backend. `build_shares()` already accepts `payer_id`, so
  the core logic barely changes. Expense still posts from my API key; only the
  recorded payer changes.
Show how much you actually saved


## Later
- [ ] **Multi-user sign-in (Path B)** — OAuth 2.0, per-user access tokens, a session
  layer, and token storage (Supabase). Only `splitwise_client.py` + a token store
  change; the processor stays the same. Biggest jump — defer until the above are solid.
- [ ] **Mobile app** — options: (a) wrap the deployed URL as a PWA / "Add to Home
  Screen" (cheapest, stays web), (b) rebuild the frontend in React Native or Flutter
  against the existing FastAPI backend (API unchanged), (c) stay web. Most stop at (a).

## Known issues / notes
- [ ] HEIC photos (iPhone default) aren't readable by the vision model — convert to
  JPEG first.
- [ ] "Ate nothing" still includes that person's equal share of tax/service by
  design — change the rule in `SPLIT_PROMPT` if zero-total is preferred.
- [ ] Free-tier rate limits (Groq) are fine for occasional bills; not built for scale.

---
\
