"""
lss_agents.py — Équipe d'agents IA d'un Master Black Belt
=========================================================
Chaque agent est un expert d'un domaine, qui reçoit UNIQUEMENT le contexte utile
à son métier (calculé à partir des données réelles du projet) et un rôle précis.
Un orchestrateur (le Master Black Belt) oriente chaque question vers le bon expert.

Deux couches :
  1. Contrôles déterministes (fonctionnent sans IA, jamais d'invention) :
       - maturity(p)  : grille de jalons par phase, score de maturité
       - pitfalls(p)  : garde-fous méthodologiques et statistiques
       - data_profile : profil statistique des données collectées
  2. Agents LLM (Groq / Gemini gratuits) qui raisonnent sur ces faits.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pandas as pd

import lss_ai as AI
import lss_report as R
import lss_stats as S

PHASES = ["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"]


# ===========================================================================
# 1. Contrôles déterministes
# ===========================================================================
def _rows(obj) -> list[dict]:
    d = R.as_df(obj)
    if d.empty:
        return []
    return [r for r in d.to_dict("records") if any(str(v).strip() not in ("", "nan", "None", "0") for v in r.values())]


SOLUTION_WORDS = ["manque de", "absence de", "il faut", "mettre en place", "à cause", "parce que", "solution",
                  "insuffisance de", "pas assez de", "devrait", "faute de", "en raison de"]


def problem_quality(text: str) -> list[str]:
    """Défauts classiques d'un énoncé de problème."""
    t = (text or "").lower()
    issues = []
    if len(t) < 80:
        issues.append("Énoncé trop court : précisez quoi, où, quand, combien et l'impact.")
    if not re.search(r"\d", t):
        issues.append("Aucun chiffre : un problème Black Belt se quantifie (niveau actuel, écart à la cible, coût).")
    found = [w for w in SOLUTION_WORDS if w in t]
    if found:
        issues.append(f"L'énoncé contient une cause ou une solution présupposée ({', '.join(found)}) : "
                      "décrivez l'effet observé, pas son explication.")
    if not re.search(r"(depuis|entre|en 20\d\d|mois|semaine|trimestre|janvier|février|mars|avril|mai|juin|juillet|"
                     r"août|septembre|octobre|novembre|décembre)", t):
        issues.append("Pas de période d'observation : indiquez sur quelle période le problème a été mesuré.")
    return issues


