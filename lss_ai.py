"""
lss_ai.py — Vraie IA gratuite pour l'application Lean Six Sigma
===============================================================
Remplace les "IA" simulées (listes de CTQ en dur, diagnostic toujours
"Potentiel ROI élevé / Top 10 %", comptage de mots-clés) par un vrai modèle
de langage, appelé via une API GRATUITE :

  • Groq   (console.groq.com)      — gratuit, sans carte, n'entraîne pas sur vos données
  • Gemini (aistudio.google.com)   — gratuit sur les modèles Flash ; ATTENTION : en
                                     palier gratuit, Google peut utiliser vos données
                                     pour améliorer ses modèles → à éviter pour des
                                     données sensibles (clients, salaires, élections…)

Configuration (Streamlit Community Cloud → App → Settings → Secrets) :

    [ai]
    provider = "groq"                 # ou "gemini"
    groq_api_key = "gsk_..."
    groq_model = "llama-3.3-70b-versatile"   # à ajuster selon la liste du console Groq
    gemini_api_key = "AIza..."
    gemini_model = "gemini-flash-latest"     # à ajuster selon AI Studio

Sans clé, chaque fonction renvoie une réponse "hors-ligne" CLAIREMENT signalée
comme telle : l'application ne prétend jamais qu'une règle fixe est de l'IA.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import pandas as pd
import requests

TIMEOUT = 60

SYSTEM_MBB = (
    "Tu es un Master Black Belt Lean Six Sigma francophone, exigeant et pédagogue. "
    "Tu coaches un Black Belt qui conduit un projet DMAIC réel. Règles : "
    "1) Tu t'appuies UNIQUEMENT sur les données du projet fournies ; si une donnée manque, tu le dis. "
    "2) Tu distingues faits mesurés, hypothèses et recommandations. "
    "3) Tu cites les outils LSS pertinents (SIPOC, VOC/CTQ, MSA, capabilité, tests d'hypothèse, "
    "FMEA, Poka-Yoke, plan de contrôle, conduite du changement ADKAR/Kotter). "
    "4) Tu es concis, structuré, actionnable. Pas de flatterie."
)


# ---------------------------------------------------------------------------
# Configuration & appel bas niveau
# ---------------------------------------------------------------------------
def get_config(secrets: Any | None = None) -> dict:
    """Lit st.secrets['ai'] si disponible. `secrets` peut être st.secrets ou un dict."""
    cfg: dict = {}
    try:
        if secrets is None:
            import streamlit as st  # import tardif : le module reste testable sans Streamlit
            secrets = st.secrets
        cfg = dict(secrets.get("ai", {}))
    except Exception:
        cfg = {}
    cfg.setdefault("provider", "groq")
    cfg.setdefault("groq_model", "llama-3.3-70b-versatile")
    cfg.setdefault("gemini_model", "gemini-flash-latest")
    return cfg


def is_available(cfg: dict) -> bool:
    prov = cfg.get("provider")
    return bool(cfg.get(f"{prov}_api_key"))


def call_llm(prompt: str, cfg: dict, system: str = SYSTEM_MBB, temperature: float = 0.3,
             max_tokens: int = 1500, retries: int = 2, history: list | None = None) -> str:
    """Appelle le fournisseur choisi. Lève RuntimeError avec un message clair."""
    prov = cfg.get("provider", "groq")
    key = cfg.get(f"{prov}_api_key")
    if not key:
        raise RuntimeError("Aucune clé API configurée (voir st.secrets['ai']).")

    for attempt in range(retries + 1):
        try:
            if prov == "groq":
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": cfg["groq_model"], "temperature": temperature, "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system}]
                                      + [{"role": h["role"], "content": h["content"]} for h in (history or [])]
                                      + [{"role": "user", "content": prompt}]},
                    timeout=TIMEOUT)
                if r.status_code == 429 and attempt < retries:
                    time.sleep(8 * (attempt + 1)); continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()

            if prov == "gemini":
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                       f"{cfg['gemini_model']}:generateContent")
                r = requests.post(
                    url, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json={"systemInstruction": {"parts": [{"text": system}]},
                          "contents": [{"role": "model" if h["role"] == "assistant" else "user",
                                        "parts": [{"text": h["content"]}]} for h in (history or [])]
                                      + [{"role": "user", "parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
                    timeout=TIMEOUT)
                if r.status_code == 429 and attempt < retries:
                    time.sleep(8 * (attempt + 1)); continue
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts).strip()

            raise RuntimeError(f"Fournisseur inconnu : {prov}")
        except requests.HTTPError as exc:
            if r.status_code == 429:
                raise RuntimeError("Quota gratuit atteint (429). Réessayez dans une minute.") from exc
            raise RuntimeError(f"Erreur API {r.status_code} : {r.text[:300]}") from exc
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(3); continue
            raise RuntimeError(f"Connexion impossible au fournisseur IA : {exc}") from exc
    raise RuntimeError("Échec après plusieurs tentatives.")


def _extract_json(text: str):
    """Récupère le premier bloc JSON d'une réponse de LLM."""
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    raw = m.group(1) if m else text
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("Pas de JSON dans la réponse")
    return json.loads(raw[start:raw.rfind("}" if raw[start] == "{" else "]") + 1])


