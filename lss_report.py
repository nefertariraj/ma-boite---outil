"""
lss_report.py — Soutenance DMAIC complète (PowerPoint) générée depuis le projet
==============================================================================
Remplace l'export actuel (DEFINE uniquement, Gantt = texte "[Diagramme généré]")
par un vrai storyboard Black Belt :

  Couverture → Résumé exécutif (KPI) → A3 une page →
  DEFINE (charte, SIPOC, VOC Pareto, parties prenantes, planning Gantt) →
  MEASURE (Y=f(X), VSM T0, plan de collecte & MSA, baseline I-MR + capabilité) →
  ANALYZE (criblage des X, causes racines, FMEA Pareto, validation des causes) →
  IMPROVE (solutions & sélection, bénéfice/effort, plan d'action, VSM futur, FMEA futur) →
  CONTROL (avant/après prouvé, capabilité par vague, plan de contrôle, gains, leçons, signatures)

Les graphiques sont des graphiques PowerPoint NATIFS (modifiables dans PowerPoint,
aucune dépendance kaleido/Chrome sur Streamlit Cloud). Chaque diapositive reçoit
des notes d'orateur.

Usage :
    from lss_report import compute_facts, build_pptx
    facts = compute_facts(projet)
    pptx_bytes = build_pptx(projet, facts, options={"auteur": "…"})
"""
from __future__ import annotations

import io
import json
import math
import re
from datetime import date, datetime

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

import lss_stats as S

# ---------------------------------------------------------------------------
# Charte graphique
# ---------------------------------------------------------------------------
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x6B, 0x72, 0x80)
LINE = RGBColor(0xE5, 0xE7, 0xEB)
SOFT = RGBColor(0xF8, 0xFA, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x05, 0x96, 0x69)
BAD = RGBColor(0xDC, 0x26, 0x26)
WARN = RGBColor(0xD9, 0x77, 0x06)
PHASE = {
    "SYNTHÈSE": RGBColor(0x1E, 0x3A, 0x8A),
    "DEFINE": RGBColor(0x25, 0x63, 0xEB),
    "MEASURE": RGBColor(0x0D, 0x94, 0x88),
    "ANALYZE": RGBColor(0x7C, 0x3A, 0xED),
    "IMPROVE": RGBColor(0xEA, 0x58, 0x0C),
    "CONTROL": RGBColor(0x05, 0x96, 0x69),
}
W, H = Inches(13.333), Inches(7.5)
MX = Inches(0.6)                 # marge latérale
TOP = Inches(1.35)               # début de la zone de contenu
CW = W - 2 * MX                  # largeur utile
CH = Inches(5.55)                # hauteur utile


# ---------------------------------------------------------------------------
# Lecture robuste des données du projet (formats de l'app existante)
# ---------------------------------------------------------------------------
def as_df(obj) -> pd.DataFrame:
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    if isinstance(obj, dict) and obj.get("_type_df_"):
        return pd.DataFrame(obj.get("data", []))
    if isinstance(obj, str) and obj.strip().startswith("{"):
        try:
            return pd.read_json(io.StringIO(obj))
        except Exception:
            return pd.DataFrame()
    if isinstance(obj, list):
        return pd.DataFrame([r for r in obj if isinstance(r, dict)])
    if isinstance(obj, dict):
        try:
            return pd.DataFrame(obj)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _clean_id(name: str) -> str:
    return "".join(c for c in str(name) if c.isalnum())


def _to_minutes(v, unit) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return v * {"Heures": 60.0, "Jours": 1440.0}.get(str(unit), 1.0)


def _fmt_duration(minutes: float) -> str:
    if minutes >= 1440:
        return f"{minutes/1440:.1f} j"
    if minutes >= 60:
        return f"{minutes/60:.1f} h"
    return f"{minutes:.0f} min"


def _fmt_num(v, dec=1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.0f}".replace(",", " ")
        return f"{v:.{dec}f}".rstrip("0").rstrip(".") if dec else f"{v:.0f}"
    return str(v)


def _fmt_p(p) -> str:
    if p is None:
        return "—"
    return "< 0,0001" if p < 1e-4 else f"{p:.4f}".replace(".", ",")


def _fmt_pp(p) -> str:
    """'< 0,0001' ou '= 0,0123' (pour écrire « p < 0,0001 » / « p = 0,0123 »)."""
    f = _fmt_p(p)
    return f if f.startswith("<") else f"= {f}"


def vsm_totals(macro_steps, detailed_map, value_col="Valeur", unit_col="Unité") -> dict:
    """Totaux VSM avec conversion d'unités (corrige l'état futur qui sommait
    minutes, heures et jours sans conversion)."""
    tot = {"lead_time": 0.0, "va": 0.0, "nva": 0.0, "bnva": 0.0, "attente": 0.0, "steps": []}
    for step in macro_steps or list((detailed_map or {}).keys()):
        rows = (detailed_map or {}).get(step, [])
        rec = {"etape": step, "VA": 0.0, "NVA": 0.0, "BNVA": 0.0, "Attente": 0.0}
        for r in rows if isinstance(rows, list) else []:
            m = _to_minutes(r.get(value_col, 0), r.get(unit_col, "Minutes"))
            t = str(r.get("Type d'activité", ""))
            key = "VA" if t.startswith("VA") else "BNVA" if t.startswith("BNRVA") or t.startswith("BNVA") \
                else "NVA" if t.startswith("NVA") else "Attente"
            rec[key] += m
        tot["steps"].append(rec)
        for k, fk in (("VA", "va"), ("NVA", "nva"), ("BNVA", "bnva"), ("Attente", "attente")):
            tot[fk] += rec[k]
    tot["lead_time"] = tot["va"] + tot["nva"] + tot["bnva"] + tot["attente"]
    tot["pce"] = 100 * tot["va"] / tot["lead_time"] if tot["lead_time"] > 0 else 0.0
    return tot


def cause_decisions(p: dict) -> pd.DataFrame:
    """Recalcule la décision statistique + terrain de la phase Analyze (même logique que l'app)."""
    an = (p.get("dmaic") or {}).get("analyze") or {}
    res = an.get("results") or []
    obs = an.get("gemba_observations") or {}
    rows = []
    for cid, plan in (an.get("gemba_plans") or {}).items():
        x = str(plan.get("x_critique", ""))
        pv = next((float(r.get("P-value", 1)) for r in res if str(r.get("Variable X", "")).strip().lower() == x.strip().lower()), 1.0)
        logs = (obs.get(cid) or {}).get("logs", []) if isinstance(obs.get(cid), dict) else []
        conf = sum(1 for l in logs if str(l.get("confirme", "")).lower() == "oui")
        taux = 100 * conf / len(logs) if logs else 0
        terrain = "Confirmée" if taux >= 80 else "Partielle" if taux >= 50 else "Non confirmée"
        stat_ok = pv < 0.05
        decision = ("Cause validée" if stat_ok and terrain == "Confirmée" else
                    "Partiellement validée" if stat_ok and terrain == "Partielle" else
                    "Contradiction à investiguer" if stat_ok != (terrain == "Confirmée") and terrain != "Partielle" else
                    "Non démontrée" if terrain == "Partielle" else "Rejetée")
        rows.append({"X": x, "Cause racine": plan.get("cause_racine", ""), "p-value": _fmt_p(pv),
                     "Terrain": f"{taux:.0f} % ({len(logs)} obs.)", "Décision": decision})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Faits chiffrés (une seule source de vérité pour l'écran, le PPT et l'IA)