def maturity(p: dict, facts: dict | None = None) -> dict:
    """Grille de jalons : {phase: [(critère, ok, détail)], ..., 'scores': {...}, 'global': %}."""
    facts = facts if facts is not None else R.compute_facts(p)
    dm = p.get("dmaic") or {}
    an, im = dm.get("analyze") or {}, dm.get("improve") or {}
    ch, rc, chg = p.get("charte") or {}, p.get("results_closure") or {}, p.get("changement") or {}
    msa = p.get("msa_etudes") or {}
    grr, kap = rc.get("gage_rr") or {}, rc.get("kappa") or {}
    pq = problem_quality(p.get("problem", ""))
    sipoc = [r for r in _rows(p.get("sipoc_data")) if str(r.get("Process", "")).strip()]
    team = [r for r in _rows(p.get("team_data")) if str(r.get("Nom", "")).strip()]
    gantt = _rows(p.get("gantt_data"))
    stk = _rows(p.get("stakeholders"))
    imr = facts.get("imr_t0") or {}
    res = an.get("results") or []
    sig = [r for r in res if _num(r.get("P-value")) is not None and _num(r.get("P-value")) < 0.05]
    causes = [c for v in (an.get("x_analyses") or {}).values() for c in v.get("causes_racines_list", []) if str(c).strip()]
    logs = [l for v in (an.get("gemba_observations") or {}).values() if isinstance(v, dict) for l in v.get("logs", [])]
    ap = im.get("action_plan") or {}
    pil = (im.get("pilote") or {}).get("resultat") or {}
    ba = facts.get("before_after") or {}
    cp = [r for r in _rows(rc.get("control_plan")) if str(r.get("Que contrôler ?", "")).strip()]
    gains = facts.get("gains_total") or 0
    signed = [r for r in _rows(rc.get("signoff")) if str(r.get("Décision", "")).startswith("Validé")]

    g: dict = {
        "DEFINE": [
            ("Énoncé du problème factuel et chiffré", not pq, " / ".join(pq) if pq else "OK"),
            ("CTQ (Y) défini", bool(p.get("selected_ctq")), p.get("selected_ctq") or "à choisir"),
            ("Objectif SMART (valeur actuelle, cible, échéance)", bool(ch.get("cible") and ch.get("valeur_actuelle") and ch.get("echeance")), ch.get("objectif_smart", "")),
            ("Périmètre IN / OUT", bool(ch.get("in_scope") and ch.get("out_scope")), ""),
            ("Business case (COPQ chiffré)", float(ch.get("copq_total") or 0) > 0, R._fmt_num(float(ch.get("copq_total") or 0), 0) + " Ar"),
            ("Équipe d'au moins 3 personnes nommées", len(team) >= 3, f"{len(team)} personne(s)"),
            ("SIPOC d'au moins 3 étapes", len(sipoc) >= 3, f"{len(sipoc)} étape(s)"),
            ("Voix du client analysée", bool(p.get("saved_voc_results")), ""),
            ("Parties prenantes analysées", len(stk) >= 2, f"{len(stk)} acteur(s)"),
            ("Planning des jalons", len(gantt) >= 3, f"{len(gantt)} jalon(s)"),
        ],
        "MEASURE": [
            ("X candidats identifiés (≥ 2)", len(_rows(p.get("measure_x_table"))) >= 2, ""),
            ("Cartographie VSM chiffrée", (facts.get("vsm_t0") or {}).get("lead_time", 0) > 0, facts.get("vsm", "")),
            ("Plan de collecte avec définitions opérationnelles", len(_rows(p.get("master_dcp_table"))) >= 1, ""),
            ("Système de mesure validé (Gage R&R ≤ 30 % ou Kappa ≥ 0,7)",
             bool(p.get("msa_is_validated_status")) or (grr.get("ok") and grr.get("%GRR", 100) <= 30) or (kap.get("ok") and kap.get("kappa", 0) >= 0.7),
             f"%GRR {grr.get('%GRR')}" if grr.get("ok") else ""),
            ("Données T0 suffisantes (n ≥ 30)", facts.get("n_t0", 0) >= 30, f"n = {facts.get('n_t0', 0)}"),
            ("Baseline stable (carte I-MR)", bool(imr.get("ok") and imr.get("stable")),
             f"{imr.get('n_out', '?')} point(s) hors contrôle" if imr.get("ok") else "non calculée"),
            ("Capabilité initiale (spécification définie)", bool(facts.get("attr_t0") or (facts.get("cap_t0") or {}).get("Cpk") is not None), ""),
        ],
        "ANALYZE": [
            ("X testés statistiquement", bool(res), f"{len(res)} test(s)"),
            ("Au moins un X significatif (p < 0,05)", bool(sig), ", ".join(str(r.get("Variable X")) for r in sig)),
            ("Causes racines identifiées (Ishikawa / 5 Pourquoi)", bool(causes), f"{len(causes)} cause(s)"),
            ("Causes vérifiées sur le terrain (Gemba)", len(logs) >= 5, f"{len(logs)} observation(s)"),
            ("AMDEC des causes", bool(an.get("fmea_data")), ""),
            ("Effet des X quantifié (régression ou DOE)", bool((an.get("regression") or {}).get("ok") or ((im.get("doe") or {}).get("resultat") or {}).get("ok")), ""),
        ],
        "IMPROVE": [
            ("Solutions reliées aux causes validées", bool(im.get("strategies")), ""),
            ("Sélection objectivée (matrice pondérée)", bool(im.get("selection_matrix")), ""),
            ("Priorisation bénéfice / effort", bool(im.get("benefit_effort_results")), ""),
            ("Plan d'action avec responsables et dates", bool(ap) and all(v.get("responsable") for v in ap.values()), f"{len(ap)} action(s)"),
            ("Pilote réalisé et concluant", bool(pil.get("ok") and pil.get("significatif")), pil.get("conclusion", "")[:90]),
            ("AMDEC future (risques résiduels)", bool(im.get("future_fmea")), ""),
            ("Plan de conduite du changement", bool(_rows(chg.get("adkar")) or _rows(chg.get("communication"))), ""),
        ],
        "CONTROL": [
            ("Données après amélioration (n ≥ 20)", facts.get("n_ctrl", 0) >= 20, f"n = {facts.get('n_ctrl', 0)}"),
            ("Amélioration prouvée statistiquement", bool(ba.get("significatif")), ba.get("conclusion", "")[:90]),
            ("Plan de contrôle (quoi, fréquence, réaction)", bool(cp), f"{len(cp)} point(s) de contrôle"),
            ("Gains financiers chiffrés", gains > 0, R._fmt_num(gains, 0) + " Ar/an" if gains else ""),
            ("Leçons apprises formalisées", bool(rc.get("lecons")), ""),
            ("Clôture validée par le sponsor", bool(signed), f"{len(signed)} validation(s)"),
        ],
    }
    scores = {ph: round(100 * sum(1 for _, ok, _ in items if ok) / len(items)) for ph, items in g.items()}
    g["scores"] = scores
    g["global"] = round(sum(scores.values()) / len(scores))
    return g


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pitfalls(p: dict, facts: dict | None = None) -> list[tuple[str, str, str]]:
    """Garde-fous : liste de (gravité, phase, message). Gravité : 🔴 bloquant, 🟠 attention, 🔵 conseil."""
    facts = facts if facts is not None else R.compute_facts(p)
    dm = p.get("dmaic") or {}
    an = dm.get("analyze") or {}
    rc = p.get("results_closure") or {}
    out = []
    grr = rc.get("gage_rr") or {}
    msa_ok = bool(p.get("msa_is_validated_status")) or (grr.get("ok") and grr.get("%GRR", 100) <= 30)
    res = an.get("results") or []
    if res and not msa_ok:
        out.append(("🔴", "MEASURE", "Des X ont été testés alors que le système de mesure n'est pas validé : "
                                     "les conclusions statistiques ne sont pas défendables."))
    if grr.get("ok") and grr.get("%GRR", 0) > 30:
        out.append(("🔴", "MEASURE", f"%GRR = {grr['%GRR']} % (> 30 %) : la mesure bruite plus que le processus."))
    if 0 < facts.get("n_t0", 0) < 30:
        out.append(("🟠", "MEASURE", f"Baseline sur {facts['n_t0']} observations : puissance statistique faible, "
                                     "intervalles de confiance larges."))
    imr = facts.get("imr_t0") or {}
    if imr.get("ok") and not imr.get("stable"):
        out.append(("🟠", "MEASURE", f"Baseline instable ({imr['n_out']} points signalés) : la capabilité (Cpk, sigma) "
                                     "n'est pas interprétable tant que les causes spéciales ne sont pas expliquées."))
    k = len(res)
    if k > 5:
        out.append(("🟠", "ANALYZE", f"{k} X testés au seuil de 5 % : environ {k*0.05:.1f} faux positif(s) attendu(s) "
                                     f"par hasard. Exigez p < {0.05/k:.4f} (Bonferroni) ou confirmez par un DOE."))
    corr = [r for r in res if "orrélation" in str(r.get("Test utilisé", "")) and str(r.get("Significatif (α=5%)", "")) == "Oui"]
    if corr:
        out.append(("🔵", "ANALYZE", "Corrélation ≠ causalité : confirmez " + ", ".join(str(r["Variable X"]) for r in corr)
                    + " par l'observation terrain ou un plan d'expériences."))
    weak = [r for r in res if str(r.get("Significatif (α=5%)", "")) == "Oui" and str(r.get("Taille d'effet", "")).find("Faible") >= 0]
    if weak:
        out.append(("🔵", "ANALYZE", "Effet significatif mais faible pour " + ", ".join(str(r["Variable X"]) for r in weak)
                    + " : statistiquement réel, pratiquement peu utile."))
    ba = facts.get("before_after") or {}
    if ba.get("ok"):
        if min(ba.get("n_avant", 0), ba.get("n_apres", 0)) < 20:
            out.append(("🟠", "CONTROL", "Moins de 20 observations dans un des groupes avant/après : prolongez la collecte."))
        if not ba.get("significatif"):
            out.append(("🔴", "CONTROL", "L'amélioration n'est pas prouvée statistiquement : ne pas clôturer en l'état."))
    gains = R.as_df(rc.get("gains"))
    if not gains.empty and "Validé par" in gains.columns:
        if gains["Validé par"].astype(str).str.strip().isin(["", "nan", "None"]).any():
            out.append(("🟠", "CONTROL", "Des gains n'ont pas de validateur : faites-les valider par le contrôle de gestion."))
    if facts.get("attr_t0", {}).get("note"):
        out.append(("🔵", "MEASURE", facts["attr_t0"]["note"]))
    pq = problem_quality(p.get("problem", ""))
    if pq and p.get("problem"):
        out.append(("🟠", "DEFINE", pq[0]))
    return out


