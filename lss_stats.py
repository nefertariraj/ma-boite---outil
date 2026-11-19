"""
lss_stats.py — Moteur statistique Lean Six Sigma (niveau Black Belt)
=====================================================================
Remplace les calculs dispersés dans app.py par des fonctions uniques, testées
et réutilisables (écran, rapport PowerPoint, IA).

Dépendances : numpy, pandas, scipy (déjà dans votre requirements).

Corrige notamment :
- Pearson calculé sur des séries non appariées (x.dropna() / y.dropna() séparés)
- ANOVA sur un Y non converti en numérique
- Niveau sigma "6.0" affiché dès qu'il y a 0 défaut, même sur 15 observations
- Absence de vrai Gage R&R (%GRR, ndc) et de Kappa attributaire
- Absence de preuve statistique Avant / Après en phase Control
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05

# Libellés considérés comme "défaut" pour les variables attributaires
DEFECT_LABELS = {"KO", "NON OK", "NOK", "NON", "ERREUR", "RETOUCHE", "NON-CONFORME",
                 "NON CONFORME", "DEFAUT", "DÉFAUT", "REJET", "1"}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def to_numeric(series: pd.Series) -> pd.Series:
    """Conversion tolérante (virgule décimale, espaces) vers float."""
    if series is None:
        return pd.Series(dtype=float)
    s = series.astype(str).str.replace(" ", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def is_numeric(series: pd.Series, threshold: float = 0.8) -> bool:
    """Une colonne est numérique si >= 80 % des valeurs non vides se convertissent."""
    non_empty = series.dropna()
    non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
    if non_empty.empty:
        return False
    return to_numeric(non_empty).notna().mean() >= threshold


def is_defect(value) -> bool:
    return str(value).strip().upper() in DEFECT_LABELS


# ---------------------------------------------------------------------------
# 1. Tests "le X agit-il sur le Y ?" (phase Analyze)
# ---------------------------------------------------------------------------
@dataclass
class XYTestResult:
    x: str
    test: str
    n: int
    statistic: float | None
    p_value: float | None
    effect: str          # taille d'effet lisible (r, eta², V de Cramér)
    effect_value: float | None
    significant: bool
    conclusion: str

    def as_row(self) -> dict:
        return {
            "Variable X": self.x,
            "Test utilisé": self.test,
            "N apparié": self.n,
            "P-value": None if self.p_value is None else round(self.p_value, 4),
            "Taille d'effet": self.effect,
            "Le X agit-il sur Y ?": self.conclusion,
            "Significatif (α=5%)": "Oui" if self.significant else "Non",
        }


def _effect_label_r(r: float) -> str:
    a = abs(r)
    return "Fort" if a >= 0.7 else "Modéré" if a >= 0.4 else "Faible" if a >= 0.2 else "Négligeable"


def test_x_on_y(df: pd.DataFrame, x: str, y: str, alpha: float = ALPHA) -> XYTestResult:
    """Choisit automatiquement le bon test selon la nature de X et de Y,
    et travaille TOUJOURS sur des paires (x, y) complètes."""
    sub = df[[x, y]].copy()
    sub = sub[(sub[x].astype(str).str.strip() != "") & (sub[y].astype(str).str.strip() != "")].dropna()
    x_num, y_num = is_numeric(sub[x]), is_numeric(sub[y])

    try:
        # Continu / Continu -> Pearson (ou Spearman si non normal)
        if x_num and y_num:
            xs, ys = to_numeric(sub[x]), to_numeric(sub[y])
            ok = xs.notna() & ys.notna()
            xs, ys = xs[ok], ys[ok]
            n = len(xs)
            if n < 5 or xs.nunique() < 2 or ys.nunique() < 2:
                return XYTestResult(x, "Corrélation", n, None, None, "—", None, False, "Données insuffisantes (n<5)")
            normal = _is_normal(xs) and _is_normal(ys)
            if normal:
                r, p = stats.pearsonr(xs, ys)
                test = "Corrélation de Pearson"
            else:
                r, p = stats.spearmanr(xs, ys)
                test = "Corrélation de Spearman (non normal)"
            sig = bool(p < alpha)
            sens = "positive" if r > 0 else "négative"
            force = {"Fort": "forte", "Modéré": "modérée", "Faible": "faible", "Négligeable": "négligeable"}[_effect_label_r(r)]
            concl = (f"Oui — corrélation {sens} {force} (r={r:.2f})" if sig
                     else "Non démontré au seuil de 5 %")
            return XYTestResult(x, test, n, float(r), float(p), f"r = {r:.2f} ({_effect_label_r(r)})", float(r), sig, concl)

        # Catégoriel / Continu -> ANOVA (ou Kruskal-Wallis)
        if (not x_num) and y_num:
            sub = sub.assign(_y=to_numeric(sub[y])).dropna(subset=["_y"])
            groups = [g["_y"].values for _, g in sub.groupby(x) if len(g) >= 2]
            n = int(sum(len(g) for g in groups))
            if len(groups) < 2:
                return XYTestResult(x, "ANOVA", n, None, None, "—", None, False, "Il faut ≥ 2 modalités avec ≥ 2 observations")
            normal = all(_is_normal(pd.Series(g)) for g in groups if len(g) >= 3)
            if normal:
                stat, p = stats.f_oneway(*groups)
                test = "ANOVA à 1 facteur"
            else:
                stat, p = stats.kruskal(*groups)
                test = "Kruskal-Wallis (non normal)"
            grand = np.concatenate(groups).mean()
            ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
            ss_total = sum(((g - grand) ** 2).sum() for g in groups)
            eta2 = ss_between / ss_total if ss_total > 0 else 0.0
            sig = bool(p < alpha)
            concl = (f"Oui — les moyennes diffèrent selon {x} (η²={eta2:.2f})" if sig
                     else "Non démontré au seuil de 5 %")
            return XYTestResult(x, test, n, float(stat), float(p), f"η² = {eta2:.2f}", float(eta2), sig, concl)

        # Continu / Catégoriel -> ANOVA inversée (on teste si X diffère selon Y)
        if x_num and not y_num:
            res = test_x_on_y(df, y, x, alpha)
            res.x = x
            return res

        # Catégoriel / Catégoriel -> Khi-deux (ou Fisher 2x2)
        table = pd.crosstab(sub[x], sub[y])
        n = int(table.values.sum())
        if table.shape[0] < 2 or table.shape[1] < 2:
            return XYTestResult(x, "Khi-deux", n, None, None, "—", None, False, "Il faut ≥ 2 modalités de chaque côté")
        chi2, p, dof, expected = stats.chi2_contingency(table)
        test = "Khi-deux d'indépendance"
        if table.shape == (2, 2) and (expected < 5).any():
            _, p = stats.fisher_exact(table.values)
            test = "Test exact de Fisher (effectifs faibles)"
        v = math.sqrt(chi2 / (n * (min(table.shape) - 1))) if n > 0 else 0.0
        sig = bool(p < alpha)
        concl = f"Oui — lien statistique (V de Cramér={v:.2f})" if sig else "Non démontré au seuil de 5 %"
        return XYTestResult(x, test, n, float(chi2), float(p), f"V = {v:.2f}", float(v), sig, concl)

    except Exception as exc:  # jamais de crash à l'écran
        return XYTestResult(x, "Erreur", 0, None, None, "—", None, False, f"Erreur de calcul : {exc}")


def _is_normal(s: pd.Series, alpha: float = ALPHA) -> bool:
    s = pd.Series(s).dropna()
    if len(s) < 3 or s.nunique() < 3:
        return False
    if len(s) > 5000:
        s = s.sample(5000, random_state=0)
    return stats.shapiro(s).pvalue >= alpha


def screen_xs(df: pd.DataFrame, y: str, xs: Iterable[str]) -> pd.DataFrame:
    """Tableau de criblage des X, trié par p-value."""
    rows = [test_x_on_y(df, x, y).as_row() for x in xs if x != y and x in df.columns]
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("P-value", na_position="last").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# 2. Capabilité : DPMO, niveau sigma, Cp / Cpk / Pp / Ppk
# ---------------------------------------------------------------------------
def sigma_from_dpmo(dpmo: float, shift: float = 1.5) -> float:
    """Niveau sigma court terme (convention 1,5σ)."""
    p = min(max(dpmo / 1e6, 1e-9), 1 - 1e-9)
    return round(float(stats.norm.ppf(1 - p) + shift), 2)


def attribute_capability(defects: int, units: int, opportunities: int = 1) -> dict:
    """DPMO + sigma. Si 0 défaut, utilise la règle de 3 (borne sup. 95 %) au lieu
    d'afficher 6σ : avec 20 unités sans défaut, on ne peut PAS prétendre être à 6σ."""
    units = max(int(units), 1)
    tot = units * max(int(opportunities), 1)
    dpmo = defects / tot * 1e6
    if defects == 0:
        dpmo_upper = 3 / tot * 1e6
        sigma = sigma_from_dpmo(dpmo_upper)
        note = f"0 défaut observé : sigma prudent ≥ {sigma} (règle de 3, n={tot})"
    else:
        sigma = sigma_from_dpmo(dpmo)
        note = ""
    return {"defauts": int(defects), "unites": units, "opportunites": int(opportunities),
            "dpmo": round(dpmo, 0), "sigma": sigma, "rendement_%": round(100 - dpmo / 1e4, 2), "note": note}


