"""
Talk IA - Evaluateur Maileva Docs e-Facture
Version sans mot de passe - nom obligatoire + Google Sheets + nettoyage JSON

Lancement local :
  py -m pip install streamlit requests gspread google-auth
  streamlit run app.py

Secrets Streamlit Cloud :
  TALK_API_KEY   = "ta_cle"
  SPREADSHEET_ID = "1AfJcWbTPMbSkbnthloOOspBSbAxN4ZMc-RmRlncltyA"
  SHEET_NAME     = "Feuille 1"

  [gcp_service_account]
  type            = "service_account"
  project_id      = "talk-ia-eval"
  private_key_id  = "xxx"
  private_key     = "-----BEGIN RSA PRIVATE KEY-----\nxxx\n-----END RSA PRIVATE KEY-----\n"
  client_email    = "talk-ia-eval@talk-ia-eval.iam.gserviceaccount.com"
  client_id       = "xxx"
  auth_uri        = "https://accounts.google.com/o/oauth2/auth"
  token_uri       = "https://oauth2.googleapis.com/token"
"""

import datetime
import json
import re
import time

import gspread
import requests
import streamlit as st
from google.oauth2.service_account import Credentials

# ==============================================================================
#  CONFIGURATION
# ==============================================================================

try:
    API_KEY        = st.secrets["TALK_API_KEY"]
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
    SHEET_NAME     = st.secrets["SHEET_NAME"]
except Exception:
    API_KEY        = "COLLE_TA_CLE_ICI"
    SPREADSHEET_ID = "1AfJcWbTPMbSkbnthloOOspBSbAxN4ZMc-RmRlncltyA"
    SHEET_NAME     = "Feuille 1"

TALK_URL = "https://talk.innovation.docaposte.com/api/TALK/ask"
SCOPES   = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ==============================================================================
#  NETTOYAGE REPONSE TALK IA
# ==============================================================================

def clean_answer(raw: str) -> str:
    if not raw:
        return raw
    text = raw.strip()
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            parts = []
            for key, val in data.items():
                if isinstance(val, str) and val.strip():
                    if key.lower() not in ("titre", "title"):
                        parts.append(f"{key.replace('_', ' ').capitalize()} : {val.strip()}")
                    else:
                        parts.append(val.strip())
                elif isinstance(val, list):
                    items = [str(v) for v in val if str(v).strip()]
                    if items:
                        parts.append("\n".join(f"- {v}" for v in items))
            return "\n\n".join(parts) if parts else text
        elif isinstance(data, str):
            return data.strip()
    except Exception:
        pass
    return text

# ==============================================================================
#  VALIDATION DU NOM
# ==============================================================================

def nom_est_valide(nom: str) -> bool:
    nom = nom.strip()
    return (
        len(nom) >= 3
        and len(nom.split()) >= 2
        and bool(re.match(r"^[a-zA-Z\u00C0-\u024F\s\-]+$", nom))
    )

# ==============================================================================
#  GOOGLE SHEETS
# ==============================================================================

@st.cache_resource
def get_sheet():
    try:
        creds  = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    except Exception:
        return None

def init_headers(sheet):
    try:
        if not sheet.get_all_values():
            sheet.insert_row([
                "Timestamp", "Evaluateur", "Equipe",
                "Question", "Reponse Talk IA", "Score /5",
                "Commentaire", "Latence (ms)"
            ], index=1)
    except Exception:
        pass

def save_row(sheet, entry: dict) -> bool:
    try:
        sheet.append_row([
            entry.get("timestamp", ""),
            entry.get("nom", ""),
            entry.get("equipe", ""),
            entry.get("question", ""),
            entry.get("answer", ""),
            entry.get("score", 0),
            entry.get("explication", ""),
            entry.get("latency_ms", 0),
        ])
        return True
    except Exception:
        return False

# ==============================================================================
#  CONFIG PAGE
# ==============================================================================