def data_profile(p: dict, max_cols: int = 12) -> pd.DataFrame:
    """Profil des données T0 : type, n, manquants, moyenne, écart-type, normalité."""
    df = R.as_df(p.get("dc_saved_df_json"))
    rows = []
    for c in [c for c in df.columns if c not in ("ID observation", "Date de modification")][:max_cols]:
        s = df[c]
        n_ok = int(s.astype(str).str.strip().replace({"": None, "nan": None, "None": None}).dropna().shape[0])
        if S.is_numeric(s):
            x = S.to_numeric(s).dropna()
            norm = S._is_normal(x)
            rows.append({"Variable": c, "Type": "Continue", "n": n_ok, "Manquants": len(s) - n_ok,
                         "Moyenne": round(float(x.mean()), 3) if len(x) else None,
                         "Écart-type": round(float(x.std()), 3) if len(x) > 1 else None,
                         "Normalité (Shapiro)": "Oui" if norm else "Non"})
        else:
            vc = s.astype(str).value_counts()
            rows.append({"Variable": c, "Type": "Attributaire", "n": n_ok, "Manquants": len(s) - n_ok,
                         "Moyenne": None, "Écart-type": None,
                         "Normalité (Shapiro)": f"{len(vc)} modalités — top : {vc.index[0] if len(vc) else '—'}"})
    return pd.DataFrame(rows)