# ---------------------------------------------------------------------------
def compute_facts(p: dict, y_col: str | None = None, spec: dict | None = None,
                  direction: str | None = None, wave: str | None = None) -> dict:
    closure = p.get("results_closure") or {}
    y_col = y_col or closure.get("y_col")
    direction = direction or closure.get("direction", "réduire")

    t0 = as_df(p.get("dc_saved_df_json"))
    ctrl = as_df((p.get("control") or {}).get("ctrl_master_data"))
    if ctrl.empty:
        cache = (p.get("control") or {}).get("vagues_data_cache") or {}
        frames = [as_df(v) for v in cache.values()]
        frames = [f for f in frames if not f.empty]
        ctrl = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    excluded = {"ID observation", "Date de modification", "Vague"}
    candidates = [c for c in t0.columns if c not in excluded]
    if not y_col and candidates:
        nums = [c for c in candidates if S.is_numeric(t0[c])]
        y_col = (nums or candidates)[0]

    if spec is None:
        spec = closure.get("spec")
    if not spec and y_col:
        pref = f"save_master_config_{_clean_id(y_col)}_"
        spec = next((v for k, v in p.items() if k.startswith(pref) and isinstance(v, dict)), None)
    spec = spec or {}

    facts: dict = {"projet": p.get("name") or p.get("nom"), "y_col": y_col, "direction": direction,
                   "spec": spec, "n_t0": int(len(t0)), "n_ctrl": int(len(ctrl))}

    # VSM avant / après
    vsm0 = vsm_totals(p.get("vsm_macro_steps"), p.get("vsm_detailed_map"))
    fs = ((p.get("dmaic") or {}).get("future_state") or {})
    fmap = fs.get("map") or p.get("future_state_map") or {}
    fsteps = fs.get("macro_steps") or p.get("future_macro_steps") or list(fmap.keys())
    vsm1 = vsm_totals(fsteps, fmap, value_col="Délai Actuel")
    facts["vsm_t0"], facts["vsm_futur"] = vsm0, vsm1
    if vsm0["lead_time"] > 0:
        facts["vsm"] = f"Lead time {_fmt_duration(vsm0['lead_time'])}, PCE {vsm0['pce']:.1f} %"

    if y_col and y_col in t0.columns:
        y0 = t0[y_col]
        facts["y_t0"] = y0.tolist()
        if S.is_numeric(y0):
            imr = S.imr_chart(y0)
            facts["imr_t0"] = imr
            lsl, usl = S.spec_limits(spec)
            facts["cap_t0"] = S.continuous_capability(y0, lsl, usl)
            facts["baseline"] = (f"{y_col} : moyenne {S.to_numeric(y0).mean():.2f}, σ {S.to_numeric(y0).std():.2f}, "
                                 f"{'stable' if imr.get('stable') else 'instable'} (n={len(y0.dropna())})")
        d0, n0 = S.count_defects(y0.tolist(), spec) if spec else (None, None)
        if spec and n0:
            facts["attr_t0"] = S.attribute_capability(d0, n0)
            facts["sigma_avant"] = facts["attr_t0"]["sigma"]

        # Vagues de contrôle
        waves_rows = [{"Période": "T0 (référence)", "N": n0 or len(y0.dropna()),
                       "Moyenne": _mean(y0), "σ": _std(y0),
                       "DPMO": facts.get("attr_t0", {}).get("dpmo"), "Sigma": facts.get("attr_t0", {}).get("sigma")}]
        if not ctrl.empty and y_col in ctrl.columns and "Vague" in ctrl.columns:
            order = sorted(ctrl["Vague"].dropna().unique(), key=lambda v: int(re.sub(r"\D", "", str(v)) or 99))
            for v in order:
                yv = ctrl.loc[ctrl["Vague"] == v, y_col]
                row = {"Période": str(v), "N": int(yv.dropna().shape[0]), "Moyenne": _mean(yv), "σ": _std(yv)}
                if spec:
                    dv, nv = S.count_defects(yv.tolist(), spec)
                    if nv:
                        ac = S.attribute_capability(dv, nv)
                        row.update(DPMO=ac["dpmo"], Sigma=ac["sigma"])
                waves_rows.append(row)
            facts["waves"] = waves_rows
            sel = ctrl if not wave else ctrl[ctrl["Vague"] == wave]
            y1 = sel[y_col]
            ba = S.before_after(y0, y1, direction=direction)
            facts["before_after"] = ba
            facts["y_ctrl"] = [(str(v), val) for v, val in zip(sel["Vague"], y1)]
            if spec:
                d1, n1 = S.count_defects(y1.tolist(), spec)
                if n1:
                    facts["attr_ctrl"] = S.attribute_capability(d1, n1)
                    facts["sigma_apres"] = facts["attr_ctrl"]["sigma"]
            if S.is_numeric(y1):
                lsl, usl = S.spec_limits(spec)
                facts["cap_ctrl"] = S.continuous_capability(y1, lsl, usl)
        else:
            facts["waves"] = waves_rows

    gains = as_df(closure.get("gains"))
    if not gains.empty:
        col = next((c for c in gains.columns if "montant" in c.lower()), None)
        if col:
            facts["gains_total"] = float(pd.to_numeric(gains[col], errors="coerce").fillna(0).sum())
            hard = gains[gains.astype(str).apply(lambda r: "hard" in " ".join(r).lower(), axis=1)]
            facts["gains_hard"] = float(pd.to_numeric(hard[col], errors="coerce").fillna(0).sum()) if not hard.empty else 0.0
            facts["gains"] = f"{facts['gains_total']:,.0f} Ar/an".replace(",", " ")
    return facts


def _mean(s):
    v = S.to_numeric(pd.Series(s)).dropna()
    return round(float(v.mean()), 2) if len(v) else None


def _std(s):
    v = S.to_numeric(pd.Series(s)).dropna()
    return round(float(v.std()), 2) if len(v) > 1 else None


# ---------------------------------------------------------------------------
# Primitives de mise en page
# ---------------------------------------------------------------------------
def _tr(s, n=300) -> str:
    s = "" if s is None or (isinstance(s, float) and math.isnan(s)) else str(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


class Deck:
    def __init__(self, project_name: str, author: str = "", date_txt: str = ""):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.project = project_name
        self.author = author
        self.date_txt = date_txt or datetime.now().strftime("%d/%m/%Y")
        self.n = 0

    # -- structure ---------------------------------------------------------
    def slide(self, phase: str, title: str, subtitle: str = "", notes: str = ""):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        col = PHASE.get(phase, PHASE["SYNTHÈSE"])
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), H)
        _fill(bar, col)
        self.text(s, MX, Inches(0.35), CW, Inches(0.3), phase, 11, col, bold=True)
        self.text(s, MX, Inches(0.6), CW, Inches(0.55), title, 24, INK, bold=True)
        if subtitle:
            self.text(s, MX, Inches(1.05), CW, Inches(0.3), subtitle, 12, MUTED)
        foot = f"{_tr(self.project, 80)}   ·   {self.date_txt}"
        self.text(s, MX, H - Inches(0.42), Inches(9), Inches(0.3), foot, 9, MUTED)
        self.text(s, W - MX - Inches(1), H - Inches(0.42), Inches(1), Inches(0.3), str(self.n), 9, MUTED, align=PP_ALIGN.RIGHT)
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    # -- texte ---------------------------------------------------------------
    def text(self, s, x, y, w, h, txt, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.02)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.vertical_anchor = anchor
        lines = txt if isinstance(txt, list) else [txt]
        for i, line in enumerate(lines):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.alignment = align
            r = para.add_run()
            r.text = str(line)
            r.font.size, r.font.bold = Pt(size), bold
            r.font.color.rgb = color
        return tb

    def card(self, s, x, y, w, h, title, body, accent=None, size=12, fill=SOFT, max_chars=None):
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        _fill(box, fill)
        box.line.color.rgb = LINE
        box.line.width = Pt(0.75)
        if accent is not None:
            strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(0.06), h)
            _fill(strip, accent)
        pad = Inches(0.18)
        self.text(s, x + pad, y + Inches(0.12), w - 2 * pad, Inches(0.3), title, 12, accent or INK, bold=True)
        if max_chars is None:
            # estimation grossière de la capacité du cadre
            cpl = max(20, int((w - 2 * pad) / Emu(Pt(size) * 0.52)))
            nlines = max(1, int((h - Inches(0.5)) / Emu(Pt(size) * 1.25)))
            max_chars = cpl * nlines
        items = body if isinstance(body, list) else [body]
        out, used = [], 0
        for it in items:
            t = _tr(it, max(40, max_chars - used))
            if not t:
                continue
            line_chars = len(t) + 30
            if used + line_chars > max_chars and out:
                out.append("…")
                break
            out.append(("• " + t) if isinstance(body, list) else t)
            used += line_chars
        self.text(s, x + pad, y + Inches(0.45), w - 2 * pad, h - Inches(0.55), out or ["—"], size, INK)

    def kpi(self, s, x, y, w, h, label, value, sub="", color=INK):
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        _fill(box, WHITE)
        box.line.color.rgb = LINE
        self.text(s, x + Inches(0.15), y + Inches(0.1), w - Inches(0.3), Inches(0.3), label, 11, MUTED)
        self.text(s, x + Inches(0.15), y + Inches(0.38), w - Inches(0.3), Inches(0.6), value, 26, color, bold=True)
        if sub:
            self.text(s, x + Inches(0.15), y + h - Inches(0.42), w - Inches(0.3), Inches(0.35), sub, 10, MUTED)

    def table(self, s, df: pd.DataFrame, x, y, w, h=None, max_rows=12, col_widths=None,
              header_color=None, max_cell=90):
        df = df.copy()
        extra = 0
        if len(df) > max_rows:
            extra = len(df) - max_rows
            df = df.head(max_rows)
        nrows, ncols = len(df) + 1, len(df.columns)
        size = 11 if nrows <= 8 else 10 if nrows <= 11 else 9
        row_h = Inches(0.36 if size >= 11 else 0.32)
        h = h or row_h * nrows
        shape = s.shapes.add_table(nrows, ncols, x, y, w, min(h, row_h * nrows))
        tbl = shape.table
        tbl.first_row = True
        if col_widths:
            tot = sum(col_widths)
            for i, cw in enumerate(col_widths):
                tbl.columns[i].width = int(w * cw / tot)
        hc = header_color or INK
        for j, c in enumerate(df.columns):
            _cell(tbl.cell(0, j), str(c), size, WHITE, hc, bold=True)
        for i, row in enumerate(df.itertuples(index=False), start=1):
            for j, v in enumerate(row):
                _cell(tbl.cell(i, j), _tr(_fmt_cell(v), max_cell), size, INK, WHITE if i % 2 else SOFT)
        if extra:
            self.text(s, x, y + row_h * nrows + Inches(0.05), w, Inches(0.3),
                      f"+ {extra} ligne(s) non affichée(s) — voir l'annexe / l'application", 9, MUTED)
        return shape

    def empty(self, s, msg="Section non renseignée dans l'application."):
        self.card(s, MX, TOP + Inches(0.3), CW, Inches(1.2), "À compléter", msg, accent=WARN)

    def save(self) -> bytes:
        buf = io.BytesIO()
        self.prs.save(buf)
        return buf.getvalue()