def continuous_capability(values: Iterable[float], lsl: float | None = None, usl: float | None = None) -> dict:
    """Cp, Cpk (σ intra via MR̄/d2) et Pp, Ppk (σ global) + PPM hors tolérance attendus."""
    x = to_numeric(pd.Series(list(values))).dropna()
    out = {"n": int(len(x)), "moyenne": None, "sigma_intra": None, "sigma_global": None,
           "Cp": None, "Cpk": None, "Pp": None, "Ppk": None, "ppm_attendus": None, "sigma_niveau": None}
    if len(x) < 2:
        return out
    mean = x.mean()
    mr = x.diff().abs().dropna()
    s_within = mr.mean() / 1.128 if mr.mean() > 0 else x.std(ddof=1)
    s_overall = x.std(ddof=1)
    out.update(moyenne=round(float(mean), 4), sigma_intra=round(float(s_within), 4), sigma_global=round(float(s_overall), 4))

    def _idx(s):
        if not s or s <= 0:
            return None, None
        cpu = (usl - mean) / (3 * s) if usl is not None else None
        cpl = (mean - lsl) / (3 * s) if lsl is not None else None
        cp = (usl - lsl) / (6 * s) if (usl is not None and lsl is not None) else None
        k = min(v for v in (cpu, cpl) if v is not None) if (cpu is not None or cpl is not None) else None
        return cp, k

    cp, cpk = _idx(s_within)
    pp, ppk = _idx(s_overall)
    rnd = lambda v: None if v is None else round(float(v), 2)
    out.update(Cp=rnd(cp), Cpk=rnd(cpk), Pp=rnd(pp), Ppk=rnd(ppk))
    if s_overall > 0 and (lsl is not None or usl is not None):
        p_out = 0.0
        if usl is not None:
            p_out += 1 - stats.norm.cdf((usl - mean) / s_overall)
        if lsl is not None:
            p_out += stats.norm.cdf((lsl - mean) / s_overall)
        out["ppm_attendus"] = round(float(p_out) * 1e6, 0)
        out["sigma_niveau"] = sigma_from_dpmo(p_out * 1e6)
    return out