# ===========================================================================
# 2. Agents
# ===========================================================================
@dataclass
class Agent:
    key: str
    name: str
    icon: str
    phase: str
    mission: str
    system: str
    quick: list = field(default_factory=list)   # (libellé, consigne)


BASE = ("Tu es {name}, membre de l'équipe d'un Master Black Belt Lean Six Sigma francophone qui conduit des projets "
        "d'amélioration de grande envergure. Ta spécialité : {mission}\n"
        "Règles impératives :\n"
        "- Tu raisonnes UNIQUEMENT à partir du CONTEXTE fourni ; tu signales explicitement toute donnée manquante.\n"
        "- Tu n'inventes jamais un chiffre, un résultat de test ou un nom.\n"
        "- Tu distingues : Faits (données) / Interprétation / Recommandation.\n"
        "- Tu es exigeant comme un MBB en revue : tu nommes les erreurs méthodologiques sans détour.\n"
        "- Tu termines par 'Prochaines actions' : 3 actions maximum, concrètes (qui / quoi / livrable).\n"
        "- Réponses en français, structurées, concises (≤ 350 mots sauf demande contraire).")

AGENTS: dict[str, Agent] = {}


def _add(key, name, icon, phase, mission, quick):
    AGENTS[key] = Agent(key, name, icon, phase, mission, BASE.format(name=name, mission=mission), quick)