st.set_page_config(
    page_title="Talk IA - Evaluateur Maileva",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==============================================================================
#  STYLES
# ==============================================================================

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

  .main-header {
    background: linear-gradient(135deg, #0018A8 0%, #1a35c4 100%);
    color: white; padding: 28px 32px; border-radius: 16px;
    margin-bottom: 28px; box-shadow: 0 8px 32px rgba(0,24,168,0.18);
  }
  .main-header h1 { font-size: 1.7rem; font-weight: 600; margin-bottom: 4px; }
  .main-header p  { font-size: 0.95rem; opacity: 0.85; }

  .badge {
    display: inline-block; background: #00C8A0; color: #0a0f2e;
    font-size: 0.75rem; font-weight: 600; padding: 3px 10px;
    border-radius: 20px; margin-bottom: 12px;
  }
  .user-banner {
    background: #e8ecff; border: 2px solid #0018A8; border-radius: 12px;
    padding: 12px 20px; margin-bottom: 20px;
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  .user-banner .info { font-size: 0.95rem; color: #0018A8; font-weight: 500; flex: 1; }
  .form-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: #d1fae5; border: 1.5px solid #10b981; color: #065f46;
    font-size: 0.78rem; font-weight: 600; padding: 4px 12px;
    border-radius: 20px; white-space: nowrap;
  }
  .form-badge.off { background: #fee2e2; border-color: #ef4444; color: #991b1b; }

  .bubble-q {
    background: #e8ecff; border-left: 4px solid #0018A8;
    padding: 14px 18px; border-radius: 0 12px 12px 0;
    margin: 10px 0; font-size: 0.97rem; color: #0018A8; font-weight: 500;
  }
  .bubble-r {
    background: #f0faf7; border-left: 4px solid #00C8A0;
    padding: 14px 18px; border-radius: 0 12px 12px 0;
    margin: 10px 0; font-size: 0.95rem; line-height: 1.65;
    color: #0a0f2e; white-space: pre-wrap;
  }
  .card {
    background: white; border-radius: 14px; padding: 18px 22px;
    margin-bottom: 14px; box-shadow: 0 2px 12px rgba(0,24,168,0.07);
    border: 1px solid #e8ecff;
  }
  .card-meta { font-size: 0.78rem; color: #6b7280; margin-bottom: 8px; }
  .sbadge {
    display: inline-block; font-size: 0.82rem; font-weight: 600;
    padding: 3px 12px; border-radius: 20px; margin-top: 8px;
  }
  .s5,.s4 { background:#d1fae5; color:#065f46; }
  .s3     { background:#fef3c7; color:#92400e; }
  .s2,.s1 { background:#fee2e2; color:#991b1b; }

  .stat-row { display:flex; gap:14px; margin-bottom:22px; flex-wrap:wrap; }
  .stat-box {
    background:white; border-radius:12px; padding:14px 18px; flex:1;
    min-width:110px; text-align:center;
    box-shadow:0 2px 8px rgba(0,24,168,0.06); border:1px solid #e8ecff;
  }
  .stat-box .val { font-size:1.8rem; font-weight:700; color:#0018A8; line-height:1; }
  .stat-box .lbl { font-size:0.72rem; color:#6b7280; margin-top:4px; }

  .saved-ok {
    background:#d1fae5; border:2px solid #10b981; border-radius:10px;
    padding:10px 16px; color:#065f46; font-size:0.9rem;
    font-weight:500; margin-top:8px;
  }
  hr.soft { border:none; border-top:1px solid #e8ecff; margin:22px 0; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
#  SESSION STATE
# ==============================================================================

for key, val in {
    "user_nom":    "",
    "user_equipe": "",
    "history":     [],
    "pending":     None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==============================================================================
#  ETAPE 1 : NOM OBLIGATOIRE (validation stricte)
# ==============================================================================

if not st.session_state.user_nom:
    st.markdown("""
    <div class="main-header">
      <div class="badge">USAGE INTERNE MAILEVA</div>
      <h1>💬 Talk IA — Evaluateur</h1>
      <p>Avant de commencer, identifiez-vous.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Qui etes-vous ?")
    st.info("Votre nom sera enregistre avec chaque evaluation. Merci d'entrer votre vrai Prenom et Nom.")

    c1, c2 = st.columns(2)
    with c1:
        nom_inp = st.text_input("Prenom et Nom *", placeholder="ex : Sophie Martin")
    with c2:
        eq_inp = st.selectbox("Equipe *", [
            "-- Selectionnez --", "Commercial", "Avant-vente",
            "Marketing", "Support", "Produit", "Direction", "Autre",
        ])

    if st.button("Commencer l'evaluation", type="primary"):
        if not nom_est_valide(nom_inp):
            st.error("Merci d'entrer votre vrai Prenom et Nom (ex : Sophie Martin).")
        elif eq_inp == "-- Selectionnez --":
            st.error("Selectionnez votre equipe.")
        else:
            st.session_state.user_nom    = nom_inp.strip()
            st.session_state.user_equipe = eq_inp
            st.rerun()
    st.stop()

# ==============================================================================
#  APPLICATION PRINCIPALE
# ==============================================================================

nom    = st.session_state.user_nom
equipe = st.session_state.user_equipe

sheet = get_sheet()
if sheet:
    init_headers(sheet)

badge_html = (
    '<span class="form-badge">● Formulaire connecte</span>'
    if sheet else
    '<span class="form-badge off">● Formulaire deconnecte</span>'
)

st.markdown(f"""
<div class="main-header">
  <div class="badge">USAGE INTERNE MAILEVA</div>
  <h1>💬 Talk IA — Evaluateur</h1>
  <p>Testez Talk IA sur Maileva Docs e-Facture et notez les reponses.</p>
</div>
<div class="user-banner">
  <div class="info">
    Connecte : <strong>{nom}</strong> &nbsp;·&nbsp; Equipe : <strong>{equipe}</strong>
  </div>
  {badge_html}
</div>
""", unsafe_allow_html=True)

# ── Stats ──────────────────────────────────────────────────────────────────────

if st.session_state.history:
    scores = [r["score"] for r in st.session_state.history]
    avg    = round(sum(scores) / len(scores), 1)
    nb_ok  = sum(1 for s in scores if s >= 4)
    nb_nok = sum(1 for s in scores if s <= 2)
    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-box"><div class="val">{len(scores)}</div><div class="lbl">Testees</div></div>
      <div class="stat-box"><div class="val">{avg}/5</div><div class="lbl">Score moyen</div></div>
      <div class="stat-box"><div class="val" style="color:#10b981">{nb_ok}</div><div class="lbl">Bonnes (&ge;4)</div></div>
      <div class="stat-box"><div class="val" style="color:#ef4444">{nb_nok}</div><div class="lbl">Mauvaises (&le;2)</div></div>
    </div>
    """, unsafe_allow_html=True)

# ── Zone question ──────────────────────────────────────────────────────────────

st.markdown("<hr class='soft'>", unsafe_allow_html=True)
st.markdown("### Pose une question a Talk IA")

question_input = st.text_input(
    "Question", label_visibility="collapsed", key="question_input",
    placeholder="ex : Quelle offre pour un client qui envoie 500 factures par mois ?",
)

cb, _ = st.columns([2, 5])
with cb:
    envoyer = st.button("Envoyer a Talk IA", type="primary", use_container_width=True)

if envoyer:
    if not question_input.strip():
        st.warning("Ecrivez une question avant d'envoyer.")
    elif st.session_state.pending is not None:
        st.warning("Notez d'abord la reponse precedente.")
    else:
        with st.spinner("Talk IA reflechit..."):
            try:
                t0   = time.time()
                resp = requests.post(
                    TALK_URL,
                    headers={"Content-Type": "application/json",
                             "x-user-api-key": API_KEY},
                    json={"prompt": question_input.strip()},
                    timeout=30,
                )
                lat = int((time.time() - t0) * 1000)

                if resp.status_code == 200:
                    raw = resp.json()
                    raw_answer = (
                        raw.get("answer") or raw.get("response") or raw.get("result")
                        or raw.get("message") or raw.get("text") or raw.get("content")
                        or str(raw)
                    )
                    st.session_state.pending = {
                        "question":   question_input.strip(),
                        "answer":     clean_answer(raw_answer),
                        "latency_ms": lat,
                        "timestamp":  datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "nom":        nom,
                        "equipe":     equipe,
                    }
                    st.rerun()
                elif resp.status_code == 429:
                    st.error("Rate limit — attendez quelques secondes et reessayez.")
                else:
                    st.error(f"Erreur HTTP {resp.status_code} : {resp.text[:200]}")
            except requests.exceptions.Timeout:
                st.error("Talk IA n'a pas repondu. Reessayez.")
            except Exception as e:
                st.error(f"Erreur : {e}")

# ── Notation ───────────────────────────────────────────────────────────────────

if st.session_state.pending:
    p = st.session_state.pending

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    st.markdown("### Reponse de Talk IA")
    st.markdown(f"""
    <div class="bubble-q">Q : {p['question']}</div>
    <div class="bubble-r">{p['answer']}</div>
    """, unsafe_allow_html=True)
    st.caption(f"Latence : {p['latency_ms']} ms")

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    st.markdown("### Notez cette reponse")

    score = st.select_slider(
        "Note", options=[1, 2, 3, 4, 5], value=3,
        format_func=lambda x: {
            1: "1 — Completement faux ou hors sujet",
            2: "2 — Insuffisant ou incorrect",
            3: "3 — Correct mais incomplet",
            4: "4 — Bonne reponse, complete",
            5: "5 — Excellente reponse, precise et complete",
        }[x],
    )
    explication = st.text_area(
        "Pourquoi cette note ?",
        placeholder="ex : La reponse ne mentionne pas le tarif au-dela du forfait...",
        height=100,
    )

    cv, ca = st.columns([2, 1])
    with cv:
        valider = st.button("Valider la note", type="primary", use_container_width=True)
    with ca:
        annuler = st.button("Ignorer", use_container_width=True)

    if valider:
        entry = {**p, "score": score, "explication": explication.strip()}
        if sheet:
            ok = save_row(sheet, entry)
            if ok:
                st.markdown('<div class="saved-ok">✅ Evaluation enregistree</div>',
                            unsafe_allow_html=True)
            else:
                st.warning("Sauvegarde echouee dans le formulaire.")
        else:
            st.warning("Formulaire deconnecte — enregistre en local uniquement.")
        st.session_state.history.append(entry)
        st.session_state.pending = None
        st.rerun()

    if annuler:
        st.session_state.pending = None
        st.rerun()

# ── Historique ─────────────────────────────────────────────────────────────────

if st.session_state.history:
    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    st.markdown(f"### Mes evaluations cette session ({len(st.session_state.history)})")

    for e in reversed(st.session_state.history):
        s     = e["score"]
        label = {5:"Excellente",4:"Bonne",3:"Correcte",2:"Insuffisante",1:"Mauvaise"}.get(s, "")
        stars = "★" * s + "☆" * (5 - s)
        expl  = (f"<br><span style='font-size:0.85rem;color:#6b7280;'>"
                 f"Commentaire : {e['explication']}</span>"
                 if e.get("explication") else "")

        st.markdown(f"""
        <div class="card">
          <div class="card-meta">
            {e['timestamp']} &nbsp;·&nbsp; {e['nom']} ({e['equipe']})
            &nbsp;·&nbsp; {e['latency_ms']} ms
          </div>
          <div class="bubble-q">Q : {e['question']}</div>
          <div style="font-size:0.9rem;color:#374151;line-height:1.6;
                      padding:6px 0;white-space:pre-wrap;">
            {e['answer'][:500]}{'...' if len(e['answer']) > 500 else ''}
          </div>
          <span class="sbadge s{s}">{stars} {label}</span>
          {expl}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    if st.button("Reinitialiser ma session"):
        st.session_state.history = []
        st.session_state.pending = None
        st.rerun()
