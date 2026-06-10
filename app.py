import os
import html
import requests
import streamlit as st

API = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Splitwise Voice", page_icon="🧾", layout="centered")

# ── Splitwise-styled CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
  --sv-green:#1CC29F; --sv-green-dark:#16A085;
  --sv-red:#FF652F;   --sv-ink:#2E3131; --sv-muted:#8A9090;
  --sv-line:#ECEFF1;  --sv-panel:#F4F6F8;
}
html, body, [class*="css"]{ font-family:'Inter',-apple-system,sans-serif; }

/* tighten + center for mobile */
.block-container{ max-width:480px; padding:1.2rem 1rem 4rem; }
#MainMenu, footer, header{ visibility:hidden; }

/* header */
.sv-head{ display:flex; align-items:center; gap:.6rem; margin:.2rem 0 1.2rem; }
.sv-logo{ width:38px;height:38px;border-radius:11px;background:var(--sv-green);
  display:flex;align-items:center;justify-content:center;font-size:20px; }
.sv-title{ font-size:1.45rem;font-weight:800;color:var(--sv-ink);letter-spacing:-.02em;line-height:1; }
.sv-sub{ font-size:.8rem;color:var(--sv-muted);margin-top:2px; }

/* buttons — big tap targets */
.stButton>button, .stFormSubmitButton>button{
  width:100%; border-radius:13px; font-weight:700; font-size:1rem;
  padding:.8rem 1rem; border:none; transition:transform .05s ease;
}
.stButton>button:active{ transform:scale(.99); }
.stButton>button[kind="primary"]{ background:var(--sv-green); color:#fff; }
.stButton>button[kind="primary"]:hover{ background:var(--sv-green-dark); color:#fff; }
.stButton>button[kind="secondary"]{
  background:#fff; color:var(--sv-green); border:1.5px solid var(--sv-green);
}

/* transcript quote */
.sv-quote{ background:var(--sv-panel); border-radius:13px; padding:.8rem 1rem;
  font-size:.95rem; color:var(--sv-ink); margin:.4rem 0 1rem;
  border-left:3px solid var(--sv-green); }
.sv-quote .lbl{ font-size:.72rem;color:var(--sv-muted);text-transform:uppercase;
  letter-spacing:.05em;display:block;margin-bottom:.2rem; }

/* total banner */
.sv-total{ text-align:center; padding:1.1rem; background:var(--sv-panel);
  border-radius:15px; margin-bottom:.8rem; }
.sv-total .amt{ font-size:2rem;font-weight:800;color:var(--sv-ink);letter-spacing:-.02em; }
.sv-total .lbl{ font-size:.8rem;color:var(--sv-muted);margin-top:.1rem; }

/* balance rows — the signature element */
.sv-row{ display:flex;align-items:center;gap:.8rem; padding:.85rem .2rem;
  border-bottom:1px solid var(--sv-line); }
.sv-row:last-child{ border-bottom:none; }
.sv-av{ width:42px;height:42px;border-radius:50%;flex:0 0 42px;
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:1rem;color:#fff; }
.sv-name{ flex:1; min-width:0; }
.sv-name .n{ font-weight:600;color:var(--sv-ink);font-size:1rem; }
.sv-name .s{ font-size:.8rem;color:var(--sv-muted); }
.sv-amt{ font-weight:700;font-size:1.05rem;text-align:right;white-space:nowrap; }
.sv-amt.owed{ color:var(--sv-green); }
.sv-amt.paid{ color:var(--sv-muted); }
.sv-badge{ display:inline-block;background:var(--sv-green);color:#fff;
  font-size:.68rem;font-weight:700;padding:.12rem .45rem;border-radius:6px;
  text-transform:uppercase;letter-spacing:.04em;margin-left:.4rem;vertical-align:middle; }
</style>
""", unsafe_allow_html=True)

# ── header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sv-head">
  <div class="sv-logo">🧾</div>
  <div>
    <div class="sv-title">Splitwise Voice</div>
    <div class="sv-sub">Snap the bill, say who ate what</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── avatar color from name (stable) ───────────────────────────────────────────
_PALETTE = ["#1CC29F", "#5B8DEF", "#F2994A", "#9B6DFF", "#EB5757", "#2D9CDB", "#27AE60"]
def avatar_color(name: str) -> str:
    return _PALETTE[sum(ord(c) for c in name) % len(_PALETTE)]
def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper() if parts else "?"

def money(v, sym="₹"):
    return f"{sym}{float(v):,.2f}"

def render_balances(res):
    split = res["split"]
    owed = split["owed"]
    payer = res.get("payer", {})
    payer_name = payer.get("name", "")
    sym = "₹" if split.get("currency", "INR") == "INR" else ""
    total = float(split["grand_total"])

    rows = ""
    # payer first
    ordered = ([payer_name] if payer_name in owed else []) + \
              [n for n in owed if n != payer_name]
    for name in ordered:
        amt = owed[name]
        col = avatar_color(name)
        av = f'<div class="sv-av" style="background:{col}">{initials(name)}</div>'
        if name == payer_name:
            sub = f"paid {money(total, sym)} · their share {money(amt, sym)}"
            amt_html = f'<div class="sv-amt paid">you paid<span class="sv-badge">payer</span></div>'
        else:
            sub = "owes you"
            amt_html = f'<div class="sv-amt owed">{money(amt, sym)}</div>'
        rows += f"""<div class="sv-row">{av}
          <div class="sv-name"><div class="n">{html.escape(name)}</div>
          <div class="s">{sub}</div></div>{amt_html}</div>"""

    st.markdown(f"""
      <div class="sv-total"><div class="amt">{money(total, sym)}</div>
      <div class="lbl">{html.escape(split.get('description','Total'))}</div></div>
      {rows}
    """, unsafe_allow_html=True)

# ── inputs ────────────────────────────────────────────────────────────────────
groups = requests.get(f"{API}/groups").json()
g = st.selectbox("Group", groups, format_func=lambda x: x["name"])
image = st.file_uploader("Receipt photo", type=["jpg", "jpeg", "png", "webp"])
audio = st.audio_input("Who ate what?")

if image and audio:
    files = {
        "image": (image.name, image.getvalue(), image.type),
        "audio": ("note.wav", audio.getvalue(), "audio/wav"),
    }
    data = {"group_id": g["id"]}

    if st.button("Preview split", type="secondary"):
        with st.spinner("Reading receipt and working out the split…"):
            r = requests.post(f"{API}/preview", files=files, data=data)
        if r.ok:
            res = r.json()
            st.markdown(
                f'<div class="sv-quote"><span class="lbl">Heard</span>'
                f'{html.escape(res["transcript"])}</div>', unsafe_allow_html=True)
            render_balances(res)
            if res["split"].get("notes"):
                st.info(res["split"]["notes"])
            with st.expander("Receipt items"):
                st.json(res["receipt"])
            st.session_state.update(ready=True, files=files, data=data)
        else:
            st.error(r.json().get("detail", "Couldn't read that one — try a clearer photo."))

    if st.session_state.get("ready") and st.button("Save to Splitwise", type="primary"):
        with st.spinner("Saving…"):
            r = requests.post(f"{API}/process-bill",
                              files=st.session_state["files"], data=st.session_state["data"])
        if r.ok:
            st.success("Saved to Splitwise")
            st.markdown(f"[Open expense]({r.json()['url']})")
            st.session_state["ready"] = False
        else:
            st.error(r.json().get("detail", "Save failed — check the split and try again."))