_add("cadrage", "l'Agent Cadrage", "🎯", "DEFINE",
     "cadrer le projet : énoncé du problème, CTQ, arbre CTQ, objectif SMART, périmètre, business case, choix DMAIC vs Kaizen.",
     [("Critiquer l'énoncé du problème", "Critique l'énoncé du problème comme en revue de jalon et propose une réécriture factuelle (quoi, où, quand, combien, impact) sans cause ni solution."),
      ("Construire l'arbre CTQ", "Construis l'arbre CTQ : besoin client → drivers → CTQ mesurables (définition opérationnelle, unité, spécification)."),
      ("Vérifier le business case", "Vérifie la solidité du business case (COPQ, gain visé) et liste les hypothèses à faire valider par la finance."),
      ("DMAIC, Kaizen ou juste-faire ?", "Ce sujet justifie-t-il un DMAIC complet, un Kaizen ou un juste-faire ? Argumente.")])
_add("stats", "l'Agent Statisticien", "📐", "MEASURE",
     "la statistique appliquée Six Sigma : MSA, stabilité, capabilité, choix et conditions des tests d'hypothèse, puissance, régression, plans d'expériences.",
     [("Interpréter mes résultats statistiques", "Interprète l'ensemble des résultats statistiques disponibles, en langage clair pour un comité, et signale les limites."),
      ("Quel test utiliser ?", "Pour chaque X candidat, indique le test adapté selon le type de X et de Y, les conditions à vérifier et la taille d'échantillon nécessaire."),
      ("Ma mesure est-elle fiable ?", "Évalue la fiabilité du système de mesure (MSA, définitions opérationnelles) et ce qu'il faut faire avant de conclure."),
      ("Concevoir un plan d'expériences", "Propose un plan d'expériences adapté (facteurs, niveaux, nombre d'essais, répliques, randomisation) pour confirmer les causes.")])
_add("causes", "l'Agent Causes racines", "🔍", "ANALYZE",
     "l'analyse des causes : Ishikawa 6M, 5 Pourquoi, analyse de flux et de gaspillages, validation des causes par les données et le terrain.",
     [("Générer un Ishikawa", "À partir des données du projet (VOC, VSM, X, résultats), propose un Ishikawa 6M d'hypothèses de causes, en marquant celles déjà étayées par des données."),
      ("Challenger mes causes racines", "Pour chaque cause racine déclarée, dis si elle est prouvée, plausible ou non démontrée, et quelle preuve manque."),
      ("Où sont les gaspillages ?", "Analyse la VSM : où sont les gaspillages majeurs (8 Muda), le goulot, et quel est le potentiel de réduction du lead time ?"),
      ("Préparer le Gemba", "Prépare un plan d'observation terrain (Gemba) pour valider les causes : quoi observer, où, combien d'observations, grille.")])
_add("solutions", "l'Agent Solutions Lean", "🛠️", "IMPROVE",
     "la conception de solutions : Lean (flux, standard, 5S, SMED, poka-yoke, Kanban, juste-à-temps), solutions Six Sigma, priorisation, pilote, AMDEC future.",
     [("Proposer des solutions par cause", "Pour chaque cause validée, propose 2 à 3 solutions de nature différente (élimination, poka-yoke, standard, automatisation) avec l'outil Lean correspondant."),
      ("Concevoir le pilote", "Conçois le pilote : périmètre, durée, indicateurs, taille d'échantillon, critère GO/NO GO, risques."),
      ("Évaluer mon plan d'action", "Évalue le plan d'action : cohérence avec les causes, charge, dépendances, risques de dérapage."),
      ("Concevoir l'état futur", "Décris l'état futur cible du processus (VSM futur) et le gain de lead time attendu.")])
