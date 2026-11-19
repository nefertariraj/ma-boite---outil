"""
tab_resultats.py — Onglet « 📣 RÉSULTATS & SOUTENANCE » + Coach IA
==================================================================
Intégration dans app.py (3 lignes) :

    from tab_resultats import render_results_tab, render_ai_coach
    tabs = st.tabs(["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL", "📣 RÉSULTATS & SOUTENANCE"])
    ...
    with tabs[5]:
        render_results_tab(p, p_idx)

Et, en bas de chaque onglet de phase (facultatif) :
        render_ai_coach(p, "define")      # ou measure / analyze / improve / control

Toutes les saisies sont stockées dans p["results_closure"] : elles partent donc
dans votre sauvegarde JSON existante (deep_serialize) sans rien changer d'autre.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lss_ai as AI
import lss_report as R
import lss_stats as S

GAINS_COLS = ["Type", "Description", "Montant annuel (Ar)", "Validé par"]
CP_COLS = ["Que contrôler ?", "Spécification", "Méthode", "Fréquence", "Responsable", "Plan de réaction"]
SIGN_COLS = ["Rôle", "Nom", "Décision", "Date"]


def _closure(p: dict) -> dict:
    c = p.setdefault("results_closure", {})
    c.setdefault("gains", [{"Type": "Hard — ", "Description": "", "Montant annuel (Ar)": 0, "Validé par": ""}])
    c.setdefault("control_plan", [dict.fromkeys(CP_COLS, "")])
    c.setdefault("signoff", [{"Rôle": r, "Nom": "", "Décision": "", "Date": ""} for r in
                             ["Sponsor", "Propriétaire du processus", "Contrôle de gestion", "Master Black Belt"]])
    c.setdefault("lecons", "")
    c.setdefault("next_steps", "")
    return c


def render_results_tab(p: dict, p_idx: int):
    st.header("📣 Résultats du projet & soutenance")
    c = _closure(p)
    k = f"_{p_idx}"

    # ------------------------------------------------------------------ 1. Y
    st.subheader("1. Indicateur de résultat (Y) et sens d'amélioration")
    t0 = R.as_df(p.get("dc_saved_df_json"))
    cols = [x for x in t0.columns if x not in ("ID observation", "Date de modification", "Vague")]
    if not cols:
        st.warning("Aucune donnée T0 : alimentez d'abord la collecte (Measure → Écran 2).")
    else:
        y_default = c.get("y_col") if c.get("y_col") in cols else cols[0]
        a, b = st.columns([3, 1])
        c["y_col"] = a.selectbox("Variable Y (CTQ mesuré)", cols, index=cols.index(y_default), key=f"res_y{k}")
        dirs = ["réduire", "augmenter", "cibler"]
        c["direction"] = b.selectbox("Objectif", dirs, index=dirs.index(c.get("direction", "réduire")), key=f"res_dir{k}")

    facts = R.compute_facts(p)
    ba = facts.get("before_after") or {}

    # ------------------------------------------------------------ 2. Preuve
    st.subheader("2. Preuve avant / après")
    if not ba.get("ok"):
        st.info("Ajoutez au moins une vague de contrôle (Control → T1) contenant la même variable Y.")
    else:
        m = st.columns(4)
        if ba["type"] == "continu":
            m[0].metric("Moyenne T0", f"{ba['moyenne_avant']:.2f}")
            m[1].metric("Moyenne après", f"{ba['moyenne_apres']:.2f}", f"{ba['delta_%']:+.1f} %" if ba.get("delta_%") is not None else None,
                        delta_color="inverse" if c.get("direction") == "réduire" else "normal")
        else:
            m[0].metric("Défauts T0", f"{ba['taux_defaut_avant_%']:.1f} %")
            m[1].metric("Défauts après", f"{ba['taux_defaut_apres_%']:.1f} %")
        m[2].metric("p-value", R._fmt_p(ba["p_value"]))
        if facts.get("sigma_avant") is not None and facts.get("sigma_apres") is not None:
            m[3].metric("Niveau sigma", f"{facts['sigma_apres']}", f"{facts['sigma_apres'] - facts['sigma_avant']:+.2f}")
        (st.success if ba["significatif"] else st.error)(ba["conclusion"])
        _staged_chart(facts)
        if facts.get("waves"):
            st.dataframe(pd.DataFrame(facts["waves"]), use_container_width=True, hide_index=True)
        if facts.get("attr_t0", {}).get("note"):
            st.caption("ℹ️ " + facts["attr_t0"]["note"])

    # ------------------------------------------------- 3. Gains & pérennité
    st.subheader("3. Gains financiers (validés par la finance)")
    st.caption("Hard savings = impact direct sur le compte de résultat ; Soft = productivité, qualité, satisfaction.")
    g = st.data_editor(pd.DataFrame(c["gains"], columns=GAINS_COLS), num_rows="dynamic", use_container_width=True,
                       key=f"res_gains{k}",
                       column_config={"Montant annuel (Ar)": st.column_config.NumberColumn(format="%d", min_value=0)})
    c["gains"] = g.to_dict("records")

    st.subheader("4. Plan de contrôle")
    cp = st.data_editor(pd.DataFrame(c["control_plan"], columns=CP_COLS), num_rows="dynamic",
                        use_container_width=True, key=f"res_cp{k}")
    c["control_plan"] = cp.to_dict("records")

    st.subheader("5. Leçons apprises & prochaines étapes")
    a, b = st.columns(2)
    c["lecons"] = a.text_area("Leçons apprises (une par ligne)", c["lecons"], height=130, key=f"res_les{k}")
    c["next_steps"] = b.text_area("Prochaines étapes / duplication (une par ligne)", c["next_steps"], height=130, key=f"res_nxt{k}")

    st.subheader("6. Validation de clôture")
    so = st.data_editor(pd.DataFrame(c["signoff"], columns=SIGN_COLS), num_rows="dynamic",
                        use_container_width=True, key=f"res_sign{k}",
                        column_config={"Décision": st.column_config.SelectboxColumn(options=["", "Validé", "Validé avec réserves", "Refusé"])})
    c["signoff"] = so.to_dict("records")

    # --------------------------------------------------- 7. Génération PPT
    st.divider()
    st.subheader("7. Générer la soutenance")
    cfg = AI.get_config()
    facts = R.compute_facts(p)  # recalcul avec les gains saisis
    a, b, d = st.columns(3)
    auteur = a.text_input("Black Belt", c.get("auteur", ""), key=f"res_aut{k}")
    sponsor = b.text_input("Sponsor", c.get("sponsor", ""), key=f"res_spo{k}")
    date_txt = d.text_input("Date", datetime.now().strftime("%d/%m/%Y"), key=f"res_date{k}")
    c["auteur"], c["sponsor"] = auteur, sponsor
    phases = st.multiselect("Phases à inclure", ["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"],
                            default=["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"], key=f"res_ph{k}")
    skip = st.toggle("Masquer les diapositives sans données", True, key=f"res_skip{k}")

    col1, col2 = st.columns(2)
    if col1.button("🧠 Rédiger le résumé exécutif" + (" (IA)" if AI.is_available(cfg) else " (hors-ligne)"),
                   use_container_width=True, key=f"res_sum_btn{k}"):
        with st.spinner("Rédaction…"):
            c["summary"] = (AI.executive_summary(p, _facts_for_ai(facts), cfg) if AI.is_available(cfg)
                            else AI.offline_summary(p, facts))
    if c.get("summary"):
        sm = c["summary"]
        sm["resume"] = st.text_area(f"Résumé exécutif — source : {sm.get('source')}", sm.get("resume", ""), height=140, key=f"res_sum{k}")
        sm["messages_cles"] = [l for l in st.text_area("Messages clés (une ligne chacun)", "\n".join(sm.get("messages_cles", [])),
                                                       key=f"res_msg{k}").split("\n") if l.strip()]
        sm["demandes"] = [l for l in st.text_area("Décisions attendues du sponsor", "\n".join(sm.get("demandes", [])),
                                                  key=f"res_dem{k}").split("\n") if l.strip()]

    if col2.button("📊 Générer la soutenance PowerPoint", type="primary", use_container_width=True, key=f"res_gen{k}"):
        with st.spinner("Construction des diapositives…"):
            data = R.build_pptx(p, facts, {"auteur": auteur, "sponsor": sponsor, "date": date_txt,
                                           "phases": phases, "skip_empty": skip, "summary": c.get("summary")})
        st.session_state[f"res_pptx{k}"] = data
    if st.session_state.get(f"res_pptx{k}"):
        name = (p.get("name") or p.get("nom") or "Projet").replace(" ", "_")[:60]
        st.download_button("📥 Télécharger la soutenance (.pptx)", st.session_state[f"res_pptx{k}"],
                           file_name=f"Soutenance_DMAIC_{name}.pptx", use_container_width=True,
                           mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                           key=f"res_dl{k}")
        st.caption("Graphiques natifs PowerPoint (modifiables). Notes d'orateur incluses sur chaque diapositive. "
                   "Pour un PDF : Fichier → Exporter dans PowerPoint, ou importez le fichier dans Google Slides.")


def _staged_chart(facts: dict):
    t0 = S.to_numeric(pd.Series(facts.get("y_t0", []))).dropna().tolist()
    ctrl = [(w, v) for w, v in facts.get("y_ctrl", [])]
    vals = t0 + [float(x) for x in S.to_numeric(pd.Series([v for _, v in ctrl])).tolist()]
    stages = ["T0"] * len(t0) + [w for w, _ in ctrl]
    if len(vals) < 3:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=vals, mode="lines+markers", name=facts.get("y_col"), line=dict(color="#059669")))
    for stg in dict.fromkeys(stages):
        idx = [i for i, s_ in enumerate(stages) if s_ == stg]
        imr = S.imr_chart([vals[i] for i in idx])
        if not imr.get("ok"):
            continue
        for key, dash, col in (("CL", "solid", "#1F2937"), ("UCL", "dash", "#DC2626"), ("LCL", "dash", "#DC2626")):
            fig.add_trace(go.Scatter(x=[idx[0], idx[-1]], y=[imr[key]] * 2, mode="lines", showlegend=False,
                                     line=dict(color=col, dash=dash, width=1)))
        fig.add_annotation(x=idx[0], y=max(vals), text=stg, showarrow=False, xanchor="left")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), title="Carte I-MR par étapes (T0 → vagues)")
    st.plotly_chart(fig, use_container_width=True)


def _facts_for_ai(facts: dict) -> dict:
    keep = ("projet", "y_col", "direction", "baseline", "vsm", "sigma_avant", "sigma_apres", "gains", "gains_total", "waves")
    out = {k: facts[k] for k in keep if k in facts}
    ba = facts.get("before_after") or {}
    out["before_after"] = {k: v for k, v in ba.items() if k != "conclusion"} | {"conclusion": ba.get("conclusion")}
    return out


# ---------------------------------------------------------------------------
# Coach IA réutilisable en bas de chaque phase
# ---------------------------------------------------------------------------
def render_ai_coach(p: dict, phase: str):
    """Revue de jalon de la phase par le Master Black Belt (agents + contrôles automatiques)."""
    import lss_agents as G
    cfg = AI.get_config()
    PH = phase.upper()
    facts = R.compute_facts(p)
    mat = G.maturity(p, facts)
    with st.expander(f"🧠 Revue de jalon {PH} — maturité {mat['scores'].get(PH, 0)} %"):
        for crit, ok, det in mat.get(PH, []):
            st.markdown(f"{'✅' if ok else '❌'} {crit}" + (f" — _{det}_" if det and det != "OK" and not ok else ""))
        for g, ph, msg in G.pitfalls(p, facts):
            if ph == PH:
                st.warning(f"{g} {msg}")
        if st.button("Demander l'avis du Master Black Belt", key=f"coach_{phase}"):
            with st.spinner("Revue en cours…"):
                st.session_state[f"coach_out_{phase}"] = G.run_agent(
                    "revue", f"Réalise la revue de jalon de la phase {PH} : points solides, lacunes bloquantes, "
                             "erreurs méthodologiques, verdict GO / GO sous conditions / NO GO.", p, cfg, facts=facts)
        if st.session_state.get(f"coach_out_{phase}"):
            st.markdown(st.session_state[f"coach_out_{phase}"])
        st.caption("Pour dialoguer avec un expert précis, ouvrez l'onglet 🧠 CENTRE IA.")