def _fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _fmt_cell(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool):
        return "✓" if v else ""
    if isinstance(v, float):
        if v != 0 and abs(v) < 0.01:
            return _fmt_p(v) if abs(v) < 1e-4 else f"{v:.4f}"
        return _fmt_num(v, 2)
    if isinstance(v, (datetime, date)):
        return v.strftime("%d/%m/%Y")
    return str(v)


def _cell(cell, text, size, color, fill, bold=False):
    cell.text = text
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = cell.margin_right = Inches(0.06)
    cell.margin_top = cell.margin_bottom = Inches(0.03)
    for para in cell.text_frame.paragraphs:
        for r in para.runs:
            r.font.size, r.font.bold = Pt(size), bold
            r.font.color.rgb = color


# ---------------------------------------------------------------------------
# Graphiques natifs
# ---------------------------------------------------------------------------
def _style_chart(chart, legend=True, size=10):
    chart.font.size = Pt(size)
    chart.font.color.rgb = INK
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False


def _axis_clean(axis, title=None):
    axis.has_major_gridlines = False
    axis.format.line.color.rgb = LINE
    axis.tick_labels.font.size = Pt(9)
    axis.tick_labels.font.color.rgb = MUTED
    if title:
        axis.has_title = True
        axis.axis_title.text_frame.text = title
        axis.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(9)


def bar_chart(s, x, y, w, h, categories, series: dict, colors=None, stacked=False, horizontal=False,
              labels=False, legend=None, number_format='0'):
    cd = CategoryChartData()
    cd.categories = [_tr(c, 40) for c in categories]
    for name, vals in series.items():
        cd.add_series(name, [None if v is None else float(v) for v in vals])
    kind = {(False, False): XL_CHART_TYPE.COLUMN_CLUSTERED, (True, False): XL_CHART_TYPE.COLUMN_STACKED,
            (False, True): XL_CHART_TYPE.BAR_CLUSTERED, (True, True): XL_CHART_TYPE.BAR_STACKED}[(stacked, horizontal)]
    chart = s.shapes.add_chart(kind, x, y, w, h, cd).chart
    _style_chart(chart, legend if legend is not None else len(series) > 1)
    _axis_clean(chart.category_axis)
    _axis_clean(chart.value_axis)
    chart.value_axis.has_major_gridlines = True
    chart.value_axis.major_gridlines.format.line.color.rgb = LINE
    chart.value_axis.tick_labels.number_format = number_format
    chart.value_axis.tick_labels.number_format_is_linked = False
    all_vals = [float(v) for vals in series.values() for v in vals if v is not None]
    if all_vals and min(all_vals) >= 0:
        chart.value_axis.minimum_scale = 0
    plot = chart.plots[0]
    plot.gap_width = 60
    if stacked:
        plot.overlap = 100
    for i, ser in enumerate(plot.series):
        if colors and i < len(colors) and colors[i] is not None:
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = colors[i]
    if labels:
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(9)
        plot.data_labels.number_format = number_format
        plot.data_labels.number_format_is_linked = False
    return chart


def line_chart(s, x, y, w, h, categories, series: dict, colors=None, dashed=(), markers=(), legend=True):
    cd = CategoryChartData()
    cd.categories = [str(c) for c in categories]
    for name, vals in series.items():
        cd.add_series(name, [None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v) for v in vals])
    chart = s.shapes.add_chart(XL_CHART_TYPE.LINE, x, y, w, h, cd).chart
    _style_chart(chart, legend)
    _axis_clean(chart.category_axis)
    _axis_clean(chart.value_axis)
    chart.value_axis.has_major_gridlines = True
    chart.value_axis.major_gridlines.format.line.color.rgb = LINE
    for i, ser in enumerate(chart.plots[0].series):
        ser.smooth = False
        col = colors[i] if colors and i < len(colors) else INK
        ser.format.line.color.rgb = col
        ser.format.line.width = Pt(2 if i in markers else 1.25)
        if i in dashed:
            from pptx.enum.dml import MSO_LINE_DASH_STYLE
            ser.format.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if i in markers:
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 5
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = col
            ser.marker.format.line.color.rgb = col
        else:
            ser.marker.style = XL_MARKER_STYLE.NONE
    if len(categories) > 25:
        from pptx.enum.chart import XL_TICK_LABEL_POSITION
        chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    return chart


def scatter_chart(s, x, y, w, h, points: list[tuple[str, float, float]], x_title, y_title, color):
    cd = XyChartData()
    ser = cd.add_series("Solutions")
    for _, px, py in points:
        ser.add_data_point(px, py)
    chart = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, x, y, w, h, cd).chart
    _style_chart(chart, legend=False)
    _axis_clean(chart.category_axis, x_title)
    _axis_clean(chart.value_axis, y_title)
    sr = chart.plots[0].series[0]
    sr.format.line.fill.background()
    sr.marker.style = XL_MARKER_STYLE.CIRCLE
    sr.marker.size = 11
    sr.marker.format.fill.solid()
    sr.marker.format.fill.fore_color.rgb = color
    for i, (label, _, _) in enumerate(points):
        dl = sr.points[i].data_label
        dl.has_text_frame = True
        dl.text_frame.text = _tr(label, 28)
        dl.position = XL_LABEL_POSITION.ABOVE
        dl.font.size = Pt(9)
    return chart


def gantt_chart(s, x, y, w, h, tasks: list[tuple[str, date, date]], color):
    t0 = min(t[1] for t in tasks)
    tasks = list(reversed(tasks))
    offs = [(st - t0).days for _, st, _ in tasks]
    durs = [max(1, (en - st).days) for _, st, en in tasks]
    ch = bar_chart(s, x, y, w, h, [t[0] for t in tasks], {"Décalage": offs, "Durée (jours)": durs},
                   colors=[None, color], stacked=True, horizontal=True, legend=False)
    ch.plots[0].series[0].format.fill.background()
    _axis_clean(ch.value_axis, f"Jours depuis le {t0.strftime('%d/%m/%Y')}")
    ch.value_axis.has_major_gridlines = True
    ch.value_axis.major_gridlines.format.line.color.rgb = LINE
    return ch


# ---------------------------------------------------------------------------
# Construction de la soutenance
# ---------------------------------------------------------------------------
def build_pptx(p: dict, facts: dict | None = None, options: dict | None = None) -> bytes:
    o = {"auteur": "", "date": "", "sponsor": "", "titre_soutenance": "Soutenance de projet DMAIC",
         "phases": ["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"], "skip_empty": True,
         "summary": None}
    o.update(options or {})
    facts = facts or compute_facts(p)
    name = p.get("name") or p.get("nom") or "Projet Lean Six Sigma"
    d = Deck(name, o["auteur"], o["date"])
    closure = p.get("results_closure") or {}
    dm = p.get("dmaic") or {}
    an, im = dm.get("analyze") or {}, dm.get("improve") or {}

    _cover(d, p, o, facts)
    _executive(d, p, o, facts)
    _a3(d, p, facts, closure)
    _maturity_slide(d, p, facts)

    if "DEFINE" in o["phases"]:
        _define(d, p, o)
    if "MEASURE" in o["phases"]:
        _measure(d, p, o, facts)
    if "ANALYZE" in o["phases"]:
        _analyze(d, p, o, an)
    if "IMPROVE" in o["phases"]:
        _improve(d, p, o, im, facts)
    if "CONTROL" in o["phases"]:
        _control(d, p, o, facts, closure)
    return d.save()


# ---- Synthèse ---------------------------------------------------------------
def _cover(d: Deck, p, o, facts):
    s = d.prs.slides.add_slide(d.blank)
    d.n += 1
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    _fill(bg, PHASE["SYNTHÈSE"])
    x = Inches(0.9)
    d.text(s, x, Inches(1.6), Inches(11), Inches(0.4), o["titre_soutenance"].upper(), 14, RGBColor(0xBF, 0xDB, 0xFE), bold=True)
    d.text(s, x, Inches(2.1), Inches(11.5), Inches(1.8), _tr(d.project, 110), 40, WHITE, bold=True)
    sub = f"CTQ : {_tr(p.get('selected_ctq'), 120)}" if p.get("selected_ctq") else ""
    d.text(s, x, Inches(4.0), Inches(11), Inches(0.5), sub, 16, RGBColor(0xDB, 0xEA, 0xFE))
    meta = "   ·   ".join(v for v in [f"Black Belt : {o['auteur']}" if o["auteur"] else "",
                                       f"Sponsor : {o['sponsor']}" if o["sponsor"] else "", d.date_txt] if v)
    d.text(s, x, Inches(6.2), Inches(11.5), Inches(0.4), meta, 13, WHITE)
    x0 = x
    for i, ph in enumerate(["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"]):
        chip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x0 + i * Inches(1.25), Inches(5.2), Inches(1.15), Inches(0.08))
        _fill(chip, PHASE[ph])
    s.notes_slide.notes_text_frame.text = ("Présentez-vous, le sponsor et l'enjeu en une phrase. "
                                           "Annoncez la structure DMAIC et la durée de la soutenance.")