def count_defects(values: Iterable, spec: dict) -> tuple[int, int]:
    """Compte les défauts selon la spécification saisie en MSA (même format que l'app :
    type_specification / valeur_exacte / valeur_seuil / borne_inf / borne_sup)."""
    vals = [v for v in values if not (v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "")]
    t = (spec or {}).get("type_specification", "")
    defects = 0
    for v in vals:
        if t.startswith("Attribut") or not _is_float(v):
            defects += is_defect(v)
            continue
        f = float(str(v).replace(",", "."))
        if t == "Supérieur ou égal à (≥)":
            defects += f < float(spec.get("valeur_seuil", 0))
        elif t == "Inférieur ou égal à (≤)":
            defects += f > float(spec.get("valeur_seuil", 0))
        elif t == "Intervalle (Entre min et max)":
            defects += not (float(spec.get("borne_inf", 0)) <= f <= float(spec.get("borne_sup", 0)))
        elif t == "Valeur exacte":
            defects += not math.isclose(f, float(spec.get("valeur_exacte", 0)), rel_tol=1e-5, abs_tol=1e-5)
    return int(defects), len(vals)


def spec_limits(spec: dict) -> tuple[float | None, float | None]:
    t = (spec or {}).get("type_specification", "")
    if t == "Supérieur ou égal à (≥)":
        return float(spec.get("valeur_seuil", 0)), None
    if t == "Inférieur ou égal à (≤)":
        return None, float(spec.get("valeur_seuil", 0))
    if t == "Intervalle (Entre min et max)":
        return float(spec.get("borne_inf", 0)), float(spec.get("borne_sup", 0))
    return None, None


def _is_float(v) -> bool:
    try:
        float(str(v).replace(",", "."))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# 3. Cartes de contrôle I-MR + règles de Nelson
# ---------------------------------------------------------------------------
def imr_chart(values: Iterable[float], frozen_limits: dict | None = None) -> dict:
    """Carte I-MR complète. `frozen_limits` permet de garder les limites T0 pour
    juger les vagues T1, T2… (pratique recommandée : on ne recalcule les limites
    qu'après avoir PROUVÉ le changement)."""
    x = to_numeric(pd.Series(list(values))).dropna().reset_index(drop=True)
    if len(x) < 2:
        return {"ok": False, "message": "Minimum 2 points"}
    mr = x.diff().abs()
    mr_bar = mr.mean()
    if frozen_limits:
        cl, mr_bar = frozen_limits["CL"], frozen_limits["MRbar"]
    else:
        cl = x.mean()
    sigma = mr_bar / 1.128 if mr_bar > 0 else 0.0
    ucl, lcl = cl + 3 * sigma, cl - 3 * sigma
    flags = nelson_rules(x, cl, sigma)
    return {
        "ok": True, "values": x.tolist(), "MR": mr.tolist(), "CL": float(cl), "UCL": float(ucl), "LCL": float(lcl),
        "MRbar": float(mr_bar), "MR_UCL": float(3.267 * mr_bar), "sigma": float(sigma),
        "flags": flags, "n_out": int(sum(1 for f in flags if f)), "stable": not any(flags),
    }


def nelson_rules(x: pd.Series, cl: float, sigma: float) -> list[str]:
    """Retourne, pour chaque point, la liste des règles violées ('' si aucune).
    R1 : 1 point au-delà de 3σ   R2 : 9 points du même côté
    R3 : 6 points croissants/décroissants   R5 : 2 sur 3 au-delà de 2σ (même côté)"""
    n = len(x)
    flags = [set() for _ in range(n)]
    if sigma <= 0:
        return [""] * n
    z = (x - cl) / sigma
    for i in range(n):
        if abs(z[i]) > 3:
            flags[i].add("R1")
        if i >= 8:
            w = z[i - 8:i + 1]
            if (w > 0).all() or (w < 0).all():
                for j in range(i - 8, i + 1):
                    flags[j].add("R2")
        if i >= 5:
            d = np.diff(x[i - 5:i + 1].values)
            if (d > 0).all() or (d < 0).all():
                for j in range(i - 5, i + 1):
                    flags[j].add("R3")
        if i >= 2:
            w = z[i - 2:i + 1]
            if (w > 2).sum() >= 2 or (w < -2).sum() >= 2:
                for j in range(i - 2, i + 1):
                    if abs(z[j]) > 2:
                        flags[j].add("R5")
    return [",".join(sorted(f)) for f in flags]


