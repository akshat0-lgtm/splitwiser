"""
Single-file Streamlit app for deployment (Streamlit Community Cloud).

Unlike app.py (which calls the FastAPI backend over HTTP), this imports the
pipeline functions directly — so it runs as ONE process with no separate server.
This is the file to point Streamlit Cloud at.

Secrets (GROQ_API_KEY, SPLITWISE_API_KEY) come from Streamlit's secrets manager
in the cloud, or your local .env when running locally.
"""

import os
import html
import streamlit as st

# Push Streamlit secrets into the environment BEFORE importing the pipeline,
# because processor.py / splitwise_client.py read their keys at import time.
for _k in ("GROQ_API_KEY", "SPLITWISE_API_KEY", "WHISPER_MODEL", "VISION_MODEL", "REASONING_MODEL"):
    try:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = st.secrets[_k]
    except Exception:
        pass  # no secrets file locally — rely on .env / real env

from dotenv import load_dotenv
load_dotenv()

from splitwise_client import Splitwise
from processor import process, build_shares

st.set_page_config(page_title="Splitwise Voice", page_icon="🧾", layout="centered")
sw = Splitwise()

# ── Splitwise-styled CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{ --sv-green:#1CC29F; --sv-green-dark:#16A085; --sv-red:#FF652F;
  --sv-ink:#2E3131; --sv-muted:#8A9090; --sv-line:#ECEFF1; --sv-panel:#F4F6F8; }
html, body, [class*="css"]{ font-family:'Inter',-apple-system,sans-serif; }
.block-container{ max-width:480px; padding:1.2rem 1rem 4rem; }
#MainMenu, footer, header{ visibility:hidden; }
.sv-head{ display:flex; align-items:center; gap:.6rem; margin:.2rem 0 1.2rem; }
.sv-logo{ width:38px;height:38px;border-radius:11px;background:var(--sv-green);
  display:flex;align-items:center;justify-content:center;font-size:20px; }
.sv-title{ font-size:1.45rem;font-weight:800;color:var(--sv-ink);letter-spacing:-.02em;line-height:1; }
.sv-sub{ font-size:.8rem;color:var(--sv-muted);margin-top:2px; }
.stButton>button{ width:100%; border-radius:13px; font-weight:700; font-size:1rem;
  padding:.8rem 1rem; border:none; transition:transform .05s ease; }