def _executive(d: Deck, p, o, facts):
    summ = o.get("summary") or {}
    s = d.slide("SYNTHÈSE", "Résumé exécutif",
                f"Source de la synthèse : {summ.get('source', 'à générer')}" if summ else "",
                notes="Commencez par le résultat : c'est ce que le comité retiendra. Puis expliquez comment vous l'avez prouvé.")
    ba = facts.get("before_after") or {}
    y = facts.get("y_col") or "Y"
    tiles = []
    if ba.get("ok") and ba.get("type") == "continu":
        good = ba["significatif"]
        tiles += [(f"{_tr(y, 28)} — avant", _fmt_num(ba["moyenne_avant"], 2), f"n = {ba['n_avant']}", INK),
                  (f"{_tr(y, 28)} — après", _fmt_num(ba["moyenne_apres"], 2), f"n = {ba['n_apres']}", GOOD if good else WARN),
                  ("Variation", f"{ba['delta_%']:+.1f} %" if ba.get("delta_%") is not None else "—",
                   f"p {_fmt_pp(ba['p_value'])}", GOOD if good else WARN)]
    elif ba.get("ok"):
        good = ba["significatif"]
        tiles += [("Taux de défauts avant", f"{ba['taux_defaut_avant_%']:.1f} %", f"n = {ba['n_avant']}", INK),
                  ("Taux de défauts après", f"{ba['taux_defaut_apres_%']:.1f} %", f"n = {ba['n_apres']}", GOOD if good else WARN),
                  ("Preuve statistique", "Oui" if good else "Non", f"p {_fmt_pp(ba['p_value'])}", GOOD if good else BAD)]
    if facts.get("sigma_avant") is not None and facts.get("sigma_apres") is not None:
        tiles.append(("Niveau sigma", f"{facts['sigma_avant']} → {facts['sigma_apres']}", "convention 1,5σ", INK))
    if facts.get("gains_total"):
        tiles.append(("Gains annuels", f"{facts['gains_total']/1e6:,.1f} M Ar".replace(",", " "),
                      f"dont hard : {facts.get('gains_hard', 0)/1e6:,.1f} M".replace(",", " "), GOOD))
    if not tiles:
        tiles = [("Résultats", "À compléter", "Saisir T0 (Measure) et les vagues (Control)", WARN)]
    tiles = tiles[:5]
    tw = (CW - Inches(0.2) * (len(tiles) - 1)) / len(tiles)
    for i, (lab, val, sub, col) in enumerate(tiles):
        d.kpi(s, MX + i * (tw + Inches(0.2)), TOP + Inches(0.1), tw, Inches(1.35), lab, val, sub, col)
    y2 = TOP + Inches(1.7)
    resume = summ.get("resume") or (ba.get("conclusion") if ba else "") or "Générez la synthèse depuis l'onglet Résultats."
    d.card(s, MX, y2, CW * 0.58, Inches(3.75), "Synthèse", _tr(resume, 900), accent=PHASE["SYNTHÈSE"], size=13)
    msgs = summ.get("messages_cles") or []
    asks = summ.get("demandes") or []
    d.card(s, MX + CW * 0.6, y2, CW * 0.4, Inches(1.95), "Messages clés", msgs or ["—"], size=11)
    d.card(s, MX + CW * 0.6, y2 + Inches(2.05), CW * 0.4, Inches(1.7), "Décisions attendues du sponsor", asks or ["—"], size=11)


def _a3(d: Deck, p, facts, closure):
    s = d.slide("SYNTHÈSE", "Le projet sur une page (A3)",
                notes="Le A3 raconte toute l'histoire en 60 secondes : gauche = comprendre, droite = agir et pérenniser.")
    an = (p.get("dmaic") or {}).get("analyze") or {}
    im = (p.get("dmaic") or {}).get("improve") or {}
    causes = [c for st_ in (an.get("x_analyses") or {}).values() for c in st_.get("causes_racines_list", []) if c]
    dec = cause_decisions(p)
    if not dec.empty:
        causes = [f"{r['Cause racine']} ({r['Décision']})" for _, r in dec.iterrows()] or causes
    sols = [str(r.get("Solution potentielle")) for r in as_df(im.get("strategies")).to_dict("records")
            if r.get("Solution potentielle")]
    ba = facts.get("before_after") or {}
    vsm0, vsm1 = facts.get("vsm_t0", {}), facts.get("vsm_futur", {})
    t0 = []
    if facts.get("baseline"):
        t0.append(facts["baseline"])
    if vsm0.get("lead_time"):
        t0.append(f"Lead time {_fmt_duration(vsm0['lead_time'])} — PCE {vsm0['pce']:.1f} %")
    if facts.get("attr_t0"):
        a = facts["attr_t0"]
        t0.append(f"DPMO {_fmt_num(a['dpmo'], 0)} — sigma {a['sigma']}")
    res = []
    if ba.get("ok"):
        res.append(ba["conclusion"])
    if vsm1.get("lead_time") and vsm0.get("lead_time"):
        res.append(f"Lead time {_fmt_duration(vsm0['lead_time'])} → {_fmt_duration(vsm1['lead_time'])}")
    if facts.get("gains"):
        res.append(f"Gains : {facts['gains']}")
    ctrl = [str(r.get("Que contrôler ?", "")) + " — " + str(r.get("Fréquence", ""))
            for r in as_df(closure.get("control_plan")).to_dict("records") if r.get("Que contrôler ?")]
    ctrl += [f"Prochaine étape : {x}" for x in (closure.get("next_steps") or "").split("\n") if x.strip()][:2]

    gw, gh = (CW - Inches(0.3)) / 3, (CH - Inches(0.25)) / 2
    blocks = [
        ("1. Problème & objectif", PHASE["DEFINE"], [p.get("problem") or "—",
                                                     (p.get("charte") or {}).get("objectif_smart") or f"CTQ : {p.get('selected_ctq') or '—'}"]),
        ("2. Situation initiale (T0)", PHASE["MEASURE"], t0 or ["—"]),
        ("3. Causes racines", PHASE["ANALYZE"], causes or ["—"]),
        ("4. Solutions déployées", PHASE["IMPROVE"], sols or ["—"]),
        ("5. Résultats prouvés", PHASE["CONTROL"], res or ["—"]),
        ("6. Pérennisation", PHASE["CONTROL"], ctrl or ["Plan de contrôle à formaliser"]),
    ]
    for i, (title, col, body) in enumerate(blocks):
        r, c = divmod(i, 3)
        d.card(s, MX + c * (gw + Inches(0.15)), TOP + r * (gh + Inches(0.15)), gw, gh, title, body,
               accent=col, size=11, fill=WHITE)


def _maturity_slide(d: Deck, p, facts):
    import lss_agents as G  # import tardif (évite l'import circulaire)
    mat = G.maturity(p, facts)
    warn = G.pitfalls(p, facts)
    s = d.slide("SYNTHÈSE", "Rigueur de la démarche : maturité DMAIC", f"Maturité globale : {mat['global']} %",
                notes="Montrez que chaque jalon a été franchi avec ses preuves ; assumez les points encore ouverts.")
    rev = G.PHASES[::-1]
    ch_ = bar_chart(s, MX, TOP, CW * 0.45, CH - Inches(0.1), rev, {"Maturité (%)": [mat["scores"][ph] for ph in rev]},
                    colors=[PHASE["SYNTHÈSE"]], horizontal=True, labels=True, legend=False)
    ch_.value_axis.maximum_scale = 100
    todo = [f"{ph} : {c}" for ph in G.PHASES for c, ok, _ in mat[ph] if not ok]
    d.card(s, MX + CW * 0.48, TOP, CW * 0.52, Inches(2.6), "Jalons encore ouverts", todo or ["Tous les jalons sont franchis."],
           accent=WARN if todo else GOOD, size=11, fill=WHITE)
    d.card(s, MX + CW * 0.48, TOP + Inches(2.8), CW * 0.52, CH - Inches(2.9), "Garde-fous méthodologiques",
           [f"{ph} — {m}" for g, ph, m in warn] or ["Aucune alerte sur les données du projet."],
           accent=BAD if any(g == "🔴" for g, _, _ in warn) else GOOD, size=11, fill=WHITE)