# ---------------------------------------------------------------------------
# 4. MSA : Gage R&R croisé (méthode ANOVA, AIAG) et Kappa attributaire
# ---------------------------------------------------------------------------
def gage_rr_anova(df: pd.DataFrame, part: str = "Pièce", operator: str = "Opérateur",
                  value: str = "Mesure", tolerance: float | None = None) -> dict:
    """Étude Gage R&R croisée. Format attendu (long) : une ligne par mesure
    avec colonnes Pièce / Opérateur / Mesure. Plan conseillé : 10 pièces × 3
    opérateurs × 2 à 3 répétitions."""
    d = df[[part, operator, value]].copy()
    d[value] = to_numeric(d[value])
    d = d.dropna()
    p, o = d[part].nunique(), d[operator].nunique()
    counts = d.groupby([part, operator]).size()
    if p < 2 or o < 2 or counts.min() < 2:
        return {"ok": False, "message": "Plan incomplet : ≥2 pièces, ≥2 opérateurs et ≥2 répétitions par couple requis."}
    r = int(counts.min())
    d = d.groupby([part, operator], group_keys=False).head(r)  # plan équilibré
    grand = d[value].mean()
    ss_total = ((d[value] - grand) ** 2).sum()
    ss_p = o * r * ((d.groupby(part)[value].mean() - grand) ** 2).sum()
    ss_o = p * r * ((d.groupby(operator)[value].mean() - grand) ** 2).sum()
    cell = d.groupby([part, operator])[value].mean()
    ss_po = r * ((cell - cell.index.get_level_values(0).map(d.groupby(part)[value].mean())
                  - cell.index.get_level_values(1).map(d.groupby(operator)[value].mean()) + grand) ** 2).sum()
    ss_e = ss_total - ss_p - ss_o - ss_po
    df_p, df_o, df_po, df_e = p - 1, o - 1, (p - 1) * (o - 1), p * o * (r - 1)
    ms_p, ms_o, ms_po, ms_e = ss_p / df_p, ss_o / df_o, ss_po / df_po, ss_e / df_e
    p_inter = 1 - stats.f.cdf(ms_po / ms_e, df_po, df_e) if ms_e > 0 else 1.0

    if p_inter > 0.25:  # interaction non significative -> modèle sans interaction (convention Minitab)
        ms_err = (ss_po + ss_e) / (df_po + df_e)
        v_rep, v_int = ms_err, 0.0
        v_op = max(0.0, (ms_o - ms_err) / (p * r))
        v_part = max(0.0, (ms_p - ms_err) / (o * r))
    else:
        v_rep = ms_e
        v_int = max(0.0, (ms_po - ms_e) / r)
        v_op = max(0.0, (ms_o - ms_po) / (p * r))
        v_part = max(0.0, (ms_p - ms_po) / (o * r))
    v_repro = v_op + v_int
    v_grr = v_rep + v_repro
    v_tot = v_grr + v_part
    sd = lambda v: math.sqrt(v)
    pct = lambda v: round(100 * sd(v) / sd(v_tot), 1) if v_tot > 0 else 0.0
    grr_pct = pct(v_grr)
    ndc = int(1.41 * sd(v_part) / sd(v_grr)) if v_grr > 0 else 99
    verdict = ("Acceptable" if grr_pct < 10 and ndc >= 5 else
               "Acceptable sous conditions" if grr_pct <= 30 else "Non acceptable — améliorer le système de mesure")
    res = {
        "ok": True, "pieces": p, "operateurs": o, "repetitions": r,
        "p_interaction": round(float(p_inter), 4),
        "%Etude_Repetabilite (EV)": pct(v_rep), "%Etude_Reproductibilite (AV)": pct(v_repro),
        "%GRR": grr_pct, "%Pieces (PV)": pct(v_part), "ndc": ndc, "verdict": verdict,
    }
    if tolerance and tolerance > 0:
        res["%Tolerance_GRR"] = round(100 * 6 * sd(v_grr) / tolerance, 1)
    return res


def fleiss_kappa(df: pd.DataFrame, item: str, appraiser: str, rating: str) -> dict:
    """Accord inter-évaluateurs pour données attributaires (OK/KO…)."""
    table = pd.crosstab(df[item], df[rating])
    n_raters = table.sum(axis=1)
    if table.empty or n_raters.nunique() != 1 or n_raters.iloc[0] < 2:
        return {"ok": False, "message": "Chaque élément doit être évalué par le même nombre (≥2) d'évaluations."}
    n = n_raters.iloc[0]
    N = len(table)
    p_j = table.sum(axis=0) / (N * n)
    P_i = ((table ** 2).sum(axis=1) - n) / (n * (n - 1))
    P_bar, P_e = P_i.mean(), (p_j ** 2).sum()
    kappa = (P_bar - P_e) / (1 - P_e) if P_e < 1 else 1.0
    verdict = "Excellent" if kappa >= 0.9 else "Acceptable" if kappa >= 0.7 else "Insuffisant"
    return {"ok": True, "kappa": round(float(kappa), 3), "accord_observe_%": round(float(100 * P_bar), 1),
            "elements": N, "evaluations_par_element": int(n), "verdict": verdict}