# ---------------------------------------------------------------------------
# Résumé compact du projet (pour tenir dans les quotas gratuits)
# ---------------------------------------------------------------------------
def _records(obj, limit=15) -> list[dict]:
    if obj is None:
        return []
    if isinstance(obj, pd.DataFrame):
        return obj.head(limit).to_dict("records")
    if isinstance(obj, dict) and obj.get("_type_df_"):
        return list(obj.get("data", []))[:limit]
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)][:limit]
    return []


def project_digest(p: dict, extra: dict | None = None, max_chars: int = 9000) -> str:
    """Texte structuré décrivant l'état du projet, phase par phase."""
    dm = p.get("dmaic", {}) or {}
    an, im = dm.get("analyze", {}) or {}, dm.get("improve", {}) or {}
    lines = [f"PROJET : {p.get('name') or p.get('nom')}", f"Phase déclarée : {p.get('status', '?')}",
             "", "## DEFINE", f"Problème : {p.get('problem') or '—'}", f"CTQ : {p.get('selected_ctq') or '—'}",
             f"Bénéfices attendus : {p.get('benefices_saisie') or '—'}"]
    sipoc = [r.get("Process") for r in _records(p.get("sipoc_data")) if r.get("Process")]
    if sipoc:
        lines.append("Étapes SIPOC : " + " → ".join(map(str, sipoc)))
    voc = _records(p.get("saved_voc_results"))
    if voc:
        lines.append("Thèmes VOC : " + "; ".join(f"{v.get('thème des irritants')} ({v.get('pourcentage')})" for v in voc))
    lines += ["", "## MEASURE"]
    x_tab = _records(p.get("measure_x_table"))
    if x_tab:
        lines.append("X candidats : " + "; ".join(str(r.get("Description", ""))[:80] for r in x_tab[:8]))
    if extra and extra.get("vsm"):
        lines.append(f"VSM T0 : {extra['vsm']}")
    if extra and extra.get("baseline"):
        lines.append(f"Baseline Y : {extra['baseline']}")
    lines.append(f"MSA validée : {'Oui' if p.get('msa_is_validated_status') else 'Non'}")
    lines += ["", "## ANALYZE"]
    for r in _records(an.get("results")):
        lines.append(f"- X={r.get('Variable X')} : {r.get('Le X agit-il sur Y ?')} (p={r.get('P-value')})")
    for x, st_ in (an.get("x_analyses") or {}).items():
        causes = [c for c in st_.get("causes_racines_list", []) if c]
        if causes:
            lines.append(f"Causes racines ({x}) : " + "; ".join(causes))
    lines += ["", "## IMPROVE"]
    for r in _records(im.get("strategies")):
        lines.append(f"- Solution : {r.get('Solution potentielle')} → cause : {r.get('Cause racine')} ({r.get('Type de solution')})")
    ap = im.get("action_plan") or {}
    if ap:
        lines.append(f"Plan d'action : {len(ap)} actions, budget total {sum(float(v.get('budget') or 0) for v in ap.values()):,.0f} Ar")
    lines += ["", "## CONTROL"]
    if extra and extra.get("before_after"):
        lines.append(f"Avant/Après : {extra['before_after']}")
    if extra and extra.get("gains"):
        lines.append(f"Gains : {extra['gains']}")
    res = p.get("results_closure", {}) or {}
    if res.get("lecons"):
        lines.append(f"Leçons apprises : {res['lecons']}")
    txt = "\n".join(str(l) for l in lines)
    return txt[:max_chars]


