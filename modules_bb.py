"""
modules_bb.py — Modules Black Belt qui manquaient dans l'application
====================================================================
  DEFINE   : render_charte_plus     → objectif SMART, périmètre IN/OUT, business case COPQ
  MEASURE  : render_gage_rr         → vrai Gage R&R (ANOVA) + Kappa attributaire
  ANALYZE  : render_regression      → régression multiple Y = f(X) + Pareto
  IMPROVE  : render_doe             → plan d'expériences 2^k
             render_pilote          → pilote avec preuve statistique et décision Go
  CHANGEMENT : render_change        → ADKAR, plan de communication, RACI, résistances

Toutes les données sont stockées dans le dictionnaire du projet `p`,
elles partent donc dans la sauvegarde JSON existante.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lss_ai as AI
import lss_report as R
import lss_stats as S


def _df(obj, cols):
    d = R.as_df(obj)
    if d.empty:
        return pd.DataFrame([dict.fromkeys(cols, "")], columns=cols)
    for c in cols:
        if c not in d.columns:
            d[c] = ""
    return d[cols]


def _ar(v) -> str:
    return f"{v:,.0f} Ar".replace(",", " ")


# ===========================================================================
# DEFINE — charte complète
# ===========================================================================
def render_charte_plus(p: dict, p_idx: int):
    st.divider()
    st.header("8. Charte du projet — objectif SMART, périmètre et business case")
    ch = p.setdefault("charte", {})
    k = f"_{p_idx}"

    st.subheader("Objectif SMART")
    c1, c2, c3, c4 = st.columns([3, 1.3, 1.3, 1.4])
    ch["indicateur"] = c1.text_input("Indicateur (Y)", ch.get("indicateur", p.get("selected_ctq", "")), key=f"ch_ind{k}")
    ch["valeur_actuelle"] = c2.text_input("Valeur actuelle", ch.get("valeur_actuelle", ""), key=f"ch_va{k}")
    ch["cible"] = c3.text_input("Cible", ch.get("cible", ""), key=f"ch_ci{k}")
    ch["echeance"] = c4.text_input("Échéance", ch.get("echeance", ""), placeholder="ex. 31/03/2027", key=f"ch_ec{k}")
    if ch["indicateur"] and ch["cible"]:
        ch["objectif_smart"] = (f"Faire passer « {ch['indicateur']} » de {ch['valeur_actuelle'] or '?'} à "
                                f"{ch['cible']} d'ici le {ch['echeance'] or '?'}, sur le périmètre défini ci-dessous.")
        st.success("🎯 " + ch["objectif_smart"])
        missing = [n for n, v in (("valeur actuelle", ch["valeur_actuelle"]), ("échéance", ch["echeance"])) if not v]
        if missing:
            st.caption("Pour être SMART, il manque : " + ", ".join(missing))

    st.subheader("Périmètre")
    c1, c2 = st.columns(2)
    ch["in_scope"] = c1.text_area("✅ Dans le périmètre (IN)", ch.get("in_scope", ""), height=110, key=f"ch_in{k}")
    ch["out_scope"] = c2.text_area("⛔ Hors périmètre (OUT)", ch.get("out_scope", ""), height=110, key=f"ch_out{k}")
    c1, c2 = st.columns(2)
    ch["contraintes"] = c1.text_area("Contraintes / hypothèses", ch.get("contraintes", ""), height=80, key=f"ch_ctr{k}")
    ch["risques"] = c2.text_area("Risques du projet", ch.get("risques", ""), height=80, key=f"ch_rsk{k}")

    st.subheader("Business case — coût de la non-qualité (COPQ)")
    st.caption("Chiffrez ce que le problème coûte chaque année. C'est ce montant qui justifie le projet devant le sponsor.")
    cols = ["Catégorie", "Description", "Volume annuel", "Coût unitaire (Ar)"]
    d = st.data_editor(_df(ch.get("copq"), cols), num_rows="dynamic", use_container_width=True, key=f"ch_copq{k}",
                       column_config={
                           "Catégorie": st.column_config.SelectboxColumn(options=[
                               "Défaillance interne (rebuts, reprises)", "Défaillance externe (réclamations, pertes clients)",
                               "Évaluation (contrôles, inspections)", "Prévention", "Attentes / temps perdu"]),
                           "Volume annuel": st.column_config.NumberColumn(min_value=0),
                           "Coût unitaire (Ar)": st.column_config.NumberColumn(min_value=0, format="%d")})
    d["Total (Ar)"] = pd.to_numeric(d["Volume annuel"], errors="coerce").fillna(0) * pd.to_numeric(d["Coût unitaire (Ar)"], errors="coerce").fillna(0)
    ch["copq"] = d.drop(columns="Total (Ar)").to_dict("records")
    ch["copq_total"] = float(d["Total (Ar)"].sum())
    c1, c2 = st.columns(2)
    c1.metric("COPQ annuel estimé", _ar(ch["copq_total"]))
    ch["gain_vise_pct"] = c2.number_input("Part du COPQ que le projet vise à supprimer (%)", 0, 100,
                                          int(ch.get("gain_vise_pct", 50)), key=f"ch_gv{k}")
    st.info(f"💰 Gain annuel visé : **{_ar(ch['copq_total'] * ch['gain_vise_pct'] / 100)}**")


# ===========================================================================
# MEASURE — Gage R&R et Kappa
# ===========================================================================
def render_gage_rr(p: dict, p_idx: int):
    st.divider()
    st.subheader("4 bis. Étude Gage R&R (méthode ANOVA) et accord attributaire (Kappa)")
    k = f"_{p_idx}"
    msa = p.setdefault("msa_etudes", {})
    t1, t2 = st.tabs(["📏 Données continues : Gage R&R", "✅ Données attributaires : Kappa"])

    with t1:
        st.caption("Plan conseillé : 10 pièces (ou dossiers) couvrant toute la plage, 3 opérateurs, 2 à 3 mesures "
                   "chacun, dans un ordre aléatoire et sans que l'opérateur voie ses mesures précédentes.")
        c1, c2, c3, c4 = st.columns(4)
        npie = c1.number_input("Pièces", 2, 30, 10, key=f"grr_np{k}")
        nop = c2.number_input("Opérateurs", 2, 6, 3, key=f"grr_no{k}")
        nrep = c3.number_input("Répétitions", 2, 5, 2, key=f"grr_nr{k}")
        tol = c4.number_input("Tolérance (USL − LSL), facultatif", 0.0, value=float(msa.get("tolerance", 0.0)), key=f"grr_tol{k}")
        msa["tolerance"] = tol
        if st.button("🧩 Générer la grille de saisie", key=f"grr_gen{k}"):
            msa["grr_data"] = [{"Pièce": f"P{i+1}", "Opérateur": f"Op{o+1}", "Répétition": r + 1, "Mesure": None}
                               for r in range(int(nrep)) for o in range(int(nop)) for i in range(int(npie))]
        data = R.as_df(msa.get("grr_data"))
        if data.empty:
            st.info("Générez la grille, saisissez les mesures (ou collez-les depuis Excel), puis calculez.")
        else:
            data = st.data_editor(data, use_container_width=True, num_rows="dynamic", key=f"grr_ed{k}", height=300)
            msa["grr_data"] = data.to_dict("records")
            if st.button("📊 Calculer le Gage R&R", type="primary", key=f"grr_run{k}"):
                msa["grr_result"] = S.gage_rr_anova(data, "Pièce", "Opérateur", "Mesure", tolerance=tol or None)
            res = msa.get("grr_result")
            if res:
                if not res.get("ok"):
                    st.error(res["message"])
                else:
                    m = st.columns(4)
                    m[0].metric("%GRR (étude)", f"{res['%GRR']} %")
                    m[1].metric("Répétabilité (EV)", f"{res['%Etude_Repetabilite (EV)']} %")
                    m[2].metric("Reproductibilité (AV)", f"{res['%Etude_Reproductibilite (AV)']} %")
                    m[3].metric("ndc", res["ndc"])
                    if "%Tolerance_GRR" in res:
                        st.caption(f"%GRR rapporté à la tolérance : {res['%Tolerance_GRR']} %")
                    (st.success if res["verdict"] == "Acceptable" else st.warning if "conditions" in res["verdict"] else st.error)(
                        f"Verdict : {res['verdict']}  (règles AIAG : < 10 % acceptable, 10–30 % sous conditions, > 30 % à améliorer ; ndc ≥ 5)")
                    if res["%Etude_Repetabilite (EV)"] > res["%Etude_Reproductibilite (AV)"]:
                        st.info("La répétabilité domine : l'instrument ou la méthode de mesure varie (entretien, résolution, mode opératoire).")
                    else:
                        st.info("La reproductibilité domine : les opérateurs ne mesurent pas pareil (formation, définition opérationnelle).")
                    p.setdefault("results_closure", {})["gage_rr"] = res

    with t2:
        st.caption("Chaque élément est jugé plusieurs fois (par plusieurs évaluateurs et/ou plusieurs fois par le même).")
        kd = R.as_df(msa.get("kappa_data"))
        if kd.empty:
            kd = pd.DataFrame([{"Élément": f"E{i+1}", "Évaluateur": e, "Résultat": ""} for i in range(10) for e in ("A", "B", "C")])
        kd = st.data_editor(kd, num_rows="dynamic", use_container_width=True, key=f"kap_ed{k}", height=300)
        msa["kappa_data"] = kd.to_dict("records")
        if st.button("📊 Calculer le Kappa", key=f"kap_run{k}"):
            sub = kd[kd["Résultat"].astype(str).str.strip() != ""]
            msa["kappa_result"] = S.fleiss_kappa(sub, "Élément", "Évaluateur", "Résultat")
        kr = msa.get("kappa_result")
        if kr:
            if kr.get("ok"):
                (st.success if kr["kappa"] >= 0.7 else st.error)(
                    f"Kappa de Fleiss = {kr['kappa']} ({kr['verdict']}) — accord observé {kr['accord_observe_%']} %")
                p.setdefault("results_closure", {})["kappa"] = kr
            else:
                st.error(kr["message"])


# ===========================================================================
# ANALYZE — régression multiple et Pareto
# ===========================================================================
def render_regression(p: dict, p_idx: int):
    st.divider()
    st.subheader("7. Quantifier Y = f(X) : régression multiple et Pareto")
    k = f"_{p_idx}"
    an = p.setdefault("dmaic", {}).setdefault("analyze", {})
    df = R.as_df(p.get("dc_saved_df_json"))
    cols = [c for c in df.columns if c not in ("ID observation", "Date de modification")]
    if len(cols) < 2:
        st.info("Il faut au moins 2 variables dans la collecte de données (Measure → Écran 2).")
        return
    t1, t2 = st.tabs(["📈 Régression multiple", "📊 Pareto des défauts"])
    with t1:
        nums = [c for c in cols if S.is_numeric(df[c])]
        if not nums:
            st.info("La régression demande un Y numérique.")
        else:
            y = st.selectbox("Y (numérique)", nums, key=f"reg_y{k}")
            xs = st.multiselect("X (numériques ou catégoriels)", [c for c in cols if c != y], key=f"reg_x{k}")
            if st.button("Calculer le modèle", key=f"reg_run{k}") and xs:
                an["regression"] = S.regression(df, y, xs)
            res = an.get("regression")
            if res:
                if not res.get("ok"):
                    st.error(res["message"])
                else:
                    c = st.columns(3)
                    c[0].metric("R² ajusté", f"{100*res['R2_ajuste']:.0f} %")
                    c[1].metric("p du modèle", R._fmt_p(res["p_modele"]))
                    c[2].metric("Observations", res["n"])
                    st.code(res["equation"], language="text")
                    st.dataframe(pd.DataFrame(res["coefficients"]), use_container_width=True, hide_index=True)
                    st.info(res["conclusion"] + " Un coefficient significatif indique de combien Y varie quand ce X augmente "
                            "d'une unité (ou passe à cette modalité), les autres X restant constants.")
    with t2:
        cats = [c for c in cols if not S.is_numeric(df[c])]
        if not cats:
            st.info("Aucune variable catégorielle (type de défaut, motif…) dans la collecte.")
        else:
            c = st.selectbox("Variable à analyser (catégories)", cats, key=f"par_c{k}")
            counts = df[c].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
            par = S.pareto(counts.index, counts.values)
            fig = go.Figure()
            fig.add_bar(x=par["Catégorie"], y=par["Nombre"], name="Nombre", marker_color="#7C3AED")
            fig.add_scatter(x=par["Catégorie"], y=par["% cumulé"], name="% cumulé", yaxis="y2", mode="lines+markers",
                            line=dict(color="#1F2937"))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix=" %"),
                              height=380, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
            st.plotly_chart(fig, use_container_width=True)
            vital = par.loc[par["Vital few (80 %)"], "Catégorie"].tolist()
            st.success(f"Les catégories prioritaires (≈ 80 % des cas) : {', '.join(map(str, vital))}")
            an["pareto"] = {"variable": c, "table": par.to_dict("records")}


# ===========================================================================
# IMPROVE — plan d'expériences et pilote
# ===========================================================================
def render_doe(p: dict, p_idx: int):
    st.divider()
    st.subheader("7. Plan d'expériences (DOE) factoriel 2^k")
    st.caption("Pour trouver le meilleur réglage de 2 à 4 facteurs à la fois, avec un minimum d'essais. "
               "-1 = niveau bas, +1 = niveau haut. Réalisez les essais dans un ordre aléatoire.")
    k = f"_{p_idx}"
    im = p.setdefault("dmaic", {}).setdefault("improve", {})
    doe = im.setdefault("doe", {})
    c1, c2 = st.columns([3, 1])
    fac_txt = c1.text_input("Facteurs (séparés par des virgules, 2 à 4)", ", ".join(doe.get("facteurs", [])),
                            placeholder="ex. Pré-contrôle, Comité bi-hebdo, Checklist", key=f"doe_f{k}")
    reps = c2.number_input("Répliques", 1, 4, int(doe.get("repliques", 1)), key=f"doe_r{k}")
    factors = [f.strip() for f in fac_txt.split(",") if f.strip()][:4]
    if st.button("🧩 Générer le plan", key=f"doe_gen{k}"):
        if 2 <= len(factors) <= 4:
            doe.update(facteurs=factors, repliques=int(reps), plan=S.doe_design(factors, int(reps)).to_dict("records"), resultat=None)
        else:
            st.warning("Indiquez entre 2 et 4 facteurs.")
    plan = R.as_df(doe.get("plan"))
    if plan.empty:
        return
    st.markdown("**Niveaux des facteurs** (pour mémoire)")
    lv = _df(doe.get("niveaux"), ["Facteur", "Niveau bas (-1)", "Niveau haut (+1)"])
    if lv["Facteur"].astype(str).str.strip().eq("").all():
        lv = pd.DataFrame([{"Facteur": f, "Niveau bas (-1)": "", "Niveau haut (+1)": ""} for f in doe["facteurs"]])
    doe["niveaux"] = st.data_editor(lv, use_container_width=True, key=f"doe_lv{k}").to_dict("records")
    plan = st.data_editor(plan, use_container_width=True, key=f"doe_ed{k}",
                          disabled=[c for c in plan.columns if c != "Réponse (Y)"])
    doe["plan"] = plan.to_dict("records")
    if st.button("📊 Analyser les effets", type="primary", key=f"doe_run{k}"):
        doe["resultat"] = S.doe_analyze(plan, doe["facteurs"])
    res = doe.get("resultat")
    if res:
        if not res.get("ok"):
            st.error(res["message"])
            return
        eff = pd.DataFrame(res["effets"])
        fig = go.Figure(go.Bar(x=eff["|Effet|"], y=eff["Terme"], orientation="h",
                               marker_color=["#EA580C" if s == "Oui" else "#CBD5E1" for s in eff["Significatif"]]))
        fig.add_vline(x=res["seuil"], line_dash="dash", line_color="#DC2626")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), yaxis=dict(autorange="reversed"),
                          title=f"Pareto des effets — {res['methode']}")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(eff, use_container_width=True, hide_index=True)
        st.success(res["conclusion"])
        st.caption("Réglage qui augmente Y (effets principaux) : " +
                   ", ".join(f"{f} {v}" for f, v in res["reglage_max"].items()) + ". Inversez si l'objectif est de réduire Y.")


def render_pilote(p: dict, p_idx: int):
    st.divider()
    st.subheader("8. Pilote des solutions")
    st.caption("Tester à petite échelle avant de généraliser : on prouve l'effet, on détecte les effets de bord.")
    k = f"_{p_idx}"
    im = p.setdefault("dmaic", {}).setdefault("improve", {})
    pil = im.setdefault("pilote", {})
    c1, c2 = st.columns(2)
    pil["solutions"] = c1.text_area("Solution(s) pilotées", pil.get("solutions", ""), height=80, key=f"pil_s{k}")
    pil["perimetre"] = c2.text_area("Périmètre et durée du pilote", pil.get("perimetre", ""), height=80, key=f"pil_p{k}")
    c1, c2 = st.columns(2)
    pil["critere"] = c1.text_input("Critère de succès", pil.get("critere", ""), placeholder="ex. délai moyen < 40 h", key=f"pil_c{k}")
    dirs = ["réduire", "augmenter", "cibler"]
    pil["direction"] = c2.selectbox("Objectif", dirs, index=dirs.index(pil.get("direction", "réduire")), key=f"pil_d{k}")
    st.markdown("**Données du pilote** (collez une colonne avant, une colonne pendant le pilote)")
    d = _df(pil.get("donnees"), ["Avant", "Pilote"])
    d = st.data_editor(d, num_rows="dynamic", use_container_width=True, key=f"pil_ed{k}", height=250)
    pil["donnees"] = d.to_dict("records")
    if st.button("📊 Évaluer le pilote", type="primary", key=f"pil_run{k}"):
        pil["resultat"] = S.before_after(d["Avant"], d["Pilote"], pil["direction"])
    res = pil.get("resultat")
    if res:
        if res.get("ok"):
            (st.success if res["significatif"] else st.warning)(res["conclusion"])
        else:
            st.error(res["message"])
    pil["effets_bord"] = st.text_area("Effets de bord observés / ajustements", pil.get("effets_bord", ""), key=f"pil_e{k}")
    opts = ["", "GO — généraliser", "GO avec ajustements", "NO GO — revoir la solution"]
    pil["decision"] = st.selectbox("Décision", opts, index=opts.index(pil.get("decision", "")), key=f"pil_dec{k}")


# ===========================================================================
# CONDUITE DU CHANGEMENT
# ===========================================================================
ADKAR = ["Awareness (conscience du besoin)", "Desire (envie de participer)", "Knowledge (savoir comment)",
         "Ability (capacité à faire)", "Reinforcement (ancrage)"]


def render_change(p: dict, p_idx: int):
    st.header("🤝 Conduite du changement")
    st.caption("Un projet techniquement juste échoue si les personnes ne changent pas leurs pratiques. "
               "Diagnostiquez, communiquez, répartissez les rôles, traitez les résistances.")
    k = f"_{p_idx}"
    ch = p.setdefault("changement", {})

    st.subheader("1. Diagnostic ADKAR par groupe d'acteurs")
    st.caption("Notez de 1 (absent) à 5 (acquis). Le premier élément < 3 est le point de blocage à traiter en priorité.")
    groups = [r.get("Name") for r in R.as_df(p.get("stakeholders")).to_dict("records") if r.get("Name")]
    cols = ["Groupe"] + [a.split(" (")[0] for a in ADKAR]
    base = R.as_df(ch.get("adkar"))
    if base.empty:
        base = pd.DataFrame([{"Groupe": g, **{c: 3 for c in cols[1:]}} for g in (groups or ["Équipe opérationnelle"])])
    cfg = {c: st.column_config.NumberColumn(min_value=1, max_value=5, step=1) for c in cols[1:]}
    ad = st.data_editor(base[cols] if set(cols) <= set(base.columns) else base, num_rows="dynamic",
                        use_container_width=True, key=f"adk_ed{k}", column_config=cfg)
    blocks = []
    for _, r in ad.iterrows():
        bp = next((c for c in cols[1:] if pd.to_numeric(r.get(c), errors="coerce") < 3), None)
        blocks.append(bp or "Aucun")
    ad["Point de blocage"] = blocks
    ch["adkar"] = ad.to_dict("records")
    actions = {"Awareness": "expliquer le pourquoi (données VOC, COPQ, risques de l'inaction)",
               "Desire": "impliquer, montrer le « qu'est-ce que j'y gagne », relais d'influence",
               "Knowledge": "former, rédiger les standards (SOP), démontrer",
               "Ability": "accompagner sur le terrain, coaching, temps d'appropriation",
               "Reinforcement": "mesurer, reconnaître, intégrer aux rituels et objectifs"}
    for _, r in ad.iterrows():
        if r["Point de blocage"] != "Aucun":
            st.markdown(f"- **{r['Groupe']}** bloqué sur **{r['Point de blocage']}** → {actions[r['Point de blocage']]}")

    st.subheader("2. Plan de communication")
    cc = ["Public", "Message clé", "Canal", "Fréquence / date", "Émetteur", "Statut"]
    ch["communication"] = st.data_editor(_df(ch.get("communication"), cc), num_rows="dynamic", use_container_width=True,
                                         key=f"com_ed{k}", column_config={"Statut": st.column_config.SelectboxColumn(
                                             options=["", "Prévu", "Fait", "Reporté"])}).to_dict("records")

    st.subheader("3. RACI")
    st.caption("R = réalise, A = approuve (un seul par activité), C = consulté, I = informé.")
    rc = ["Activité", "R (Réalise)", "A (Approuve)", "C (Consulté)", "I (Informé)"]
    raci = st.data_editor(_df(ch.get("raci"), rc), num_rows="dynamic", use_container_width=True, key=f"raci_ed{k}")
    ch["raci"] = raci.to_dict("records")
    multi_a = raci[raci["A (Approuve)"].astype(str).str.contains(",|/| et ", regex=True)]
    if not multi_a.empty:
        st.warning("Une activité ne doit avoir qu'un seul « A » : " + ", ".join(multi_a["Activité"].astype(str)))

    st.subheader("4. Registre des résistances")
    rr = ["Acteur / groupe", "Résistance exprimée", "Cause probable", "Action", "Responsable", "Statut"]
    ch["resistances"] = st.data_editor(_df(ch.get("resistances"), rr), num_rows="dynamic", use_container_width=True,
                                       key=f"res_ed_{p_idx}", column_config={"Statut": st.column_config.SelectboxColumn(
                                           options=["", "Ouverte", "En cours", "Levée"])}).to_dict("records")