# ---------------------------------------------------------------------------
# 5. Preuve Avant / Après (phase Control) — LE cœur de la soutenance
# ---------------------------------------------------------------------------
def before_after(before: Iterable, after: Iterable, direction: str = "réduire",
                 alpha: float = ALPHA) -> dict:
    """Compare T0 et T1. direction = 'réduire' | 'augmenter' | 'cibler'.
    Continu : Welch t-test ou Mann-Whitney selon la normalité + Levene (variance).
    Attributaire : test de 2 proportions (ou Fisher si effectifs faibles)."""
    b = pd.Series(list(before)).dropna()
    a = pd.Series(list(after)).dropna()
    b = b[b.astype(str).str.strip() != ""]
    a = a[a.astype(str).str.strip() != ""]
    if len(b) < 2 or len(a) < 2:
        return {"ok": False, "message": "Il faut au moins 2 valeurs avant et après."}

    if is_numeric(b) and is_numeric(a):
        b, a = to_numeric(b).dropna(), to_numeric(a).dropna()
        alt = {"réduire": "greater", "augmenter": "less"}.get(direction, "two-sided")
        normal = _is_normal(b) and _is_normal(a)
        if normal:
            stat, p = stats.ttest_ind(b, a, equal_var=False, alternative=alt)
            test = "t de Welch"
        else:
            stat, p = stats.mannwhitneyu(b, a, alternative=alt)
            test = "Mann-Whitney"
        lev_p = stats.levene(b, a).pvalue
        delta = a.mean() - b.mean()
        delta_pct = 100 * delta / b.mean() if b.mean() != 0 else None
        sig = bool(p < alpha)
        concl = (f"Amélioration statistiquement prouvée ({test}, p={p:.4f})." if sig else
                 f"Amélioration NON prouvée statistiquement ({test}, p={p:.4f}) — prolonger la collecte ou revoir les solutions.")
        if lev_p < alpha:
            concl += f" La variabilité a aussi changé (Levene p={lev_p:.4f}; σ {b.std():.2f} → {a.std():.2f})."
        return {"ok": True, "type": "continu", "test": test, "p_value": round(float(p), 4),
                "significatif": sig, "n_avant": len(b), "n_apres": len(a),
                "moyenne_avant": round(float(b.mean()), 3), "moyenne_apres": round(float(a.mean()), 3),
                "mediane_avant": round(float(b.median()), 3), "mediane_apres": round(float(a.median()), 3),
                "sigma_avant": round(float(b.std()), 3), "sigma_apres": round(float(a.std()), 3),
                "delta": round(float(delta), 3), "delta_%": None if delta_pct is None else round(float(delta_pct), 1),
                "p_levene": round(float(lev_p), 4), "conclusion": concl}

    # Attributaire : proportion de défauts
    db, da = int(b.map(is_defect).sum()), int(a.map(is_defect).sum())
    nb, na = len(b), len(a)
    pb, pa = db / nb, da / na
    table = np.array([[db, nb - db], [da, na - da]])
    if (table < 5).any():
        alt = {"réduire": "greater", "augmenter": "less"}.get(direction, "two-sided")
        _, p = stats.fisher_exact(table, alternative=alt)
        test = "Test exact de Fisher"
    else:
        pool = (db + da) / (nb + na)
        se = math.sqrt(pool * (1 - pool) * (1 / nb + 1 / na)) or 1e-12
        z = (pb - pa) / se
        p = 1 - stats.norm.cdf(z) if direction == "réduire" else stats.norm.cdf(z) if direction == "augmenter" else 2 * (1 - stats.norm.cdf(abs(z)))
        test = "Test de 2 proportions (z)"
    sig = bool(p < alpha)
    concl = (f"Baisse du taux de défauts prouvée ({100*pb:.1f}% → {100*pa:.1f}%, {test}, p={p:.4f})." if sig
             else f"Écart non prouvé ({100*pb:.1f}% → {100*pa:.1f}%, p={p:.4f}).")
    return {"ok": True, "type": "attributaire", "test": test, "p_value": round(float(p), 4), "significatif": sig,
            "n_avant": nb, "n_apres": na, "taux_defaut_avant_%": round(100 * pb, 2),
            "taux_defaut_apres_%": round(100 * pa, 2), "conclusion": concl}


# ---------------------------------------------------------------------------
# 6. Pareto
# ---------------------------------------------------------------------------
def pareto(labels: Iterable[str], counts: Iterable[float]) -> pd.DataFrame:
    d = pd.DataFrame({"Catégorie": list(labels), "Nombre": list(counts)})
    d["Nombre"] = pd.to_numeric(d["Nombre"], errors="coerce").fillna(0)
    d = d.sort_values("Nombre", ascending=False).reset_index(drop=True)
    tot = d["Nombre"].sum() or 1
    d["%"] = (100 * d["Nombre"] / tot).round(1)
    d["% cumulé"] = d["%"].cumsum().round(1)
    d["Vital few (80 %)"] = d["% cumulé"].shift(fill_value=0) < 80
    return d


def to_dict(obj) -> dict:
    return asdict(obj) if hasattr(obj, "__dataclass_fields__") else dict(obj)