# ---------------------------------------------------------------------------
# Fonctions métier
# ---------------------------------------------------------------------------
def coach_review(p: dict, phase: str, cfg: dict, extra: dict | None = None) -> str:
    """Revue de jalon (tollgate) d'une phase par le Master Black Belt."""
    prompt = (f"Voici l'état du projet :\n\n{project_digest(p, extra)}\n\n"
              f"Fais la REVUE DE JALON (tollgate) de la phase {phase.upper()}. Structure :\n"
              "1. Ce qui est solide (max 3 points)\n2. Lacunes bloquantes avant de passer à la phase suivante\n"
              "3. Erreurs méthodologiques ou statistiques détectées\n"
              "4. Les 3 prochaines actions concrètes (qui / quoi / livrable)\n"
              "5. Verdict : GO / GO sous conditions / NO GO")
    return _safe(prompt, cfg, fallback=_offline_checklist(phase))


def suggest_ctq(problem: str, cfg: dict) -> list[str]:
    prompt = (f"Problème décrit par le Black Belt :\n\"\"\"{problem}\"\"\"\n\n"
              "1) Reformule-le en énoncé de problème SMART (quoi, où, quand, ampleur, impact) si possible.\n"
              "2) Propose 4 CTQ mesurables (indicateur + unité + cible + sens d'amélioration).\n"
              "Réponds en JSON : {\"enonce\": \"...\", \"ctq\": [\"...\", ...]}")
    try:
        data = _extract_json(call_llm(prompt, cfg, temperature=0.2))
        return [data.get("enonce", "")] + list(data.get("ctq", []))
    except Exception as exc:
        return [f"⚠️ IA indisponible ({exc}). Formulez un CTQ : indicateur + unité + cible, ex. « Délai de traitement < 48 h pour 95 % des dossiers »."]


def analyse_voc(verbatims: list[str], cfg: dict, max_items: int = 150) -> pd.DataFrame:
    """Analyse thématique réelle des verbatims (remplace le comptage de mots-clés)."""
    sample = [v for v in verbatims if str(v).strip()][:max_items]
    numbered = "\n".join(f"{i+1}. {v}" for i, v in enumerate(sample))
    prompt = ("Analyse thématique de verbatims clients (Voice of Customer).\n"
              f"{numbered}\n\nRegroupe-les en 3 à 7 thèmes. Pour chaque thème : nom, besoin client sous-jacent, "
              "type de gaspillage Lean (Muda/Mura/Muri ou défaut), CTQ mesurable proposé, liste des numéros de verbatims. "
              "Réponds en JSON : [{\"theme\":..., \"besoin\":..., \"gaspillage\":..., \"ctq\":..., \"verbatims\":[1,4]}]")
    try:
        data = _extract_json(call_llm(prompt, cfg, temperature=0.2, max_tokens=2500))
        rows = []
        for t in data:
            n = len(set(t.get("verbatims", [])))
            rows.append({"thème des irritants": t.get("theme"), "explication": t.get("gaspillage"),
                         "besoin client": t.get("besoin"), "nombre d'occurrence": n,
                         "pourcentage": f"{100*n/max(len(sample),1):.1f}%", "CTQ": t.get("ctq")})
        return pd.DataFrame(rows).sort_values("nombre d'occurrence", ascending=False).reset_index(drop=True)
    except Exception as exc:
        return pd.DataFrame([{"thème des irritants": "⚠️ IA indisponible", "explication": str(exc)}])


def executive_summary(p: dict, facts: dict, cfg: dict) -> dict:
    """Résumé exécutif + messages clés pour la soutenance, à partir de FAITS chiffrés."""
    prompt = (f"Données du projet :\n{project_digest(p, facts)}\n\nFaits chiffrés vérifiés :\n"
              f"{json.dumps(facts, ensure_ascii=False, default=str)[:4000]}\n\n"
              "Rédige pour un comité de direction :\n"
              "- 'resume' : 5 phrases max (problème, démarche, résultat prouvé, gain, pérennisation)\n"
              "- 'messages_cles' : 3 à 5 puces courtes, chiffrées\n"
              "- 'risques' : 2 à 3 risques résiduels\n"
              "- 'demandes' : décisions attendues du sponsor\n"
              "N'invente AUCUN chiffre absent des faits. Réponds en JSON avec ces 4 clés.")
    try:
        data = _extract_json(call_llm(prompt, cfg, temperature=0.2))
        data["source"] = "IA"
        return data
    except Exception as exc:
        return offline_summary(p, facts, reason=str(exc))


