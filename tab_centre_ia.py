"""
tab_centre_ia.py — Centre IA (équipe d'agents) et portefeuille de projets
========================================================================
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lss_agents as G
import lss_ai as AI
import lss_report as R

SHORT = {"cadrage": "Cadrage", "stats": "Statisticien", "causes": "Causes racines", "solutions": "Solutions Lean",
         "changement": "Changement", "revue": "Master Black Belt", "soutenance": "Soutenance"}
PHASE_COL = {"DEFINE": "#2563EB", "MEASURE": "#0D9488", "ANALYZE": "#7C3AED", "IMPROVE": "#EA580C", "CONTROL": "#059669"}


def _facts(p):
    try:
        return R.compute_facts(p)
    except Exception:
        return {}


def render_ai_center(p: dict, p_idx: int):
    k = f"_{p_idx}"
    cfg = AI.get_config()
    st.header("🧠 Centre IA — votre équipe d'experts")
    if AI.is_available(cfg):
        st.success(f"IA active ({cfg['provider'].capitalize()}). Les agents raisonnent sur les données réelles de ce projet.")
    else:
        st.warning("IA hors-ligne : les agents affichent uniquement les contrôles automatiques. "
                   "Ajoutez une clé gratuite Groq dans les Secrets pour activer les analyses rédigées.")
    facts = _facts(p)
    mat = G.maturity(p, facts)
    warn = G.pitfalls(p, facts)

    # ------------------------------------------------------------ maturité
    st.subheader("1. Tableau de bord de maturité du projet")
    c = st.columns(6)
    c[0].metric("Maturité globale", f"{mat['global']} %")
    for i, ph in enumerate(G.PHASES, start=1):
        c[i].metric(ph.capitalize(), f"{mat['scores'][ph]} %")
    fig = go.Figure(go.Bar(x=list(mat["scores"].values()), y=G.PHASES, orientation="h",
                           marker_color=[PHASE_COL[ph] for ph in G.PHASES],
                           text=[f"{v} %" for v in mat["scores"].values()], textposition="auto"))
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0, 100]),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Voir la grille de jalons détaillée"):
        for ph in G.PHASES:
            st.markdown(f"**{ph} — {mat['scores'][ph]} %**")
            for crit, ok, det in mat[ph]:
                st.markdown(f"{'✅' if ok else '❌'} {crit}" + (f" — _{det}_" if det and det != "OK" else ""))

    st.subheader("2. Garde-fous méthodologiques")
    if not warn:
        st.success("Aucune alerte détectée sur les données actuelles.")
    for g, ph, msg in warn:
        (st.error if g == "🔴" else st.warning if g == "🟠" else st.info)(f"{g} **{ph}** — {msg}")

    # ------------------------------------------------------------ orchestrateur
    st.subheader("3. Poser une question à l'équipe")
    st.caption("Le Master Black Belt oriente votre question vers l'expert le plus compétent.")
    q = st.text_area("Votre question", key=f"ia_q{k}", height=90,
                     placeholder="ex. Mes 3 agences ont-elles vraiment des délais différents, et que dois-je faire ?")
    if st.button("📨 Envoyer à l'équipe", type="primary", key=f"ia_send{k}") and q.strip():
        with st.spinner("Orientation et analyse…"):
            agent = G.route(q, cfg)
            ans = G.run_agent(agent, q, p, cfg, history=_hist(p, agent), facts=facts)
        _log(p, agent, q, ans)
        st.session_state[f"ia_last{k}"] = (agent, ans)
    if st.session_state.get(f"ia_last{k}"):
        agent, ans = st.session_state[f"ia_last{k}"]
        a = G.AGENTS[agent]
        st.markdown(f"**{a.icon} Réponse de {a.name}**")
        st.markdown(ans)

    # ------------------------------------------------------------ agents
    st.subheader("4. Consulter un expert directement")
    keys = list(G.AGENTS)
    sel = st.radio("Expert", keys, horizontal=True, key=f"ia_agent{k}",
                   format_func=lambda x: f"{G.AGENTS[x].icon} {SHORT[x]}")
    a = G.AGENTS[sel]
    st.caption(f"Spécialité : {a.mission}")
    cols = st.columns(len(a.quick))
    for i, (lab, prompt) in enumerate(a.quick):
        if cols[i].button(lab, key=f"ia_quick_{sel}_{i}{k}", use_container_width=True):
            with st.spinner(f"{a.name} analyse le projet…"):
                ans = G.run_agent(sel, prompt, p, cfg, history=_hist(p, sel), facts=facts)
            _log(p, sel, lab, ans)
    hist = _hist(p, sel)
    if hist:
        for m in hist[-8:]:
            with st.chat_message("user" if m["role"] == "user" else "assistant"):
                st.markdown(m["content"])
        b1, b2 = st.columns([1, 4])
        if b1.button("🗑️ Effacer", key=f"ia_clear_{sel}{k}"):
            p.setdefault("ai_chats", {})[sel] = []
            st.rerun()
        b2.download_button("📥 Exporter l'échange (.md)", _to_md(sel, hist), file_name=f"echange_{sel}.md", key=f"ia_dl_{sel}{k}")
    follow = st.text_input(f"Poursuivre avec {a.name}", key=f"ia_follow_{sel}{k}")
    if st.button("Envoyer", key=f"ia_follow_btn_{sel}{k}") and follow.strip():
        with st.spinner("…"):
            ans = G.run_agent(sel, follow, p, cfg, history=_hist(p, sel), facts=facts)
        _log(p, sel, follow, ans)
        st.rerun()

    # ------------------------------------------------------------ revue complète
    st.subheader("5. Revue complète du projet par le Master Black Belt")
    if st.button("🧠 Lancer la revue complète", key=f"ia_full{k}"):
        with st.spinner("Revue de toutes les phases…"):
            rep = G.full_review(p, cfg)
        p.setdefault("ai_reports", []).append(rep)
    reps = p.get("ai_reports") or []
    if reps:
        last = reps[-1]
        st.caption(f"Dernière revue : {last['date']} — maturité globale {last['maturite']['global']} %")
        st.markdown(last["avis"])
        if len(reps) > 1:
            hist_df = pd.DataFrame([{"Date": r["date"], "Maturité (%)": r["maturite"]["global"]} for r in reps])
            st.line_chart(hist_df.set_index("Date"))


def _hist(p, agent) -> list:
    return list((p.get("ai_chats") or {}).get(agent, []))


def _log(p, agent, q, ans):
    chats = p.setdefault("ai_chats", {})
    h = chats.setdefault(agent, [])
    h += [{"role": "user", "content": q}, {"role": "assistant", "content": ans}]
    chats[agent] = h[-20:]


def _to_md(agent, hist) -> str:
    a = G.AGENTS[agent]
    out = [f"# Échange avec {a.name}", ""]
    for m in hist:
        out += [f"**{'Black Belt' if m['role'] == 'user' else a.name}** :", "", m["content"], ""]
    return "\n".join(out)


# ===========================================================================
# Portefeuille
# ===========================================================================
def render_portfolio(projects: list):
    if not projects:
        return
    rows = []
    for p in projects:
        try:
            f = R.compute_facts(p)
            m = G.maturity(p, f)
            ba = f.get("before_after") or {}
            rows.append({"Projet": p.get("name") or p.get("nom"), "Phase": p.get("status", ""),
                         "Maturité (%)": m["global"], "Sigma avant": f.get("sigma_avant"), "Sigma après": f.get("sigma_apres"),
                         "Amélioration prouvée": "Oui" if ba.get("significatif") else ("Non" if ba.get("ok") else "—"),
                         "Gains (M Ar/an)": round((f.get("gains_total") or 0) / 1e6, 1),
                         "COPQ (M Ar/an)": round(float((p.get("charte") or {}).get("copq_total") or 0) / 1e6, 1),
                         "Alertes bloquantes": sum(1 for g, _, _ in G.pitfalls(p, f) if g == "🔴")})
        except Exception as exc:
            rows.append({"Projet": p.get("name") or p.get("nom"), "Phase": p.get("status", ""), "Maturité (%)": None,
                         "Alertes bloquantes": f"erreur : {exc}"[:60]})
    d = pd.DataFrame(rows)
    with st.expander(f"📊 Portefeuille de projets ({len(d)})", expanded=True):
        c = st.columns(4)
        c[0].metric("Projets", len(d))
        c[1].metric("Gains validés", f"{d.get('Gains (M Ar/an)', pd.Series([0])).fillna(0).sum():.1f} M Ar/an")
        c[2].metric("COPQ adressé", f"{d.get('COPQ (M Ar/an)', pd.Series([0])).fillna(0).sum():.1f} M Ar/an")
        c[3].metric("Maturité moyenne", f"{pd.to_numeric(d['Maturité (%)'], errors='coerce').mean():.0f} %")
        st.dataframe(d, use_container_width=True, hide_index=True,
                     column_config={"Maturité (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d %%")})