_add("changement", "l'Agent Conduite du changement", "🤝", "IMPROVE",
     "la conduite du changement : ADKAR, Kotter, cartographie des acteurs, communication, gestion des résistances, ancrage culturel.",
     [("Plan d'action ADKAR", "À partir du diagnostic ADKAR et des parties prenantes, propose les interventions prioritaires par groupe."),
      ("Rédiger les messages clés", "Rédige les messages de communication clés par public (direction, managers, opérationnels), adaptés à leur niveau d'adhésion."),
      ("Traiter les résistances", "Pour chaque résistance identifiée, propose une réponse et l'acteur le mieux placé pour la porter."),
      ("Ancrer le changement", "Comment ancrer durablement le changement (rituels, management visuel, indicateurs, reconnaissance) ?")])
_add("revue", "le Master Black Belt (revue de jalon)", "🧠", "TOUTES",
     "les revues de jalon (tollgates) : évaluer la maturité du projet, décider GO / GO sous conditions / NO GO, coacher le Black Belt.",
     [("Revue de jalon complète", "Réalise la revue de jalon de la phase en cours : points solides, lacunes bloquantes, erreurs méthodologiques, verdict GO / GO sous conditions / NO GO."),
      ("Quels sont mes 3 plus gros risques ?", "Quels sont les 3 plus gros risques d'échec de ce projet aujourd'hui, et comment les réduire ?"),
      ("Plan des 2 prochaines semaines", "Propose mon plan de travail des 2 prochaines semaines, priorisé."),
      ("Ce projet est-il prêt à clôturer ?", "Le projet est-il prêt à être clôturé ? Liste précisément ce qui manque.")])
_add("soutenance", "l'Agent Soutenance", "📣", "CONTROL",
     "la préparation des comités de direction : storytelling DMAIC, messages clés chiffrés, anticipation des questions difficiles.",
     [("Questions pièges du comité", "Liste les 8 questions les plus difficiles qu'un comité de direction posera sur ce projet, avec pour chacune la réponse appuyée sur les données (ou la donnée manquante)."),
      ("Fil rouge de la soutenance", "Propose le fil rouge (storytelling) de la soutenance en 7 temps, avec le message clé de chaque temps."),
      ("Pitch de 2 minutes", "Rédige le pitch oral de 2 minutes pour présenter ce projet à la direction générale."),
      ("Note de synthèse au sponsor", "Rédige une note de synthèse d'une page au sponsor (contexte, résultats, gains, décisions attendues).")])


# ---------------------------------------------------------------------------
# Contexte spécialisé par agent
# ---------------------------------------------------------------------------
def _j(obj, n=2500) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)[:n]