# ---------------------------------------------------------------------------
# 7. Régression multiple (MCO) — quantifier Y = f(X1, X2, …)
# ---------------------------------------------------------------------------
def regression(df: pd.DataFrame, y: str, xs: list[str]) -> dict:
    """Régression linéaire multiple. Les X catégoriels sont codés en indicatrices
    (modalité de référence = la première). Retourne coefficients, p-values, R²."""
    d = df[[y] + list(xs)].copy()
    d = d[d.astype(str).apply(lambda r: all(v.strip() not in ("", "nan", "None") for v in r), axis=1)]
    d[y] = to_numeric(d[y])
    parts, names = [], []
    for x in xs:
        if is_numeric(d[x]):
            d[x] = to_numeric(d[x])
            parts.append(d[[x]])
            names.append(x)
        else:
            dummies = pd.get_dummies(d[x].astype(str), prefix=x, prefix_sep=" = ", drop_first=True, dtype=float)
            parts.append(dummies)
            names += list(dummies.columns)
    if not parts:
        return {"ok": False, "message": "Choisissez au moins un X."}
    X = pd.concat(parts, axis=1)
    ok = d[y].notna() & X.notna().all(axis=1)
    X, Y = X[ok].to_numpy(float), d.loc[ok, y].to_numpy(float)
    n, k = X.shape
    if n <= k + 2:
        return {"ok": False, "message": f"Pas assez d'observations ({n}) pour {k} coefficient(s)."}
    X1 = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(X1, Y, rcond=None)
    resid = Y - X1 @ beta
    sse, sst = float(resid @ resid), float(((Y - Y.mean()) ** 2).sum())
    dof = n - k - 1
    s2 = sse / dof
    cov = s2 * np.linalg.pinv(X1.T @ X1)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, 0.0)
    pv = 2 * (1 - stats.t.cdf(np.abs(t), dof))
    r2 = 1 - sse / sst if sst > 0 else 0.0
    r2a = 1 - (1 - r2) * (n - 1) / dof
    f = ((sst - sse) / k) / s2 if s2 > 0 else 0.0
    pf = 1 - stats.f.cdf(f, k, dof)
    coefs = pd.DataFrame({"Terme": ["Constante"] + names, "Coefficient": np.round(beta, 4),
                          "Erreur std": np.round(se, 4), "t": np.round(t, 2), "P-value": np.round(pv, 4)})
    coefs["Significatif"] = np.where(coefs["P-value"] < ALPHA, "Oui", "Non")
    eq = f"{y} = {beta[0]:.3f} " + " ".join(f"{'+' if b >= 0 else '−'} {abs(b):.3f}·[{nm}]" for b, nm in zip(beta[1:], names))
    return {"ok": True, "n": int(n), "R2": round(float(r2), 3), "R2_ajuste": round(float(r2a), 3),
            "p_modele": round(float(pf), 4), "equation": eq, "coefficients": coefs.to_dict("records"),
            "conclusion": (f"Le modèle explique {100*r2a:.0f} % de la variation du Y (R² ajusté), "
                           f"modèle {'significatif' if pf < ALPHA else 'non significatif'} (p={pf:.4f}).")}


# ---------------------------------------------------------------------------
# 8. Plans d'expériences factoriels complets 2^k
# ---------------------------------------------------------------------------
def doe_design(factors: list[str], replicates: int = 1) -> pd.DataFrame:
    """Plan factoriel complet 2^k en ordre standard (niveaux codés -1 / +1)."""
    import itertools
    k = len(factors)
    runs = list(itertools.product([-1, 1], repeat=k))
    rows = []
    for r in range(replicates):
        for i, lv in enumerate(runs):
            row = {"Essai": i + 1 + r * len(runs), "Réplique": r + 1}
            row.update({f: lv[::-1][j] for j, f in enumerate(factors)})
            row["Réponse (Y)"] = None
            rows.append(row)
    return pd.DataFrame(rows)


def doe_analyze(design: pd.DataFrame, factors: list[str], response: str = "Réponse (Y)") -> dict:
    """Effets principaux et interactions + significativité (Lenth si pas de réplique,
    test t si répliques)."""
    import itertools
    d = design.copy()
    d[response] = to_numeric(d[response])
    d = d.dropna(subset=[response])
    if len(d) < 2 ** len(factors):
        return {"ok": False, "message": f"Saisissez la réponse des {2**len(factors)} essais au minimum."}
    terms = []
    for r in range(1, len(factors) + 1):
        for combo in itertools.combinations(factors, r):
            col = np.prod([d[c].astype(float).values for c in combo], axis=0)
            terms.append((" × ".join(combo), col))
    y = d[response].values
    effects = [(name, float(y[col > 0].mean() - y[col < 0].mean())) for name, col in terms]
    m = len(effects)
    reps = d.groupby(factors).size().min()
    abs_e = np.abs([e for _, e in effects])
    if reps >= 2:
        # variance de l'erreur pure à partir des répliques
        s2 = d.groupby(factors)[response].var(ddof=1).mean()
        se = 2 * math.sqrt(s2 / len(d))
        dof = len(d) - 2 ** len(factors)
        pv = [2 * (1 - stats.t.cdf(abs(e) / se, dof)) if se > 0 else 1.0 for _, e in effects]
        method, threshold = "Test t (erreur pure des répliques)", float(stats.t.ppf(0.975, dof) * se)
    else:
        s0 = 1.5 * np.median(abs_e)
        pse = 1.5 * np.median(abs_e[abs_e < 2.5 * s0]) if (abs_e < 2.5 * s0).any() else s0
        threshold = float(stats.t.ppf(0.975, max(m / 3, 1)) * pse)
        pv = [None] * m
        method = "Méthode de Lenth (sans réplique)"
    rows = [{"Terme": n, "Effet": round(e, 4), "|Effet|": round(abs(e), 4),
             "P-value": None if p is None else round(p, 4),
             "Significatif": "Oui" if abs(e) > threshold else "Non"} for (n, e), p in zip(effects, pv)]
    out = pd.DataFrame(rows).sort_values("|Effet|", ascending=False).reset_index(drop=True)
    best = {f: ("+1" if dict(effects)[f] > 0 else "-1") for f in factors}
    return {"ok": True, "methode": method, "seuil": round(threshold, 4), "effets": out.to_dict("records"),
            "moyenne": round(float(y.mean()), 4), "reglage_max": best,
            "conclusion": "Facteurs significatifs : " + (", ".join(out.loc[out["Significatif"] == "Oui", "Terme"]) or "aucun")}


