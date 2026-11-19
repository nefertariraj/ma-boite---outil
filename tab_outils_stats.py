"""
tab_outils_stats.py — Boîte à outils statistique du Black Belt
==============================================================
Utilisable à n'importe quelle phase, sur les données du projet (T0, Control)
ou sur un fichier importé. Chaque résultat peut être interprété par l'Agent
Statisticien.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats as sps

import lss_agents as G
import lss_ai as AI
import lss_report as R
import lss_stats as S

GREEN, RED, INK, ACC = "#059669", "#DC2626", "#1F2937", "#2563EB"


def _source(p: dict, k: str) -> pd.DataFrame:
    opts = ["Données T0 du projet (Measure)", "Données de contrôle (Control)", "Importer un fichier (CSV / Excel)", "Coller des valeurs"]
    src = st.radio("Source des données", opts, horizontal=True, key=f"ts_src{k}")
    if src == opts[0]:
        return R.as_df(p.get("dc_saved_df_json"))
    if src == opts[1]:
        return R.as_df((p.get("control") or {}).get("ctrl_master_data"))
    if src == opts[2]:
        f = st.file_uploader("Fichier", type=["csv", "xlsx", "xls"], key=f"ts_file{k}")
        if f is None:
            return pd.DataFrame()
        try:
            if f.name.lower().endswith(".csv"):
                raw = f.getvalue().decode("utf-8", errors="ignore")
                sep = ";" if raw.count(";") > raw.count(",") else ","
                return pd.read_csv(pd.io.common.StringIO(raw), sep=sep)
            return pd.read_excel(f)
        except Exception as exc:
            st.error(f"Lecture impossible : {exc}")
            return pd.DataFrame()
    txt = st.text_area("Collez une ou plusieurs colonnes depuis Excel (avec la ligne d'en-tête)", key=f"ts_paste{k}", height=140)
    if not txt.strip():
        return pd.DataFrame()
    try:
        return pd.read_csv(pd.io.common.StringIO(txt), sep="\t" if "\t" in txt else (";" if ";" in txt else ","))
    except Exception:
        return pd.DataFrame({"Valeurs": [l for l in txt.splitlines() if l.strip()]})


def _interpret(label: str, result: dict, p: dict, key: str):
    if st.button("🧠 Faire interpréter par l'Agent Statisticien", key=key):
        cfg = AI.get_config()
        q = (f"Interprète ce résultat ({label}) pour un Black Belt puis pour un comité de direction, vérifie les conditions "
             f"d'application et dis ce qu'il faut faire ensuite : {json.dumps(result, ensure_ascii=False, default=str)[:3000]}")
        with st.spinner("Analyse…"):
            st.session_state[key + "_out"] = G.run_agent("stats", q, p, cfg)
    if st.session_state.get(key + "_out"):
        st.markdown(st.session_state[key + "_out"])


def _limits_fig(y, cl, ucl, lcl, title, flags=None, ytitle=""):
    x = list(range(1, len(y) + 1))
    fig = go.Figure()
    fig.add_scatter(x=x, y=y, mode="lines+markers", name="Valeur", line=dict(color=ACC),
                    marker=dict(color=[RED if f else ACC for f in (flags or [""] * len(y))], size=7))
    for v, nm, dash, col in ((cl, "CL", "solid", INK), (ucl, "UCL", "dash", RED), (lcl, "LCL", "dash", RED)):
        yy = v if isinstance(v, list) else [v] * len(y)
        fig.add_scatter(x=x, y=yy, mode="lines", name=nm, line=dict(color=col, dash=dash, width=1, shape="hv"))
    fig.update_layout(title=title, height=330, margin=dict(l=10, r=10, t=40, b=10), yaxis_title=ytitle,
                      legend=dict(orientation="h"))
    return fig


def render_stats_toolbox(p: dict, p_idx: int):
    st.header("🧮 Boîte à outils statistique")
    st.caption("Analyses à la demande, à toutes les phases. Les points rouges signalent une règle de contrôle violée.")
    k = f"_{p_idx}"
    df = _source(p, k)
    cols = [c for c in df.columns if c not in ("ID observation", "Date de modification")] if not df.empty else []
    nums = [c for c in cols if S.is_numeric(df[c])]
    if not df.empty:
        st.caption(f"{len(df)} lignes · {len(cols)} colonnes · {len(nums)} numériques")

    t = st.tabs(["📊 Descriptif & normalité", "⚖️ Tests d'hypothèse", "🔢 Taille d'échantillon",
                 "📉 Cartes de contrôle", "🎯 Capabilité", "🧪 Profil des données"])

    # ---------------------------------------------------------------- descriptif
    with t[0]:
        if not nums:
            st.info("Aucune colonne numérique dans la source choisie.")
        else:
            c = st.selectbox("Variable", nums, key=f"ts_d_var{k}")
            res = S.describe(df[c])
            if res.get("ok"):
                m = st.columns(5)
                m[0].metric("n", res["n"]); m[1].metric("Moyenne", res["moyenne"]); m[2].metric("Médiane", res["mediane"])
                m[3].metric("Écart-type", res["ecart_type"]); m[4].metric("p Shapiro", res["p_shapiro"])
                st.caption(f"IC 95 % de la moyenne : {res['IC95_moyenne'][0]} → {res['IC95_moyenne'][1]} · "
                           f"Q1–Q3 : {res['Q1']} – {res['Q3']} · min–max : {res['min']} – {res['max']} · "
                           f"asymétrie {res['asymetrie']}, aplatissement {res['aplatissement']}")
                (st.success if res["normal"] else st.warning)(
                    "Distribution compatible avec la loi normale." if res["normal"] else
                    "Distribution non normale : privilégiez les tests non paramétriques (Mann-Whitney, Kruskal-Wallis) "
                    "ou cherchez une cause (mélange de populations, valeurs extrêmes, données bornées).")
                x = S.to_numeric(df[c]).dropna().sort_values().values
                a, b = st.columns(2)
                fig = go.Figure(go.Histogram(x=x, marker_color=ACC, nbinsx=min(30, max(5, int(np.sqrt(len(x)))))))
                fig.update_layout(title="Histogramme", height=300, margin=dict(l=10, r=10, t=40, b=10))
                a.plotly_chart(fig, use_container_width=True)
                th = sps.norm.ppf((np.arange(1, len(x) + 1) - 0.5) / len(x)) * x.std(ddof=1) + x.mean()
                fig = go.Figure()
                fig.add_scatter(x=th, y=x, mode="markers", marker=dict(color=ACC), name="Données")
                fig.add_scatter(x=[th.min(), th.max()], y=[th.min(), th.max()], mode="lines", line=dict(color=RED, dash="dash"), name="Normale")
                fig.update_layout(title="Droite de Henry (Q-Q plot)", height=300, margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
                b.plotly_chart(fig, use_container_width=True)
                _interpret(f"descriptif de {c}", res, p, f"ts_d_ai{k}")

    # ---------------------------------------------------------------- tests
    with t[1]:
        tests = ["Comparer des groupes (X catégoriel → Y)", "Relation entre deux variables (auto)", "Comparer à une cible",
                 "Mesures appariées (avant/après sur les mêmes unités)", "Comparer des variabilités"]
        which = st.selectbox("Question", tests, key=f"ts_t_kind{k}")
        res = None
        if not cols:
            st.info("Choisissez une source de données.")
        elif which in (tests[0], tests[1]):
            a, b = st.columns(2)
            y = a.selectbox("Y (résultat)", cols, key=f"ts_t_y{k}")
            x = b.selectbox("X (facteur)", [c for c in cols if c != y], key=f"ts_t_x{k}")
            if x:
                r = S.test_x_on_y(df, x, y)
                res = r.as_row()
                st.dataframe(pd.DataFrame([res]), use_container_width=True, hide_index=True)
                (st.success if r.significant else st.info)(r.conclusion)
                if not S.is_numeric(df[x]) and S.is_numeric(df[y]):
                    d = df[[x, y]].copy(); d[y] = S.to_numeric(d[y])
                    fig = go.Figure([go.Box(y=g[y], name=str(n), boxmean=True) for n, g in d.dropna().groupby(x)])
                    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, title=f"{y} selon {x}")
                    st.plotly_chart(fig, use_container_width=True)
                elif S.is_numeric(df[x]) and S.is_numeric(df[y]):
                    fig = go.Figure(go.Scatter(x=S.to_numeric(df[x]), y=S.to_numeric(df[y]), mode="markers", marker=dict(color=ACC)))
                    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=x, yaxis_title=y)
                    st.plotly_chart(fig, use_container_width=True)
        elif which == tests[2]:
            if nums:
                a, b, c_ = st.columns(3)
                v = a.selectbox("Variable", nums, key=f"ts_t1_v{k}")
                tgt = b.number_input("Cible", value=0.0, key=f"ts_t1_t{k}")
                alt = c_.selectbox("Hypothèse", ["two-sided", "less", "greater"], key=f"ts_t1_a{k}",
                                   format_func=lambda s: {"two-sided": "différente", "less": "inférieure", "greater": "supérieure"}[s])
                res = S.one_sample(df[v], tgt, alt)
                (st.success if res.get("significatif") else st.info)(res.get("conclusion", res.get("message")))
        elif which == tests[3]:
            if len(nums) >= 2:
                a, b = st.columns(2)
                v1 = a.selectbox("Avant", nums, key=f"ts_tp_a{k}")
                v2 = b.selectbox("Après", [c for c in nums if c != v1], key=f"ts_tp_b{k}")
                res = S.paired(df[v1], df[v2])
                (st.success if res.get("significatif") else st.info)(res.get("conclusion", res.get("message")))
            else:
                st.info("Il faut deux colonnes numériques (avant et après sur les mêmes unités).")
        else:
            a, b = st.columns(2)
            y = a.selectbox("Variable numérique", nums or ["—"], key=f"ts_tv_y{k}")
            g = b.selectbox("Groupes", [c for c in cols if c != y] or ["—"], key=f"ts_tv_g{k}")
            if nums and g in df.columns:
                res = S.variances({str(n): grp[y].tolist() for n, grp in df.groupby(g)})
                (st.success if res.get("significatif") else st.info)(res.get("conclusion", res.get("message")))
                if res.get("ok"):
                    st.json(res["ecarts_types"])
        if res:
            _interpret(which, res, p, f"ts_t_ai{k}")

    # ---------------------------------------------------------------- taille d'échantillon
    with t[2]:
        st.caption("Combien d'observations faut-il pour détecter un écart réel ? À faire AVANT de collecter.")
        kind = st.radio("Type de Y", ["Continu (moyenne)", "Attributaire (proportion)"], horizontal=True, key=f"ts_n_kind{k}")
        a, b, c_ = st.columns(3)
        alpha = a.selectbox("Risque α", [0.01, 0.05, 0.10], index=1, key=f"ts_n_a{k}")
        power = b.selectbox("Puissance (1 − β)", [0.8, 0.9, 0.95], key=f"ts_n_p{k}")
        two = c_.toggle("Comparer 2 groupes (sinon : 1 groupe vs cible)", True, key=f"ts_n_2{k}")
        if kind.startswith("Continu"):
            a, b = st.columns(2)
            sd0 = float(S.to_numeric(df[nums[0]]).std()) if nums else 1.0
            sigma = a.number_input("Écart-type estimé (σ)", 0.0001, value=round(sd0 or 1.0, 3), key=f"ts_n_s{k}")
            delta = b.number_input("Écart minimal à détecter (Δ)", 0.0001, value=round((sd0 or 1.0) / 2, 3), key=f"ts_n_d{k}")
            n = S.sample_size_means(delta, sigma, alpha, power, two_groups=two)
            st.success(f"**{n} observations {'par groupe' if two else ''}** pour détecter un écart de {delta} "
                       f"(soit {delta/sigma:.2f} σ) avec α = {alpha} et une puissance de {int(power*100)} %.")
            ns = list(range(5, max(60, 2 * n) + 1, 5))
            fig = go.Figure(go.Scatter(x=ns, y=[S.power_means(v, delta, sigma, alpha, two) for v in ns], mode="lines", line=dict(color=ACC)))
            fig.add_hline(y=power, line_dash="dash", line_color=RED)
            fig.update_layout(title="Courbe de puissance", height=280, margin=dict(l=10, r=10, t=40, b=10),
                              xaxis_title="n par groupe", yaxis_title="Puissance", yaxis_range=[0, 1])
            st.plotly_chart(fig, use_container_width=True)
        else:
            a, b = st.columns(2)
            p1 = a.number_input("Proportion actuelle (ex. 0,18 = 18 % de défauts)", 0.001, 0.999, 0.18, key=f"ts_n_p1{k}")
            p2 = b.number_input("Proportion visée", 0.001, 0.999, 0.08, key=f"ts_n_p2{k}")
            n = S.sample_size_proportions(p1, p2, alpha, power)
            st.success(f"**{n} unités par groupe** pour prouver le passage de {p1:.1%} à {p2:.1%}.")

    # ---------------------------------------------------------------- cartes
    with t[3]:
        kind = st.selectbox("Type de carte", ["I-MR (valeurs individuelles)", "X̄-R (sous-groupes)",
                                              "p (proportion de défectueux)", "u (défauts par unité)"], key=f"ts_c_kind{k}")
        st.caption("Guide : continu & 1 mesure à la fois → I-MR ; continu par lots → X̄-R ; "
                   "% d'unités non conformes → p ; nombre de défauts par unité → u.")
        if kind.startswith("I-MR") and nums:
            v = st.selectbox("Variable", nums, key=f"ts_c_v{k}")
            c = S.imr_chart(df[v])
            if c.get("ok"):
                st.plotly_chart(_limits_fig(c["values"], c["CL"], c["UCL"], c["LCL"], f"Carte I — {v}", c["flags"]), use_container_width=True)
                st.plotly_chart(_limits_fig(c["MR"][1:], c["MRbar"], c["MR_UCL"], 0, "Carte MR (étendues mobiles)"), use_container_width=True)
                _chart_verdict(c["flags"])
                _interpret("carte I-MR", {k_: c[k_] for k_ in ("CL", "UCL", "LCL", "n_out", "stable")} | {"regles": [f for f in c["flags"] if f]}, p, f"ts_c_ai{k}")
        elif kind.startswith("X̄") and nums:
            a, b = st.columns(2)
            v = a.selectbox("Variable", nums, key=f"ts_c_xv{k}")
            n = b.number_input("Taille des sous-groupes", 2, 10, 5, key=f"ts_c_xn{k}")
            c = S.xbar_r_chart(df[v], int(n))
            if c.get("ok"):
                st.plotly_chart(_limits_fig(c["means"], c["CL"], c["UCL"], c["LCL"], f"Carte X̄ — {v}", c["flags"]), use_container_width=True)
                st.plotly_chart(_limits_fig(c["ranges"], c["R_CL"], c["R_UCL"], c["R_LCL"], "Carte R"), use_container_width=True)
                _chart_verdict(c["flags"])
            else:
                st.warning(c["message"])
        elif kind[0] in "pu" and nums:
            a, b = st.columns(2)
            d_ = a.selectbox("Nombre de défectueux / défauts", nums, key=f"ts_c_d{k}")
            n_ = b.selectbox("Taille d'échantillon / nombre d'unités", nums, key=f"ts_c_n{k}")
            c = S.p_chart(df[d_], df[n_]) if kind[0] == "p" else S.u_chart(df[d_], df[n_])
            if c.get("ok"):
                y = c["p"] if kind[0] == "p" else c["u"]
                st.plotly_chart(_limits_fig(y, c["CL"], c["UCL"], c["LCL"], f"Carte {kind[0]}", c["flags"]), use_container_width=True)
                _chart_verdict(c["flags"])
            else:
                st.warning(c["message"])
        else:
            st.info("Aucune colonne numérique disponible.")

    # ---------------------------------------------------------------- capabilité
    with t[4]:
        if nums:
            a, b, c_ = st.columns(3)
            v = a.selectbox("Variable", nums, key=f"ts_k_v{k}")
            lsl = b.text_input("LSL (limite basse, vide si aucune)", key=f"ts_k_l{k}")
            usl = c_.text_input("USL (limite haute, vide si aucune)", key=f"ts_k_u{k}")
            f = lambda s: float(s.replace(",", ".")) if s.strip() else None
            try:
                L, U = f(lsl), f(usl)
            except ValueError:
                L = U = None
                st.error("Limites non numériques.")
            if L is not None or U is not None:
                cap = S.continuous_capability(df[v], L, U)
                m = st.columns(6)
                for i, key_ in enumerate(["Cp", "Cpk", "Pp", "Ppk", "ppm_attendus", "sigma_niveau"]):
                    m[i].metric(key_.replace("_", " "), "—" if cap.get(key_) is None else cap[key_])
                cpk = cap.get("Cpk")
                if cpk is not None:
                    (st.success if cpk >= 1.33 else st.warning if cpk >= 1 else st.error)(
                        "Processus capable (Cpk ≥ 1,33)." if cpk >= 1.33 else
                        "Processus juste capable (1 ≤ Cpk < 1,33)." if cpk >= 1 else "Processus non capable (Cpk < 1).")
                x = S.to_numeric(df[v]).dropna()
                fig = go.Figure(go.Histogram(x=x, marker_color=ACC, histnorm="probability density", name="Données"))
                xs = np.linspace(x.min() - x.std(), x.max() + x.std(), 200)
                fig.add_scatter(x=xs, y=sps.norm.pdf(xs, x.mean(), x.std()), mode="lines", line=dict(color=INK), name="Normale")
                for lim, nm in ((L, "LSL"), (U, "USL")):
                    if lim is not None:
                        fig.add_vline(x=lim, line_color=RED, line_dash="dash", annotation_text=nm)
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                imr = S.imr_chart(x)
                if imr.get("ok") and not imr["stable"]:
                    st.warning("⚠️ Le processus n'est pas stable : ces indices ne sont pas prédictifs.")
                _interpret(f"capabilité de {v}", cap, p, f"ts_k_ai{k}")
            else:
                st.info("Saisissez au moins une limite de spécification.")

    # ---------------------------------------------------------------- profil
    with t[5]:
        prof = G.data_profile(p)
        if prof.empty:
            st.info("Pas encore de données T0 dans le projet.")
        else:
            st.dataframe(prof, use_container_width=True, hide_index=True)


def _chart_verdict(flags):
    n = sum(1 for f in flags if f)
    if n:
        rules = sorted({r for f in flags for r in f.split(",") if r})
        st.error(f"Processus hors contrôle statistique : {n} point(s) — règles {', '.join(rules)} "
                 "(R1 : point au-delà de 3σ · R2 : 9 points du même côté · R3 : 6 points en tendance · R5 : 2 sur 3 au-delà de 2σ). "
                 "Cherchez les causes spéciales avant tout calcul de capabilité.")
    else:
        st.success("Processus sous contrôle statistique : seule la variation de causes communes est présente.")