# ---- DEFINE -----------------------------------------------------------------
def _define(d: Deck, p, o):
    col = PHASE["DEFINE"]
    team = as_df(p.get("team_data"))
    team = team[team.astype(str).apply(lambda r: "".join(r).strip() != "", axis=1)] if not team.empty else team
    s = d.slide("DEFINE", "Charte du projet",
                notes="Énoncé factuel du problème (sans cause ni solution), CTQ chiffré, bénéfices attendus, équipe.")
    half = (CW - Inches(0.25)) / 2
    d.card(s, MX, TOP, half, Inches(2.6), "Énoncé du problème", _tr(p.get("problem") or "—", 700), accent=col, size=12)
    d.card(s, MX + half + Inches(0.25), TOP, half, Inches(1.2), "CTQ (Y du projet)", _tr(p.get("selected_ctq") or "—", 200), accent=col, size=13)
    d.card(s, MX + half + Inches(0.25), TOP + Inches(1.4), half, Inches(1.2), "Bénéfices attendus",
           _tr(p.get("benefices_saisie") or "—", 300), accent=col, size=11)
    d.text(s, MX, TOP + Inches(2.85), CW, Inches(0.3), "Équipe projet", 13, col, bold=True)
    if not team.empty:
        d.table(s, team, MX, TOP + Inches(3.2), CW, max_rows=6, header_color=col)
    else:
        d.text(s, MX, TOP + Inches(3.2), CW, Inches(0.3), "Équipe non renseignée.", 11, MUTED)

    ch = p.get("charte") or {}
    copq = as_df(ch.get("copq"))
    if not copq.empty:
        copq = copq[pd.to_numeric(copq.get("Coût unitaire (Ar)"), errors="coerce").fillna(0) > 0]
    if ch.get("objectif_smart") or ch.get("in_scope") or not copq.empty:
        s = d.slide("DEFINE", "Objectif SMART, périmètre et business case",
                    notes="Le business case chiffre ce que coûte le problème aujourd'hui : c'est la justification du projet.")
        d.card(s, MX, TOP, CW, Inches(0.95), "Objectif SMART", ch.get("objectif_smart") or "—", accent=col, size=14, fill=WHITE)
        third = (CW - Inches(0.4)) / 3
        y2 = TOP + Inches(1.15)
        d.card(s, MX, y2, third, Inches(2.0), "Dans le périmètre", [l for l in (ch.get("in_scope") or "").split("\n") if l.strip()] or ["—"], accent=GOOD, size=11)
        d.card(s, MX + third + Inches(0.2), y2, third, Inches(2.0), "Hors périmètre", [l for l in (ch.get("out_scope") or "").split("\n") if l.strip()] or ["—"], accent=BAD, size=11)
        tot = float(ch.get("copq_total") or 0)
        d.kpi(s, MX + 2 * (third + Inches(0.2)), y2, third, Inches(2.0), "Coût annuel de la non-qualité",
              f"{tot/1e6:,.1f} M Ar".replace(",", " ") if tot else "—",
              f"Gain visé : {tot * float(ch.get('gain_vise_pct', 0)) / 100 / 1e6:,.1f} M Ar".replace(",", " ") if tot else "", color=BAD)
        if not copq.empty:
            t = copq.copy()
            t["Total (Ar)"] = pd.to_numeric(t["Volume annuel"], errors="coerce").fillna(0) * pd.to_numeric(t["Coût unitaire (Ar)"], errors="coerce").fillna(0)
            for c_ in ("Coût unitaire (Ar)", "Total (Ar)"):
                t[c_] = t[c_].map(lambda v: _fmt_num(float(v), 0))
            d.table(s, t, MX, y2 + Inches(2.2), CW, max_rows=4, header_color=col, max_cell=60)

    sip = as_df(p.get("sipoc_data"))
    if not sip.empty:
        sip = sip[sip.astype(str).apply(lambda r: "".join(r).strip() != "", axis=1)]
    if not sip.empty or not o["skip_empty"]:
        s = d.slide("DEFINE", "SIPOC — périmètre du processus",
                    notes="Délimitez le périmètre : premier et dernier pas du processus, clients et sorties critiques.")
        if sip.empty:
            d.empty(s)
        else:
            cols = [c for c in ["Supplier", "Input", "Process", "Output", "Customer"] if c in sip.columns]
            d.table(s, sip[cols], MX, TOP, CW, max_rows=13, header_color=col)

    voc = as_df(p.get("saved_voc_results"))
    if not voc.empty or not o["skip_empty"]:
        s = d.slide("DEFINE", "Voix du client — Pareto des irritants",
                    notes="Les verbatims ont été regroupés par thème ; le Pareto désigne le thème prioritaire et son CTQ.")
        if voc.empty:
            d.empty(s)
        else:
            cnt_col = next((c for c in voc.columns if "occurrence" in c.lower()), None)
            th_col = next((c for c in voc.columns if "thème" in c.lower()), voc.columns[0])
            par = S.pareto(voc[th_col].astype(str), voc[cnt_col] if cnt_col else [1] * len(voc))
            ch = bar_chart(s, MX, TOP, CW * 0.55, CH - Inches(0.2), par["Catégorie"], {"Occurrences": par["Nombre"]},
                           colors=[col], labels=True, legend=False)
            keep = [c for c in [th_col, "CTQ", "pourcentage"] if c in voc.columns]
            d.table(s, voc[keep], MX + CW * 0.58, TOP, CW * 0.42, max_rows=8, header_color=col, max_cell=60)

    stk = as_df(p.get("stakeholders"))
    if not stk.empty or not o["skip_empty"]:
        s = d.slide("DEFINE", "Parties prenantes — niveau d'adhésion",
                    notes="Où se situe chaque acteur aujourd'hui, et qui faut-il faire bouger pour réussir le changement ?")
        if stk.empty:
            d.empty(s)
        else:
            levels = ["Strongly Against", "Moderately Against", "Neutral", "Moderately Supportive", "Strongly Supportive"]
            fr = {"Strongly Against": "Très opposé", "Moderately Against": "Opposé", "Neutral": "Neutre",
                  "Moderately Supportive": "Favorable", "Strongly Supportive": "Très favorable"}
            name_col = "Name" if "Name" in stk.columns else stk.columns[0]
            rows = []
            for _, r in stk.iterrows():
                lvl = next((fr[l] for l in levels if l in stk.columns and bool(r.get(l))), "—")
                rows.append({"Partie prenante": r.get(name_col), "Adhésion actuelle": lvl})
            sdf = pd.DataFrame(rows)
            d.table(s, sdf, MX, TOP, CW * 0.45, max_rows=12, header_color=col)
            counts = sdf["Adhésion actuelle"].value_counts().reindex(list(fr.values()), fill_value=0)
            bar_chart(s, MX + CW * 0.5, TOP, CW * 0.5, CH - Inches(0.3), list(counts.index), {"Acteurs": list(counts.values)},
                      colors=[col], labels=True, legend=False)

    g = as_df(p.get("gantt_data"))
    tasks = []
    if not g.empty and {"Etape", "Début", "Fin"} <= set(g.columns):
        for _, r in g.iterrows():
            st_, en = pd.to_datetime(r["Début"], errors="coerce"), pd.to_datetime(r["Fin"], errors="coerce")
            if pd.notna(st_) and pd.notna(en) and str(r["Etape"]).strip():
                tasks.append((f"{r['Etape']} ({r.get('Responsable', '')})".replace(" ()", ""), st_.date(), en.date()))
    if tasks or not o["skip_empty"]:
        s = d.slide("DEFINE", "Planning et jalons DMAIC",
                    notes="Rappelez les jalons prévus et les écarts éventuels avec le réalisé.")
        if tasks:
            gantt_chart(s, MX, TOP, CW, CH - Inches(0.2), tasks, col)
        else:
            d.empty(s)