def offline_summary(p: dict, facts: dict, reason: str = "") -> dict:
    """Résumé construit par règles (sans IA), à partir des seuls faits calculés."""
    ba = facts.get("before_after") or {}
    msgs = []
    if ba.get("ok"):
        if ba.get("type") == "continu":
            msgs.append(f"Y moyen : {ba['moyenne_avant']} → {ba['moyenne_apres']} ({ba.get('delta_%')} %)")
        else:
            msgs.append(f"Taux de défauts : {ba['taux_defaut_avant_%']} % → {ba['taux_defaut_apres_%']} %")
        msgs.append(ba["conclusion"])
    if facts.get("sigma_avant") is not None and facts.get("sigma_apres") is not None:
        msgs.append(f"Niveau sigma : {facts['sigma_avant']} → {facts['sigma_apres']}")
    if facts.get("gains_total"):
        msgs.append(f"Gains validés : {facts['gains_total']:,.0f} Ar / an".replace(",", " "))
    resume = (f"Le projet « {p.get('name') or p.get('nom')} » traitait le problème suivant : "
              f"{(p.get('problem') or 'non renseigné')[:220].rstrip('. ')}. "
              f"CTQ suivi : {p.get('selected_ctq') or 'non défini'}. "
              + (ba.get("conclusion", "Résultats avant/après à compléter.") if ba else "Résultats avant/après à compléter."))
    return {"resume": resume, "messages_cles": msgs or ["Compléter les données T0 et Control pour chiffrer les résultats."],
            "risques": ["Dérive si le plan de contrôle n'est pas appliqué par le propriétaire du processus."],
            "demandes": ["Valider les gains avec le contrôle de gestion", "Officialiser le transfert au propriétaire du processus"],
            "source": "Règles (hors-ligne)" + (f" — {reason[:80]}" if reason else "")}


def speaker_notes(slide_title: str, content: str, cfg: dict) -> str:
    prompt = (f"Diapositive « {slide_title} » d'une soutenance DMAIC. Contenu :\n{content[:2500]}\n\n"
              "Écris les notes de l'orateur (60 à 90 secondes à l'oral) : message principal, preuve, transition. "
              "N'invente aucun chiffre.")
    return _safe(prompt, cfg, fallback="")


def ask(question: str, p: dict, cfg: dict, extra: dict | None = None) -> str:
    """Chat libre avec le coach, contextualisé par le projet."""
    prompt = f"Contexte projet :\n{project_digest(p, extra)}\n\nQuestion du Black Belt : {question}"
    return _safe(prompt, cfg, fallback="⚠️ Coach IA hors-ligne : configurez une clé gratuite Groq ou Gemini.")


# ---------------------------------------------------------------------------
def _safe(prompt: str, cfg: dict, fallback: str) -> str:
    if not is_available(cfg):
        return "🔌 **Mode hors-ligne (aucune clé IA)**\n\n" + fallback if fallback else ""
    try:
        return call_llm(prompt, cfg)
    except Exception as exc:
        return f"⚠️ {exc}\n\n" + fallback


TOLLGATE = {
    "define": ["Énoncé du problème factuel (quoi/où/quand/combien), sans cause ni solution",
               "Objectif SMART chiffré sur le Y", "Périmètre IN/OUT", "Business case (COPQ en Ar)",
               "Sponsor, équipe, propriétaire du processus nommés", "SIPOC validé", "VOC → CTQ mesurables",
               "Planning et jalons", "Analyse des parties prenantes + plan de communication"],
    "measure": ["Définition opérationnelle du Y", "Plan de collecte (quoi/qui/quand/combien)",
                "MSA : Gage R&R %GRR < 30 % (ou Kappa ≥ 0.7)", "Baseline : moyenne, σ, carte I-MR stable ?",
                "Capabilité initiale (DPMO, sigma, Cpk)", "Cartographie VSM : lead time, PCE"],
    "analyze": ["X criblés par tests d'hypothèse (p-values)", "Causes racines (Ishikawa, 5 pourquoi)",
                "Validation terrain (Gemba)", "Quantification de l'effet de chaque X validé", "FMEA actuelle"],
    "improve": ["Solutions reliées à chaque cause validée", "Matrice de sélection pondérée",
                "Pilote / essai avec données", "Plan d'action (qui, quand, budget)", "FMEA future", "Plan de conduite du changement"],
    "control": ["Preuve statistique avant/après", "Capabilité après", "Plan de contrôle (quoi, spéc., fréquence, réaction)",
                "Standards / SOP mis à jour", "Formation", "Gains validés par la finance", "Transfert au propriétaire du processus"],
}


def _offline_checklist(phase: str) -> str:
    items = TOLLGATE.get(phase.lower(), [])
    return "Checklist de jalon à vérifier :\n" + "\n".join(f"- [ ] {i}" for i in items)