def context_for(agent_key: str, p: dict, facts: dict | None = None) -> str:
    facts = facts if facts is not None else R.compute_facts(p)
    dm = p.get("dmaic") or {}
    an, im = dm.get("analyze") or {}, dm.get("improve") or {}
    mat = maturity(p, facts)
    warn = pitfalls(p, facts)
    head = [f"PROJET : {p.get('name') or p.get('nom')} — phase déclarée : {p.get('status', '?')}",
            f"Maturité par phase : {mat['scores']} (global {mat['global']} %)"]
    if warn:
        head.append("Alertes automatiques : " + " | ".join(f"{g} {ph} : {m}" for g, ph, m in warn))
    blocks = []
    if agent_key == "cadrage":
        blocks += [f"Problème : {p.get('problem')}", f"Défauts détectés dans l'énoncé : {problem_quality(p.get('problem', ''))}",
                   f"CTQ : {p.get('selected_ctq')}", f"Bénéfices : {p.get('benefices_saisie')}",
                   f"Charte : {_j(p.get('charte'))}", f"Opportunité : {_j(p.get('opportunite'))}",
                   f"SIPOC : {_j(_rows(p.get('sipoc_data')))}", f"VOC : {_j(p.get('saved_voc_results'))}"]
    elif agent_key == "stats":
        prof = data_profile(p)
        blocks += [f"Y étudié : {facts.get('y_col')} — objectif : {facts.get('direction')} — spécification : {_j(facts.get('spec'))}",
                   "Profil des données T0 :\n" + (prof.to_string(index=False) if not prof.empty else "aucune donnée"),
                   f"Baseline : {facts.get('baseline')}", f"Capabilité T0 : {_j(facts.get('cap_t0'))} / {_j(facts.get('attr_t0'))}",
                   f"MSA : Gage R&R {_j((p.get('results_closure') or {}).get('gage_rr'))} ; Kappa {_j((p.get('results_closure') or {}).get('kappa'))} ; validée={p.get('msa_is_validated_status')}",
                   f"Tests X→Y : {_j(an.get('results'))}", f"Régression : {_j(an.get('regression'), 1500)}",
                   f"DOE : {_j((im.get('doe') or {}).get('resultat'), 1500)}", f"Avant/après : {_j(facts.get('before_after'))}",
                   f"Vagues : {_j(facts.get('waves'))}"]
    elif agent_key == "causes":
        v0 = facts.get("vsm_t0") or {}
        blocks += [f"Problème : {p.get('problem')}", f"VOC : {_j(p.get('saved_voc_results'), 1200)}",
                   f"X candidats : {_j(_rows(p.get('measure_x_table')), 1500)}",
                   f"VSM par étape (minutes) : {_j(v0.get('steps'), 1500)} ; lead time {v0.get('lead_time')} ; PCE {v0.get('pce')}",
                   f"Tests X→Y : {_j(an.get('results'))}", f"Analyses de causes : {_j(an.get('x_analyses'), 2500)}",
                   f"Validation causes : {R.cause_decisions(p).to_dict('records')}", f"AMDEC : {_j(an.get('fmea_data'), 1500)}"]
    elif agent_key == "solutions":
        blocks += [f"Causes validées : {R.cause_decisions(p).to_dict('records')}",
                   f"Causes déclarées : {_j([c for v in (an.get('x_analyses') or {}).values() for c in v.get('causes_racines_list', [])])}",
                   f"Solutions : {_j(im.get('strategies'))}", f"Sélection : {_j(im.get('selection_matrix'))}",
                   f"Bénéfice/effort : {_j(im.get('benefit_effort_results'))}", f"Plan d'action : {_j(im.get('action_plan'))}",
                   f"Pilote : {_j(im.get('pilote'))}", f"VSM T0 : {_j((facts.get('vsm_t0') or {}).get('steps'), 1200)}",
                   f"AMDEC future : {_j(im.get('future_fmea'))}"]
    elif agent_key == "changement":
        blocks += [f"Parties prenantes : {_j(_rows(p.get('stakeholders')))}", f"Équipe : {_j(_rows(p.get('team_data')))}",
                   f"Changement (ADKAR, communication, RACI, résistances) : {_j(p.get('changement'), 3000)}",
                   f"Solutions déployées : {_j(im.get('strategies'), 1200)}"]
    elif agent_key == "revue":
        for ph in PHASES:
            blocks.append(f"Jalon {ph} ({mat['scores'][ph]} %) : " +
                          "; ".join(f"{'✔' if ok else '✘'} {c}{(' — ' + str(d)) if d and d != 'OK' else ''}" for c, ok, d in mat[ph]))
        blocks.append(AI.project_digest(p, facts, max_chars=4000))
    elif agent_key == "soutenance":
        blocks += [AI.project_digest(p, facts, max_chars=5000), f"Faits chiffrés : {_j({k: facts.get(k) for k in ('baseline', 'vsm', 'sigma_avant', 'sigma_apres', 'gains', 'waves')})}",
                   f"Preuve avant/après : {_j(facts.get('before_after'))}", f"Charte : {_j(p.get('charte'), 1200)}"]
    return "\n".join(head + [""] + [str(b) for b in blocks])[:11000]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