# ---- MEASURE ----------------------------------------------------------------
def _measure(d: Deck, p, o, facts):
    col = PHASE["MEASURE"]
    xt = as_df(p.get("measure_x_table"))
    if not xt.empty:
        xt = xt[~xt.get("Description", pd.Series(dtype=str)).astype(str).str.startswith(("Attente de la collecte", "Facteur de variabilité additionnel"))]
    if not xt.empty or not o["skip_empty"]:
        s = d.slide("MEASURE", "Y = f(X) — variables candidates",
                    f"Y : {_tr(p.get('selected_ctq'), 120)}",
                    notes="Expliquez comment les X candidats ont été identifiés (VOC, VSM, terrain) avant d'être testés.")
        if xt.empty:
            d.empty(s)
        else:
            d.table(s, xt, MX, TOP, CW, max_rows=11, header_color=col, col_widths=[1, 5, 1.4, 2.4][: len(xt.columns)])

    v0 = facts.get("vsm_t0") or {}
    if v0.get("lead_time") or not o["skip_empty"]:
        s = d.slide("MEASURE", "Cartographie de la chaîne de valeur (état actuel)",
                    notes="Le PCE montre la part du temps qui apporte réellement de la valeur au client.")
        if not v0.get("lead_time"):
            d.empty(s)
        else:
            steps = v0["steps"]
            kw = (CW - Inches(0.4)) / 3
            d.kpi(s, MX, TOP, kw, Inches(1.2), "Lead time total", _fmt_duration(v0["lead_time"]))
            d.kpi(s, MX + kw + Inches(0.2), TOP, kw, Inches(1.2), "Temps à valeur ajoutée", _fmt_duration(v0["va"]), color=GOOD)
            d.kpi(s, MX + 2 * (kw + Inches(0.2)), TOP, kw, Inches(1.2), "Efficience du processus (PCE)", f"{v0['pce']:.1f} %",
                  color=BAD if v0["pce"] < 10 else WARN if v0["pce"] < 25 else GOOD)
            unit, div = ("heures", 60) if v0["lead_time"] > 600 else ("minutes", 1)
            bar_chart(s, MX, TOP + Inches(1.4), CW, CH - Inches(1.5), [x["etape"] for x in steps],
                      {k: [x[k] / div for x in steps] for k in ["VA", "NVA", "BNVA", "Attente"]},
                      colors=[GOOD, BAD, WARN, MUTED], stacked=True, number_format='0.0')
            d.text(s, W - MX - Inches(3), TOP + Inches(1.4), Inches(3), Inches(0.3), f"Durées en {unit}", 9, MUTED, align=PP_ALIGN.RIGHT)

    dcp = as_df(p.get("master_dcp_table"))
    msa = as_df(p.get("msa_table_saved"))
    if not dcp.empty or not msa.empty or not o["skip_empty"]:
        s = d.slide("MEASURE", "Plan de collecte et validation du système de mesure",
                    f"Système de mesure certifié : {'OUI' if p.get('msa_is_validated_status') else 'NON'}",
                    notes="Sans système de mesure fiable, aucune conclusion n'est défendable : présentez %GRR / Kappa.")
        if dcp.empty and msa.empty:
            d.empty(s)
        if not dcp.empty:
            keep = [c for c in ["Variable à mesurer", "Définition opérationnelle exacte", "Type de donnée", "Fréquence",
                                "Taille échantillon", "Responsable collecte"] if c in dcp.columns]
            d.table(s, dcp[keep], MX, TOP, CW, max_rows=5, header_color=col, max_cell=60)
        if not msa.empty:
            d.table(s, msa, MX, TOP + Inches(2.9 if not dcp.empty else 0), CW, max_rows=5, header_color=col)
        grr = (p.get("results_closure") or {}).get("gage_rr")
        if grr and grr.get("ok"):
            d.text(s, MX, H - Inches(0.85), CW, Inches(0.3),
                   f"Gage R&R : %GRR = {grr['%GRR']} %, ndc = {grr['ndc']} → {grr['verdict']}", 11, col, bold=True)

    imr = facts.get("imr_t0")
    if (imr and imr.get("ok")) or not o["skip_empty"]:
        y = facts.get("y_col") or "Y"
        s = d.slide("MEASURE", f"Baseline — carte I-MR de « {_tr(y, 50)} »",
                    notes="Le processus est-il stable (causes communes uniquement) ? Quelle est sa capabilité de départ ?")
        if not (imr and imr.get("ok")):
            d.empty(s, "Aucune donnée T0 numérique : alimentez la collecte (Measure, écran 2).")
        else:
            n = len(imr["values"])
            line_chart(s, MX, TOP, CW * 0.68, CH - Inches(0.1), list(range(1, n + 1)),
                       {y: imr["values"], "CL": [imr["CL"]] * n, "UCL": [imr["UCL"]] * n, "LCL": [imr["LCL"]] * n},
                       colors=[PHASE["MEASURE"], INK, BAD, BAD], dashed=(2, 3), markers=(0,))
            cap = facts.get("cap_t0") or {}
            at = facts.get("attr_t0") or {}
            body = [f"n = {n}", f"Moyenne = {_fmt_num(imr['CL'], 2)}", f"σ intra (MR̄/d2) = {_fmt_num(imr['sigma'], 2)}",
                    f"UCL / LCL = {_fmt_num(imr['UCL'], 2)} / {_fmt_num(imr['LCL'], 2)}",
                    f"Points hors contrôle : {imr['n_out']} ({'instable' if imr['n_out'] else 'stable'})"]
            if cap.get("Cpk") is not None:
                body.append(" · ".join(f"{k} = {cap[k]}" for k in ("Cp", "Cpk", "Ppk") if cap.get(k) is not None))
            if at:
                body.append(f"DPMO = {_fmt_num(at['dpmo'], 0)} · sigma = {at['sigma']}")
                if at.get("note"):
                    body.append(at["note"])
            d.card(s, MX + CW * 0.7, TOP, CW * 0.3, CH - Inches(0.1), "Lecture", body, accent=col, size=11, fill=WHITE)


# ---- ANALYZE ----------------------------------------------------------------
def _analyze(d: Deck, p, o, an):
    col = PHASE["ANALYZE"]
    res = as_df(an.get("results"))
    if not res.empty or not o["skip_empty"]:
        s = d.slide("ANALYZE", "Criblage statistique des X",
                    "Test d'hypothèse — seuil de signification α = 5 %",
                    notes="Une p-value < 0,05 signifie que l'effet observé a peu de chances d'être dû au hasard.")
        if res.empty:
            d.empty(s)
        else:
            d.table(s, res, MX, TOP, CW, max_rows=12, header_color=col)

    xa = an.get("x_analyses") or {}
    rows = []
    for x, st_ in xa.items():
        for c in st_.get("causes_racines_list", []):
            if str(c).strip():
                rows.append({"X étudié": x, "Méthode": st_.get("methode", ""), "Cause racine identifiée": c})
    if rows or not o["skip_empty"]:
        s = d.slide("ANALYZE", "Causes racines identifiées",
                    notes="Pour chaque X significatif : Ishikawa (6M) ou 5 Pourquoi, jusqu'à une cause actionnable.")
        if rows:
            d.table(s, pd.DataFrame(rows), MX, TOP, CW, max_rows=12, header_color=col, col_widths=[2, 1.2, 5])
            five = [(x, st_) for x, st_ in xa.items() if st_.get("methode") == "5 Pourquoi" and st_.get("data")]
            if five and len(rows) <= 6:
                x, st_ = five[0]
                chain = " → ".join(_tr(st_["data"].get(f"p{i}"), 60) for i in range(1, 6) if st_["data"].get(f"p{i}"))
                d.card(s, MX, TOP + Inches(3.3), CW, Inches(1.4), f"Exemple — 5 Pourquoi sur « {_tr(x, 40)} »", chain, accent=col, size=11)
        else:
            d.empty(s)

    fm = an.get("fmea_data") or {}
    if fm or not o["skip_empty"]:
        s = d.slide("ANALYZE", "AMDEC (FMEA) de l'état actuel — risques prioritaires",
                    notes="RPN = Sévérité × Occurrence × Détection. On traite en priorité les RPN les plus élevés.")
        if not fm:
            d.empty(s)
        else:
            rows = [{"Cause": cid.split("_", 1)[-1], "Mode": v.get("mode", ""), "S": v.get("S"), "O": v.get("O"),
                     "D": v.get("D"), "RPN": v.get("S", 1) * v.get("O", 1) * v.get("D", 1)} for cid, v in fm.items()]
            f = pd.DataFrame(rows).sort_values("RPN", ascending=False)
            bar_chart(s, MX, TOP, CW * 0.48, CH - Inches(0.2), f["Cause"].head(10), {"RPN": f["RPN"].head(10)},
                      colors=[col], horizontal=True, labels=True, legend=False)
            d.table(s, f, MX + CW * 0.51, TOP, CW * 0.49, max_rows=10, header_color=col, col_widths=[3, 2, .6, .6, .6, .9], max_cell=50)

    reg = an.get("regression") or {}
    if reg.get("ok"):
        s = d.slide("ANALYZE", "Modélisation : régression multiple",
                    f"R² ajusté = {100*reg['R2_ajuste']:.0f} %  ·  p du modèle {_fmt_pp(reg['p_modele'])}  ·  n = {reg['n']}",
                    notes="L'équation quantifie l'effet de chaque X : c'est elle qui dit sur quel levier agir en priorité.")
        d.card(s, MX, TOP, CW, Inches(0.9), "Équation", reg["equation"], accent=col, size=12, fill=WHITE)
        d.table(s, pd.DataFrame(reg["coefficients"]), MX, TOP + Inches(1.1), CW, max_rows=10, header_color=col)

    dec = cause_decisions(p)
    if not dec.empty or not o["skip_empty"]:
        s = d.slide("ANALYZE", "Validation des causes racines : statistique + terrain",
                    notes="Une cause n'est retenue que si la statistique ET l'observation terrain (Gemba) convergent.")
        if dec.empty:
            d.empty(s)
        else:
            d.table(s, dec, MX, TOP, CW, max_rows=12, header_color=col, col_widths=[1.6, 3.4, 1.1, 1.5, 1.8])