# ---------------------------------------------------------------------------
# 9. Taille d'échantillon et puissance
# ---------------------------------------------------------------------------
def sample_size_means(delta: float, sigma: float, alpha: float = 0.05, power: float = 0.8,
                      two_groups: bool = True, two_sided: bool = True) -> int:
    """n par groupe pour détecter un écart de moyenne `delta` (σ connu ou estimé)."""
    if delta <= 0 or sigma <= 0:
        return 0
    za = stats.norm.ppf(1 - alpha / (2 if two_sided else 1))
    zb = stats.norm.ppf(power)
    n = (2 if two_groups else 1) * ((za + zb) * sigma / delta) ** 2
    return int(math.ceil(n))


def sample_size_proportions(p1: float, p2: float, alpha: float = 0.05, power: float = 0.8,
                            two_sided: bool = True) -> int:
    """n par groupe pour détecter le passage d'une proportion p1 à p2."""
    if not (0 < p1 < 1 and 0 < p2 < 1) or p1 == p2:
        return 0
    za = stats.norm.ppf(1 - alpha / (2 if two_sided else 1))
    zb = stats.norm.ppf(power)
    pbar = (p1 + p2) / 2
    n = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return int(math.ceil(n))


def power_means(n: int, delta: float, sigma: float, alpha: float = 0.05, two_groups: bool = True) -> float:
    """Puissance atteinte avec n par groupe."""
    if n <= 1 or sigma <= 0:
        return 0.0
    se = sigma * math.sqrt((2 if two_groups else 1) / n)
    za = stats.norm.ppf(1 - alpha / 2)
    return round(float(1 - stats.norm.cdf(za - delta / se) + stats.norm.cdf(-za - delta / se)), 3)


# ---------------------------------------------------------------------------
# 10. Autres cartes de contrôle : X̄-R, p, u
# ---------------------------------------------------------------------------
_A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
_D3 = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
_D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}


def xbar_r_chart(values: Iterable[float], subgroup: int = 5) -> dict:
    x = to_numeric(pd.Series(list(values))).dropna().reset_index(drop=True)
    n = int(subgroup)
    if n < 2 or n > 10 or len(x) < 2 * n:
        return {"ok": False, "message": "Taille de sous-groupe entre 2 et 10, et au moins 2 sous-groupes."}
    k = len(x) // n
    groups = [x[i * n:(i + 1) * n] for i in range(k)]
    means = [float(g.mean()) for g in groups]
    ranges = [float(g.max() - g.min()) for g in groups]
    xbb, rbar = float(np.mean(means)), float(np.mean(ranges))
    ucl, lcl = xbb + _A2[n] * rbar, xbb - _A2[n] * rbar
    sigma = (ucl - xbb) / 3
    return {"ok": True, "means": means, "ranges": ranges, "CL": xbb, "UCL": ucl, "LCL": lcl,
            "R_CL": rbar, "R_UCL": _D4[n] * rbar, "R_LCL": _D3[n] * rbar,
            "flags": nelson_rules(pd.Series(means), xbb, sigma), "subgroup": n, "k": k}


def p_chart(defectives: Iterable[float], sizes: Iterable[float]) -> dict:
    d = to_numeric(pd.Series(list(defectives))).fillna(0)
    n = to_numeric(pd.Series(list(sizes))).fillna(0)
    ok = n > 0
    d, n = d[ok].reset_index(drop=True), n[ok].reset_index(drop=True)
    if len(d) < 2:
        return {"ok": False, "message": "Au moins 2 échantillons."}
    pbar = float(d.sum() / n.sum())
    p = (d / n).tolist()
    se = [math.sqrt(pbar * (1 - pbar) / ni) for ni in n]
    ucl = [min(1.0, pbar + 3 * s) for s in se]
    lcl = [max(0.0, pbar - 3 * s) for s in se]
    out = ["R1" if (pi > u or pi < l) else "" for pi, u, l in zip(p, ucl, lcl)]
    return {"ok": True, "p": p, "CL": pbar, "UCL": ucl, "LCL": lcl, "flags": out, "n_out": sum(1 for f in out if f)}


