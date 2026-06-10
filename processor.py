"""
Two-stage pipeline, both on Groq, both free tier:

  Stage 1 — Groq Whisper
    Voice note → transcript ("Akshat had the pizza, Rahul the beer")

  Stage 2 — Llama 4 Scout (vision)
    Receipt image → structured list of line items + prices
    Scout is multimodal and good at OCR/extraction. We only ask it to READ
    the receipt, not reason about who owes what.

  Stage 3 — GPT-OSS 120B (text reasoning)
    Line items + transcript + group members → per-person amounts as JSON
    OSS 120B is the stronger reasoner. No image needed here, just text.

Splitting OCR and reasoning into separate calls means each model does what
it's actually good at.
"""

import os
import json
import base64

from groq import Groq

WHISPER_MODEL  = os.environ.get("WHISPER_MODEL",  "whisper-large-v3-turbo")
VISION_MODEL   = os.environ.get("VISION_MODEL",   "meta-llama/llama-4-scout-17b-16e-instruct")
REASONING_MODEL = os.environ.get("REASONING_MODEL", "openai/gpt-oss-120b")

_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ── Stage 1: transcription ────────────────────────────────────────────────────

def transcribe(audio_bytes: bytes, filename: str = "note.m4a") -> str:
    resp = _groq.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=WHISPER_MODEL,
    )
    return resp.text.strip()


# ── Stage 2: receipt OCR via Scout vision ────────────────────────────────────

OCR_PROMPT = """You are a receipt parser. Look at the receipt image and extract every line item.
When a line shows multiple units (e.g. "4 x Premium ticket  620"), set "quantity" to that
number (4), put the UNIT price in "unit_price" (155.00), and the line TOTAL in "amount" (620.00).
Keep the quantity OUT of the name — the name should be just the item ("Premium ticket").
For single items, quantity is 1 and unit_price equals amount.
Return ONLY valid JSON, no markdown, in exactly this shape:
{
  "restaurant": "name of the place or 'Unknown'",
  "currency": "INR",
  "items": [
    {"name": "Premium ticket", "amount": 620.00, "quantity": 4, "unit_price": 155.00},
    {"name": "Service charge 10%", "amount": 32.00, "quantity": 1, "unit_price": 32.00}
  ],
  "grand_total": 652.00
}
Include taxes, service charges, tips, and delivery fees as separate line items (quantity 1).
Use the printed prices exactly. grand_total must equal the sum of all item amounts."""


def _media_type(filename: str) -> str:
    f = filename.lower()
    if f.endswith(".png"):  return "image/png"
    if f.endswith(".webp"): return "image/webp"
    if f.endswith((".heic", ".heif")):
        raise ValueError("HEIC not supported — convert to JPEG first.")
    return "image/jpeg"


def ocr_receipt(image_bytes: bytes, image_name: str) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{_media_type(image_name)};base64,{b64}"

    resp = _groq.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text",      "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_completion_tokens=1000,
    )
    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ── Stage 3: split reasoning via GPT-OSS 120B ────────────────────────────────

SPLIT_PROMPT = """You are splitting a restaurant bill among friends.

RECEIPT ITEMS (already parsed from the receipt image):
__ITEMS__

Grand total: __GRAND_TOTAL__ __CURRENCY__

GROUP MEMBERS (use these exact names in your output):
__MEMBERS__

VOICE NOTE (who ate/ordered what):
"__TRANSCRIPT__"

Rules:
- Assign each item to the person(s) the voice note says ordered/ate it.
- If an item is "shared" or unmentioned, split it equally across everyone present.
- Tax, service charge, tip, delivery fees → always split equally across everyone.
- Some items show a quantity and a per-unit price, e.g. "Premium ticket: 620 INR
  (qty 4 @ 155 each)". If the voice note assigns specific units to people
  ("Roshni covered 3 tickets, Akshat had 1"), split that line by unit price:
  Roshni = 3 × 155 = 465, Akshat = 1 × 155 = 155. The units you assign across
  people MUST add up to that line's quantity.
- The per-person totals MUST sum exactly to the grand total.
- If someone is said to have "nothing" or "wasn't there", assign them 0 for food
  items but still include their share of any mandatory service/tax charges unless
  the voice note says they weren't present at all.

Return ONLY valid JSON, no markdown:
{
  "description": "short label e.g. 'Toit dinner'",
  "currency": "INR",
  "grand_total": 1234.50,
  "owed": {"Akshat": 800.50, "Rahul": 434.00},
  "breakdown": [
    {"item": "Penne Arrabbiata", "amount": 320.00, "assigned_to": ["Akshat"]}
  ],
  "notes": "anything ambiguous you had to guess, or empty string"
}"""


def _fmt_item(item: dict, currency: str) -> str:
    line = f"- {item['name']}: {item['amount']} {currency}"
    qty = item.get("quantity", 1)
    if qty and qty != 1:
        up = item.get("unit_price")
        line += f" (qty {qty} @ {up} each)" if up else f" (qty {qty})"
    return line


def split_bill(receipt: dict, transcript: str, members: list[dict]) -> dict:
    member_names = "\n".join(f"- {m['name']}" for m in members)
    currency     = receipt.get("currency", "INR")
    items_text   = "\n".join(_fmt_item(item, currency) for item in receipt["items"])
    prompt = (
        SPLIT_PROMPT
        .replace("__ITEMS__", items_text)
        .replace("__GRAND_TOTAL__", str(receipt["grand_total"]))
        .replace("__CURRENCY__", currency)
        .replace("__MEMBERS__", member_names)
        .replace("__TRANSCRIPT__", transcript)
    )

    resp = _groq.chat.completions.create(
        model=REASONING_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        reasoning_effort="low",
        temperature=0.1,
        max_completion_tokens=4000,
    )
    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ── Full pipeline ─────────────────────────────────────────────────────────────

def process(image_bytes: bytes, image_name: str, audio_bytes: bytes,
            audio_name: str, members: list[dict]) -> tuple[str, dict, dict]:
    """
    Returns (transcript, receipt_ocr, split_result).
    Kept separate so /preview can call this and show intermediate results.
    """
    transcript = transcribe(audio_bytes, audio_name)
    receipt    = ocr_receipt(image_bytes, image_name)
    split      = split_bill(receipt, transcript, members)
    return transcript, receipt, split


# ── Share builder (unchanged) ─────────────────────────────────────────────────

def build_shares(split: dict, members: list[dict], payer_id: int) -> list[dict]:
    name_to_id = {m["name"]: m["id"] for m in members}
    total = round(float(split["grand_total"]), 2)

    owed = {}
    for name, amt in split["owed"].items():
        if name not in name_to_id:
            raise ValueError(f"'{name}' not in group members {list(name_to_id)}")
        owed[name_to_id[name]] = round(float(amt), 2)

    drift = round(total - sum(owed.values()), 2)
    if drift:
        biggest = max(owed, key=owed.get)
        owed[biggest] = round(owed[biggest] + drift, 2)

    shares = []
    for uid, amt in owed.items():
        shares.append({
            "user_id": uid,
            "paid":    total if uid == payer_id else 0.0,
            "owed":    amt,
        })
    if payer_id not in owed:
        shares.append({"user_id": payer_id, "paid": total, "owed": 0.0})
    return shares