# ---- IMPROVE ----------------------------------------------------------------
def _improve(d: Deck, p, o, im, facts):
    col = PHASE["IMPROVE"]
    strat = as_df(im.get("strategies"))
    sel = as_df(im.get("selection_matrix"))
    if not strat.empty or not o["skip_empty"]:
        s = d.slide("IMPROVE", "Solutions par cause racine et sélection pondérée",
                    notes="Chaque solution répond à une cause validée ; la matrice pondérée objective le choix.")
        if strat.empty:
            d.empty(s)
        else:
            keep = [c for c in ["Cause racine", "Solution potentielle", "Type de solution"] if c in strat.columns]
            d.table(s, strat[keep], MX, TOP, CW * (0.55 if not sel.empty else 1), max_rows=10, header_color=col, max_cell=70)
            if not sel.empty and "Score Total" in sel.columns:
                sel = sel.sort_values("Score Total", ascending=True)
                bar_chart(s, MX + CW * 0.58, TOP, CW * 0.42, CH - Inches(0.2), sel["Solution potentielle"].astype(str),
                          {"Score pondéré": sel["Score Total"].round(2)}, colors=[col], horizontal=True, labels=True,
                          legend=False, number_format='0.00')

    be = as_df(im.get("benefit_effort_results"))
    if not be.empty or not o["skip_empty"]:
        s = d.slide("IMPROVE", "Matrice bénéfice / effort",
                    notes="Quick wins d'abord (fort bénéfice, faible effort), projets stratégiques planifiés ensuite.")
        if be.empty:
            d.empty(s)
        else:
            pts = [(r["Solution potentielle"], float(r["Score Effort"]), float(r["Score Bénéfice"])) for _, r in be.iterrows()]
            scatter_chart(s, MX, TOP, CW * 0.6, CH - Inches(0.1), pts, "Effort", "Bénéfice", col)
            keep = [c for c in ["Solution potentielle", "Quadrant", "Priorité"] if c in be.columns]
            d.table(s, be[keep], MX + CW * 0.63, TOP, CW * 0.37, max_rows=10, header_color=col, max_cell=45)

    ap = im.get("action_plan") or {}
    if ap or not o["skip_empty"]:
        s = d.slide("IMPROVE", "Plan de déploiement des solutions",
                    notes="Qui fait quoi, quand, avec quel budget. Signalez les actions en retard et les risques.")
        if not ap:
            d.empty(s)
        else:
            rows, tasks = [], []
            for sol, v in ap.items():
                stt, en = pd.to_datetime(v.get("debut"), errors="coerce"), pd.to_datetime(v.get("fin"), errors="coerce")
                rows.append({"Action": sol, "Responsable": v.get("responsable", ""),
                             "Début": stt.strftime("%d/%m/%Y") if pd.notna(stt) else "",
                             "Fin": en.strftime("%d/%m/%Y") if pd.notna(en) else "",
                             "Charge (JH)": v.get("charge", 0), "Budget (Ar)": _fmt_num(float(v.get("budget") or 0), 0)})
                if pd.notna(stt) and pd.notna(en):
                    tasks.append((_tr(sol, 35), stt.date(), en.date()))
            top_h = Inches(2.6) if tasks else CH
            d.table(s, pd.DataFrame(rows), MX, TOP, CW, max_rows=6, header_color=col, col_widths=[3.5, 1.6, 1.1, 1.1, 1, 1.3])
            if tasks:
                gantt_chart(s, MX, TOP + Inches(2.75), CW, CH - Inches(2.8), tasks, col)
            tot = sum(float(v.get("budget") or 0) for v in ap.values())
            d.text(s, W - MX - Inches(5), Inches(1.05), Inches(5), Inches(0.3),
                   f"Budget total : {_fmt_num(tot, 0)} Ar", 12, col, bold=True, align=PP_ALIGN.RIGHT)

    v0, v1 = facts.get("vsm_t0") or {}, facts.get("vsm_futur") or {}
    if (v0.get("lead_time") and v1.get("lead_time")) or not o["skip_empty"]:
        s = d.slide("IMPROVE", "Chaîne de valeur : état actuel vs état futur",
                    notes="Montrez où le temps a été gagné et quelle part de non-valeur ajoutée a été supprimée.")
        if not (v0.get("lead_time") and v1.get("lead_time")):
            d.empty(s, "Renseignez le VSM (Measure) et l'état futur (Improve, « Délai Actuel »).")
        else:
            div, unit = (60, "h") if v0["lead_time"] > 600 else (1, "min")
            bar_chart(s, MX, TOP, CW * 0.6, CH - Inches(0.1), ["État actuel (T0)", "État futur"],
                      {k: [v0[kk] / div, v1[kk] / div] for k, kk in [("VA", "va"), ("NVA", "nva"), ("BNVA", "bnva"), ("Attente", "attente")]},
                      colors=[GOOD, BAD, WARN, MUTED], stacked=True, number_format='0.0')
            gain = v0["lead_time"] - v1["lead_time"]
            body = [f"Lead time : {_fmt_duration(v0['lead_time'])} → {_fmt_duration(v1['lead_time'])}",
                    f"Gain : {_fmt_duration(gain)} ({100*gain/v0['lead_time']:.0f} %)",
                    f"PCE : {v0['pce']:.1f} % → {v1['pce']:.1f} %", f"Unité du graphique : {unit}"]
            d.card(s, MX + CW * 0.63, TOP, CW * 0.37, Inches(2.6), "Gains de flux", body, accent=col, size=13, fill=WHITE)

    doe = (im.get("doe") or {}).get("resultat") or {}
    if doe.get("ok"):
        s = d.slide("IMPROVE", "Plan d'expériences : effets des facteurs", doe.get("methode", ""),
                    notes="Les barres au-delà du seuil sont les effets significatifs ; on en déduit le réglage optimal.")
        eff = pd.DataFrame(doe["effets"]).sort_values("|Effet|")
        bar_chart(s, MX, TOP, CW * 0.55, CH - Inches(0.1), eff["Terme"], {"|Effet|": eff["|Effet|"]},
                  colors=[col], horizontal=True, labels=True, legend=False, number_format='0.00')
        lv = as_df((im.get("doe") or {}).get("niveaux"))
        body = [doe["conclusion"], f"Seuil de signification : {doe['seuil']}",
                "Réglage qui augmente Y : " + ", ".join(f"{k_} {v_}" for k_, v_ in doe["reglage_max"].items())]
        d.card(s, MX + CW * 0.58, TOP, CW * 0.42, Inches(2.4), "Lecture", body, accent=col, size=11, fill=WHITE)
        if not lv.empty:
            d.table(s, lv, MX + CW * 0.58, TOP + Inches(2.6), CW * 0.42, max_rows=4, header_color=col)

    pil = im.get("pilote") or {}
    pres = pil.get("resultat") or {}
    if pil.get("solutions") or pres.get("ok"):
        s = d.slide("IMPROVE", "Pilote : preuve à petite échelle avant généralisation",
                    f"Décision : {pil.get('decision') or 'à prendre'}",
                    notes="Le pilote prouve l'effet sur un périmètre réduit et révèle les effets de bord.")
        half = (CW - Inches(0.25)) / 2
        d.card(s, MX, TOP, half, Inches(2.6), "Ce qui a été testé",
               [pil.get("solutions") or "—", f"Périmètre : {pil.get('perimetre') or '—'}", f"Critère de succès : {pil.get('critere') or '—'}"],
               accent=col, size=12, fill=WHITE)
        d.card(s, MX, TOP + Inches(2.8), half, Inches(2.6), "Effets de bord / ajustements", pil.get("effets_bord") or "—",
               accent=WARN, size=12, fill=WHITE)
        if pres.get("ok"):
            if pres["type"] == "continu":
                bar_chart(s, MX + half + Inches(0.25), TOP, half, Inches(3.6), ["Avant", "Pilote"],
                          {"Moyenne": [pres["moyenne_avant"], pres["moyenne_apres"]]}, colors=[col], labels=True,
                          legend=False, number_format='0.0')
            else:
                bar_chart(s, MX + half + Inches(0.25), TOP, half, Inches(3.6), ["Avant", "Pilote"],
                          {"% défauts": [pres["taux_defaut_avant_%"], pres["taux_defaut_apres_%"]]}, colors=[col],
                          labels=True, legend=False, number_format='0.0')
            d.card(s, MX + half + Inches(0.25), TOP + Inches(3.8), half, Inches(1.6), "Verdict statistique",
                   pres["conclusion"], accent=GOOD if pres["significatif"] else BAD, size=11, fill=WHITE)

    ff = as_df(im.get("future_fmea"))
    if (not ff.empty and "RPN actuel" in ff.columns) or not o["skip_empty"]:
        s = d.slide("IMPROVE", "AMDEC future : réduction du risque",
                    notes="Les solutions réduisent-elles l'occurrence et améliorent-elles la détection ?")
        if ff.empty or "RPN actuel" not in ff.columns:
            d.empty(s)
        else:
            lab = ff.columns[0]
            bar_chart(s, MX, TOP, CW * 0.55, CH - Inches(0.1), ff[lab].astype(str),
                      {"RPN actuel": ff["RPN actuel"], "RPN futur": ff["RPN futur"]}, colors=[BAD, GOOD], labels=True)
            keep = [c for c in [lab, "RPN actuel", "RPN futur", "Pourcentage de réduction", "Efficacité"] if c in ff.columns]
            t = ff[keep].copy()
            if "Pourcentage de réduction" in t.columns:
                t["Pourcentage de réduction"] = t["Pourcentage de réduction"].map(lambda v: f"{float(v):.0f} %")
            d.table(s, t, MX + CW * 0.58, TOP, CW * 0.42, max_rows=8, header_color=col, max_cell=45)