ROUTES = [
    ("stats", ["test", "p-value", "pvalue", "statist", "normal", "régression", "regression", "anova", "corrélation",
               "capabilit", "cpk", "sigma", "gage", "msa", "kappa", "échantillon", "doe", "plan d'expérience", "carte de contrôle", "spc"]),
    ("causes", ["cause", "ishikawa", "pourquoi", "gemba", "gaspillage", "muda", "vsm", "goulot", "amdec", "fmea"]),
    ("solutions", ["solution", "poka", "smed", "5s", "kanban", "standard", "pilote", "plan d'action", "état futur", "amélior"]),
    ("changement", ["changement", "adkar", "kotter", "résistance", "communication", "adhésion", "raci", "acteur", "manager"]),
    ("soutenance", ["soutenance", "comité", "présentation", "pitch", "direction", "sponsor", "synthèse", "question"]),
    ("cadrage", ["problème", "ctq", "smart", "périmètre", "charte", "business case", "copq", "objectif", "kaizen", "voc", "sipoc"]),
]


def route(question: str, cfg: dict | None = None) -> str:
    """Choisit l'agent : classification par LLM si disponible, sinon par mots-clés."""
    q = question.lower()
    if cfg and AI.is_available(cfg):
        try:
            prompt = ("Classe la question d'un Black Belt vers UN expert parmi : "
                      + ", ".join(f"{k} ({a.mission[:70]})" for k, a in AGENTS.items())
                      + f"\nQuestion : {question}\nRéponds uniquement par la clé.")
            ans = AI.call_llm(prompt, cfg, system="Tu es un routeur. Réponds par un seul mot.", temperature=0, max_tokens=10)
            key = re.sub(r"[^a-z]", "", ans.lower())
            if key in AGENTS:
                return key
        except Exception:
            pass
    scores = {k: sum(1 for w in words if w in q) for k, words in ROUTES}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "revue"


def run_agent(agent_key: str, question: str, p: dict, cfg: dict, history: list | None = None,
              facts: dict | None = None) -> str:
    agent = AGENTS[agent_key]
    ctx = context_for(agent_key, p, facts)
    if not AI.is_available(cfg):
        return offline_answer(agent_key, p, facts)
    prompt = f"CONTEXTE DU PROJET (données réelles) :\n{ctx}\n\nDEMANDE DU BLACK BELT : {question}"
    try:
        return AI.call_llm(prompt, cfg, system=agent.system, temperature=0.3, max_tokens=1800,
                           history=(history or [])[-6:])
    except Exception as exc:
        return f"⚠️ {exc}\n\n" + offline_answer(agent_key, p, facts)


def offline_answer(agent_key: str, p: dict, facts: dict | None = None) -> str:
    """Réponse sans IA : uniquement des contrôles calculés, clairement signalée."""
    facts = facts if facts is not None else R.compute_facts(p)
    mat = maturity(p, facts)
    warn = pitfalls(p, facts)
    phase = AGENTS[agent_key].phase
    lines = ["🔌 **Mode hors-ligne** — contrôles automatiques (aucune IA). Ajoutez une clé gratuite pour les analyses rédigées.", ""]
    phases = PHASES if phase == "TOUTES" else [phase]
    for ph in phases:
        lines.append(f"**Jalon {ph} — {mat['scores'][ph]} %**")
        lines += [f"- {'✅' if ok else '❌'} {c}" + (f" — {d}" if d and d != 'OK' and not ok else "") for c, ok, d in mat[ph]]
    rel = [w for w in warn if phase == "TOUTES" or w[1] == phase]
    if rel:
        lines += ["", "**Alertes**"] + [f"- {g} {m}" for g, _, m in rel]
    if agent_key == "cadrage":
        pq = problem_quality(p.get("problem", ""))
        if pq:
            lines += ["", "**Énoncé du problème**"] + [f"- {x}" for x in pq]
    return "\n".join(lines)


def full_review(p: dict, cfg: dict) -> dict:
    """Revue complète du projet : maturité, alertes et avis du MBB."""
    facts = R.compute_facts(p)
    mat = maturity(p, facts)
    warn = pitfalls(p, facts)
    avis = run_agent("revue", "Réalise une revue complète du projet, phase par phase, puis donne le verdict global.", p, cfg, facts=facts)
    return {"maturite": {k: mat[k] for k in ("scores", "global")}, "alertes": warn, "avis": avis,
            "date": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}