def u_chart(defects: Iterable[float], units: Iterable[float]) -> dict:
    c = to_numeric(pd.Series(list(defects))).fillna(0)
    n = to_numeric(pd.Series(list(units))).fillna(0)
    ok = n > 0
    c, n = c[ok].reset_index(drop=True), n[ok].reset_index(drop=True)
    if len(c) < 2:
        return {"ok": False, "message": "Au moins 2 échantillons."}
    ubar = float(c.sum() / n.sum())
    u = (c / n).tolist()
    ucl = [ubar + 3 * math.sqrt(ubar / ni) for ni in n]
    lcl = [max(0.0, ubar - 3 * math.sqrt(ubar / ni)) for ni in n]
    out = ["R1" if (ui > a or ui < b) else "" for ui, a, b in zip(u, ucl, lcl)]
    return {"ok": True, "u": u, "CL": ubar, "UCL": ucl, "LCL": lcl, "flags": out, "n_out": sum(1 for f in out if f)}


# ---------------------------------------------------------------------------
# 11. Tests d'hypothèse unitaires (boîte à outils)
# ---------------------------------------------------------------------------
def describe(values: Iterable[float]) -> dict:
    x = to_numeric(pd.Series(list(values))).dropna()
    if len(x) < 2:
        return {"ok": False, "message": "Au moins 2 valeurs numériques."}
    sh = stats.shapiro(x.sample(min(len(x), 5000), random_state=0)) if len(x) >= 3 else None
    ci = stats.t.interval(0.95, len(x) - 1, loc=x.mean(), scale=stats.sem(x)) if len(x) > 1 else (None, None)
    return {"ok": True, "n": int(len(x)), "moyenne": round(float(x.mean()), 4), "mediane": round(float(x.median()), 4),
            "ecart_type": round(float(x.std()), 4), "min": round(float(x.min()), 4), "max": round(float(x.max()), 4),
            "Q1": round(float(x.quantile(.25)), 4), "Q3": round(float(x.quantile(.75)), 4),
            "IC95_moyenne": (round(float(ci[0]), 4), round(float(ci[1]), 4)),
            "asymetrie": round(float(stats.skew(x)), 3), "aplatissement": round(float(stats.kurtosis(x)), 3),
            "p_shapiro": None if sh is None else round(float(sh.pvalue), 4),
            "normal": None if sh is None else bool(sh.pvalue >= ALPHA)}


def one_sample(values: Iterable[float], target: float, alternative: str = "two-sided") -> dict:
    x = to_numeric(pd.Series(list(values))).dropna()
    if len(x) < 3:
        return {"ok": False, "message": "Au moins 3 valeurs."}
    if _is_normal(x):
        st_, p = stats.ttest_1samp(x, target, alternative=alternative)
        test = "t à 1 échantillon"
    else:
        st_, p = stats.wilcoxon(x - target, alternative=alternative)
        test = "Wilcoxon (non normal)"
    sig = bool(p < ALPHA)
    return {"ok": True, "test": test, "p_value": round(float(p), 4), "significatif": sig,
            "moyenne": round(float(x.mean()), 4), "mediane": round(float(x.median()), 4),
            "conclusion": (f"La moyenne diffère significativement de {target} ({test}, p={p:.4f})." if sig
                           else f"Pas de différence démontrée avec {target} ({test}, p={p:.4f}).")}


def paired(before: Iterable[float], after: Iterable[float], alternative: str = "two-sided") -> dict:
    d = pd.DataFrame({"a": to_numeric(pd.Series(list(before))), "b": to_numeric(pd.Series(list(after)))}).dropna()
    if len(d) < 3:
        return {"ok": False, "message": "Au moins 3 paires complètes."}
    diff = d["b"] - d["a"]
    if _is_normal(diff):
        st_, p = stats.ttest_rel(d["b"], d["a"], alternative=alternative)
        test = "t apparié"
    else:
        st_, p = stats.wilcoxon(d["b"], d["a"], alternative=alternative)
        test = "Wilcoxon apparié (non normal)"
    sig = bool(p < ALPHA)
    return {"ok": True, "test": test, "p_value": round(float(p), 4), "significatif": sig, "n_paires": int(len(d)),
            "diff_moyenne": round(float(diff.mean()), 4),
            "conclusion": (f"Différence significative entre les deux mesures ({test}, p={p:.4f}, Δ moyen = {diff.mean():.3f})."
                           if sig else f"Pas de différence démontrée ({test}, p={p:.4f}).")}


def variances(groups: dict) -> dict:
    gs = [to_numeric(pd.Series(v)).dropna() for v in groups.values()]
    gs = [g for g in gs if len(g) >= 2]
    if len(gs) < 2:
        return {"ok": False, "message": "Au moins 2 groupes de 2 valeurs."}
    st_, p = stats.levene(*gs)
    sig = bool(p < ALPHA)
    return {"ok": True, "test": "Levene", "p_value": round(float(p), 4), "significatif": sig,
            "ecarts_types": {k: round(float(to_numeric(pd.Series(v)).dropna().std()), 4) for k, v in groups.items()},
            "conclusion": "Les variabilités diffèrent significativement." if sig else "Pas de différence de variabilité démontrée."}