# ---- CONTROL ----------------------------------------------------------------
def _control(d: Deck, p, o, facts, closure):
    col = PHASE["CONTROL"]
    ba = facts.get("before_after") or {}
    y = facts.get("y_col") or "Y"
    t0v = S.to_numeric(pd.Series(facts.get("y_t0", []))).dropna().tolist()
    cv = [(w, v) for w, v in facts.get("y_ctrl", []) if pd.notna(S.to_numeric(pd.Series([v])).iloc[0])]
    if (ba.get("ok") or not o["skip_empty"]):
        s = d.slide("CONTROL", "Résultats : la preuve avant / après",
                    f"Y = {_tr(y, 60)} · objectif : {facts.get('direction', 'réduire')}",
                    notes="C'est la diapositive centrale : le changement est-il réel (p-value) et significatif pour le métier ?")
        if not ba.get("ok"):
            d.empty(s, "Ajoutez au moins une vague de contrôle (T1) avec la même variable Y que la baseline T0.")
        else:
            if ba["type"] == "continu" and t0v and cv:
                vals = t0v + [float(S.to_numeric(pd.Series([v])).iloc[0]) for _, v in cv]
                stages = ["T0"] * len(t0v) + [w for w, _ in cv]
                series = {y: vals}
                for stg in dict.fromkeys(stages):
                    seg = [v for v, st_ in zip(vals, stages) if st_ == stg]
                    imr = S.imr_chart(seg)
                    if imr.get("ok"):
                        series[f"CL {stg}"] = [imr["CL"] if st_ == stg else None for st_ in stages]
                        series[f"UCL {stg}"] = [imr["UCL"] if st_ == stg else None for st_ in stages]
                ncl = len(series) - 1
                colors = [col] + [INK if "CL " in k and "UCL" not in k else BAD for k in list(series)[1:]]
                line_chart(s, MX, TOP, CW * 0.64, CH - Inches(0.45), list(range(1, len(vals) + 1)), series,
                           colors=colors, dashed=tuple(i for i, k in enumerate(series) if k.startswith("UCL")),
                           markers=(0,), legend=False)
                d.text(s, MX, TOP + CH - Inches(0.35), CW * 0.64, Inches(0.3),
                       "Carte I-MR par étapes : T0 puis vagues de contrôle (limites recalculées par étape)", 9, MUTED)
                body = [f"Test : {ba['test']} — p {_fmt_pp(ba['p_value'])}",
                        f"Moyenne : {_fmt_num(ba['moyenne_avant'], 2)} → {_fmt_num(ba['moyenne_apres'], 2)} ({ba['delta_%']:+.1f} %)" if ba.get("delta_%") is not None else "",
                        f"Écart-type : {_fmt_num(ba['sigma_avant'], 2)} → {_fmt_num(ba['sigma_apres'], 2)}",
                        f"n : {ba['n_avant']} → {ba['n_apres']}"]
            else:
                bar_chart(s, MX, TOP, CW * 0.6, CH - Inches(0.1), ["Avant (T0)", "Après"],
                          {"Taux de défauts (%)": [ba.get("taux_defaut_avant_%"), ba.get("taux_defaut_apres_%")]},
                          colors=[col], labels=True, legend=False, number_format='0.0')
                body = [f"Test : {ba['test']} — p {_fmt_pp(ba['p_value'])}",
                        f"Défauts : {ba['taux_defaut_avant_%']} % → {ba['taux_defaut_apres_%']} %",
                        f"n : {ba['n_avant']} → {ba['n_apres']}"]
            verdict_col = GOOD if ba["significatif"] else BAD
            d.card(s, MX + CW * 0.66, TOP, CW * 0.34, Inches(1.5), "Verdict",
                   "Amélioration PROUVÉE" if ba["significatif"] else "Amélioration NON prouvée", accent=verdict_col, size=16, fill=WHITE)
            d.card(s, MX + CW * 0.66, TOP + Inches(1.65), CW * 0.34, CH - Inches(1.75), "Statistiques",
                   [b for b in body if b] + [ba["conclusion"]], accent=col, size=11, fill=WHITE)

    waves = pd.DataFrame(facts.get("waves") or [])
    if len(waves) > 1 or not o["skip_empty"]:
        s = d.slide("CONTROL", "Capabilité : référence T0 vs vagues de contrôle",
                    notes="La performance tient-elle dans la durée, vague après vague ?")
        if len(waves) <= 1:
            d.empty(s)
        else:
            if waves["Sigma"].notna().any():
                bar_chart(s, MX, TOP, CW * 0.5, CH - Inches(0.1), waves["Période"], {"Niveau sigma": waves["Sigma"]},
                          colors=[col], labels=True, legend=False, number_format='0.00')
            elif waves["Moyenne"].notna().any():
                bar_chart(s, MX, TOP, CW * 0.5, CH - Inches(0.1), waves["Période"], {"Moyenne": waves["Moyenne"]},
                          colors=[col], labels=True, legend=False, number_format='0.0')
            d.table(s, waves, MX + CW * 0.53, TOP, CW * 0.47, max_rows=10, header_color=col)

    cp = as_df(closure.get("control_plan"))
    if not cp.empty or not o["skip_empty"]:
        s = d.slide("CONTROL", "Plan de contrôle — pérennisation",
                    notes="Qui surveille quoi, à quelle fréquence, et que fait-on en cas de dérive (plan de réaction) ?")
        if cp.empty:
            d.empty(s, "Renseignez le plan de contrôle dans l'onglet Résultats & Soutenance.")
        else:
            d.table(s, cp, MX, TOP, CW, max_rows=10, header_color=col, max_cell=70)

    chg = p.get("changement") or {}
    adk = as_df(chg.get("adkar"))
    com = as_df(chg.get("communication"))
    if not com.empty:
        com = com[com.astype(str).apply(lambda r: "".join(r).strip() != "", axis=1)]
    if not adk.empty or not com.empty:
        s = d.slide("CONTROL", "Conduite du changement : adhésion et communication",
                    notes="Où en sont les personnes (ADKAR) et comment le changement a été accompagné.")
        y_ = TOP
        if not adk.empty:
            d.text(s, MX, y_, CW, Inches(0.3), "Diagnostic ADKAR (1 = absent, 5 = acquis)", 12, col, bold=True)
            d.table(s, adk, MX, y_ + Inches(0.35), CW, max_rows=5, header_color=col)
            y_ += Inches(0.35) + Inches(0.36) * (min(len(adk), 5) + 1) + Inches(0.3)
        if not com.empty:
            d.text(s, MX, y_, CW, Inches(0.3), "Plan de communication", 12, col, bold=True)
            d.table(s, com, MX, y_ + Inches(0.35), CW, max_rows=5, header_color=col, max_cell=60)

    gains = as_df(closure.get("gains"))
    if not gains.empty or not o["skip_empty"]:
        s = d.slide("CONTROL", "Bénéfices financiers et opérationnels",
                    notes="Distinguez gains 'hard' (impact compte de résultat) et 'soft' ; indiquez qui les a validés.")
        if gains.empty:
            d.empty(s)
        else:
            mcol = next((c for c in gains.columns if "montant" in c.lower()), None)
            tcol = next((c for c in gains.columns if c.lower().startswith("type")), None)
            if mcol and tcol:
                agg = gains.groupby(tcol)[mcol].apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                bar_chart(s, MX, TOP, CW * 0.42, CH - Inches(0.1), list(agg.index), {"Ar / an": list(agg.values)},
                          colors=[col], labels=True, legend=False, number_format='#,##0')
            show = gains.copy()
            if mcol:
                show[mcol] = show[mcol].map(lambda v: _fmt_num(float(v), 0) if str(v).strip() not in ("", "nan", "None") else "")
            d.table(s, show, MX + CW * 0.45, TOP, CW * 0.55, max_rows=9, header_color=col, max_cell=55)
            if facts.get("gains_total"):
                d.text(s, W - MX - Inches(6), Inches(1.05), Inches(6), Inches(0.3),
                       f"Total : {_fmt_num(facts['gains_total'], 0)} Ar / an", 12, col, bold=True, align=PP_ALIGN.RIGHT)

    les, nxt = closure.get("lecons") or "", closure.get("next_steps") or ""
    if les or nxt or not o["skip_empty"]:
        s = d.slide("CONTROL", "Leçons apprises et prochaines étapes",
                    notes="Ce que vous referiez / ne referiez pas, et les opportunités de duplication (Yokoten).")
        half = (CW - Inches(0.25)) / 2
        d.card(s, MX, TOP, half, CH - Inches(0.1), "Leçons apprises",
               [l for l in les.split("\n") if l.strip()] or ["—"], accent=col, size=12, fill=WHITE)
        d.card(s, MX + half + Inches(0.25), TOP, half, CH - Inches(0.1), "Prochaines étapes / duplication",
               [l for l in nxt.split("\n") if l.strip()] or ["—"], accent=col, size=12, fill=WHITE)

    sign = as_df(closure.get("signoff"))
    s = d.slide("CONTROL", "Clôture et transfert au propriétaire du processus",
                notes="Demandez formellement la validation de clôture et le transfert de responsabilité.")
    if sign.empty:
        sign = pd.DataFrame([{"Rôle": r, "Nom": "", "Décision": "", "Date": ""} for r in
                             ["Sponsor", "Propriétaire du processus", "Contrôle de gestion", "Master Black Belt"]])
    d.table(s, sign, MX, TOP, CW, max_rows=8, header_color=col)
    checks = [("Amélioration prouvée statistiquement", bool(ba.get("significatif"))),
              ("Plan de contrôle en place", not as_df(closure.get("control_plan")).empty),
              ("Gains chiffrés", bool(facts.get("gains_total"))),
              ("Système de mesure validé", bool(p.get("msa_is_validated_status")))]
    y0 = TOP + Inches(0.36) * (len(sign) + 1) + Inches(0.4)
    for i, (lab, ok) in enumerate(checks):
        d.text(s, MX, y0 + i * Inches(0.38), CW, Inches(0.35), f"{'✔' if ok else '✘'}  {lab}", 13, GOOD if ok else BAD, bold=True)