.stButton>button:active{ transform:scale(.99); }
.stButton>button[kind="primary"]{ background:var(--sv-green); color:#fff; }
.stButton>button[kind="primary"]:hover{ background:var(--sv-green-dark); color:#fff; }
.stButton>button[kind="secondary"]{ background:#fff; color:var(--sv-green); border:1.5px solid var(--sv-green); }
.sv-quote{ background:var(--sv-panel); border-radius:13px; padding:.8rem 1rem; font-size:.95rem;
  color:var(--sv-ink); margin:.4rem 0 1rem; border-left:3px solid var(--sv-green); }
.sv-quote .lbl{ font-size:.72rem;color:var(--sv-muted);text-transform:uppercase;
  letter-spacing:.05em;display:block;margin-bottom:.2rem; }
.sv-total{ text-align:center; padding:1.1rem; background:var(--sv-panel); border-radius:15px; margin-bottom:.8rem; }
.sv-total .amt{ font-size:2rem;font-weight:800;color:var(--sv-ink);letter-spacing:-.02em; }
.sv-total .lbl{ font-size:.8rem;color:var(--sv-muted);margin-top:.1rem; }
.sv-row{ display:flex;align-items:center;gap:.8rem; padding:.85rem .2rem; border-bottom:1px solid var(--sv-line); }
.sv-row:last-child{ border-bottom:none; }
.sv-av{ width:42px;height:42px;border-radius:50%;flex:0 0 42px;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;color:#fff; }
.sv-name{ flex:1; min-width:0; }
.sv-name .n{ font-weight:600;color:var(--sv-ink);font-size:1rem; }
.sv-name .s{ font-size:.8rem;color:var(--sv-muted); }
.sv-amt{ font-weight:700;font-size:1.05rem;text-align:right;white-space:nowrap; }
.sv-amt.owed{ color:var(--sv-green); }
.sv-amt.paid{ color:var(--sv-muted); }
.sv-badge{ display:inline-block;background:var(--sv-green);color:#fff;font-size:.68rem;font-weight:700;
  padding:.12rem .45rem;border-radius:6px;text-transform:uppercase;letter-spacing:.04em;margin-left:.4rem;vertical-align:middle; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sv-head"><div class="sv-logo">🧾</div>
  <div><div class="sv-title">Splitwise Voice</div>
  <div class="sv-sub">Snap the bill, say who ate what</div></div></div>
""", unsafe_allow_html=True)

_PALETTE = ["#1CC29F", "#5B8DEF", "#F2994A", "#9B6DFF", "#EB5757", "#2D9CDB", "#27AE60"]
def avatar_color(name): return _PALETTE[sum(ord(c) for c in name) % len(_PALETTE)]
def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper() if parts else "?"
def money(v, sym="₹"): return f"{sym}{float(v):,.2f}"

def render_balances(split, payer_name):
    owed = split["owed"]
    sym = "₹" if split.get("currency", "INR") == "INR" else ""
    total = float(split["grand_total"])
    ordered = ([payer_name] if payer_name in owed else []) + [n for n in owed if n != payer_name]
    rows = ""
    for name in ordered:
        amt = owed[name]; col = avatar_color(name)
        av = f'<div class="sv-av" style="background:{col}">{initials(name)}</div>'
        if name == payer_name:
            sub = f"paid {money(total, sym)} · their share {money(amt, sym)}"
            amt_html = '<div class="sv-amt paid">you paid<span class="sv-badge">payer</span></div>'
        else:
            sub = "owes you"
            amt_html = f'<div class="sv-amt owed">{money(amt, sym)}</div>'
        rows += (f'<div class="sv-row">{av}<div class="sv-name"><div class="n">'
                 f'{html.escape(name)}</div><div class="s">{sub}</div></div>{amt_html}</div>')
    st.markdown(f'<div class="sv-total"><div class="amt">{money(total, sym)}</div>'
                f'<div class="lbl">{html.escape(split.get("description","Total"))}</div></div>{rows}',
                unsafe_allow_html=True)

# ── inputs ────────────────────────────────────────────────────────────────────
groups = sw.groups()
g = st.selectbox("Group", groups, format_func=lambda x: x["name"])
image = st.file_uploader("Receipt photo", type=["jpg", "jpeg", "png", "webp"])
audio = st.audio_input("Who ate what?")

if image and audio:
    if st.button("Preview split", type="secondary"):
        with st.spinner("Reading receipt and working out the split…"):
            try:
                members = sw.members(g["id"])
                me = sw.current_user()
                payer_name = (me.get("first_name", "") + " " + (me.get("last_name") or "")).strip()
                transcript, receipt, split = process(
                    image.getvalue(), image.name,
                    audio.getvalue(), "note.wav", members)
                shares = build_shares(split, members, payer_id=me["id"])
                st.session_state.update(
                    ready=True, group_id=g["id"], split=split,
                    shares=shares, payer_name=payer_name,
                    transcript=transcript, receipt=receipt)
            except Exception as e:
                st.session_state["ready"] = False
                st.error(f"Couldn't read that one — try a clearer photo. ({e})")

if st.session_state.get("ready"):
    st.markdown(f'<div class="sv-quote"><span class="lbl">Heard</span>'
                f'{html.escape(st.session_state["transcript"])}</div>', unsafe_allow_html=True)
    render_balances(st.session_state["split"], st.session_state["payer_name"])
    if st.session_state["split"].get("notes"):
        st.info(st.session_state["split"]["notes"])
    with st.expander("Receipt items"):
        st.json(st.session_state["receipt"])

    if st.button("Save to Splitwise", type="primary"):
        with st.spinner("Saving…"):
            try:
                split = st.session_state["split"]
                expense = sw.create_expense(
                    group_id=st.session_state["group_id"],
                    description=split.get("description", "Bill"),
                    cost=float(split["grand_total"]),
                    shares=st.session_state["shares"],
                    currency=split.get("currency", "INR"))
                st.success("Saved to Splitwise")
                st.markdown(f"[Open expense](https://secure.splitwise.com/expenses/{expense['id']})")
                st.session_state["ready"] = False
            except Exception as e:
                st.error(f"Save failed — check the split and try again. ({e})")
