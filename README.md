# LSS Toolbox — conduite de projets Lean Six Sigma niveau Master Black Belt

Une application Streamlit gratuite pour conduire des projets DMAIC de bout en bout, avec une équipe d'agents IA spécialisés.

## Ce que fait l'application

| Onglet | Contenu |
|---|---|
| **DEFINE** | Problème et CTQ proposés par l'IA, matrice d'opportunité, VOC (analyse par IA), SIPOC, parties prenantes, planning, **charte : objectif SMART, périmètre IN/OUT, business case COPQ** |
| **MEASURE** | Y = f(X), VSM, plan de collecte, MSA, **Gage R&R (ANOVA) et Kappa**, collecte T0, capabilité |
| **ANALYZE** | Tests X→Y (choix automatique du test, données appariées), causes racines, AMDEC, Gemba, **régression multiple et Pareto** |
| **IMPROVE** | Solutions, matrice pondérée, bénéfice/effort, plan d'action, état futur, **plan d'expériences 2^k, pilote** |
| **CONTROL** | Vagues de contrôle, cartes I-MR, sigma |
| **🤝 CHANGEMENT** | ADKAR, plan de communication, RACI, registre des résistances |
| **🧮 OUTILS STATS** | Descriptif et normalité, tests d'hypothèse, taille d'échantillon et puissance, cartes I-MR / X̄-R / p / u, capabilité |
| **🧠 CENTRE IA** | Maturité DMAIC, garde-fous méthodologiques, 7 agents experts, revue complète par le Master Black Belt |
| **📣 RÉSULTATS** | Preuve avant/après, gains, plan de contrôle, leçons apprises, clôture, **soutenance PowerPoint complète** |

La page d'accueil affiche le **portefeuille de projets** : maturité, sigma, gains et alertes.

### L'équipe d'agents IA

| Agent | Rôle |
|---|---|
| 🎯 Cadrage | Énoncé du problème, arbre CTQ, objectif SMART, business case, choix entre DMAIC et Kaizen |
| 📐 Statisticien | MSA, stabilité, capabilité, choix et conditions des tests, puissance, régression, plans d'expériences |
| 🔍 Causes racines | Ishikawa 6M, 5 Pourquoi, gaspillages VSM, préparation du Gemba |
| 🛠️ Solutions Lean | Solutions par cause (poka-yoke, SMED, standard…), pilote, état futur |
| 🤝 Changement | ADKAR, messages de communication, traitement des résistances |
| 🧠 Master Black Belt | Revues de jalon, risques, verdict GO / NO GO |
| 📣 Soutenance | Questions pièges du comité, storytelling, pitch, note au sponsor |

Chaque agent ne reçoit que les données utiles à son métier, calculées à partir du projet. Il ne doit rien inventer et doit signaler les données manquantes. Une couche de **contrôles automatiques** (grille de maturité, garde-fous statistiques) fonctionne même sans IA.

## Mise en route (Streamlit Community Cloud)

1. **Fichier principal :** `streamlit_app.py`.
2. **Activer l'IA gratuite :**
   - créez une clé sur [console.groq.com](https://console.groq.com) (gratuit, sans carte bancaire) ;
   - dans Streamlit Cloud, ouvrez **⋮ → Settings → Secrets** ;
   - collez le contenu de `secrets_exemple.toml` avec votre clé.
3. **Essayer l'application :** importez `exemples/projet_exemple_credit_PME.json` depuis la barre latérale (**Reprendre mon travail**).
4. **Sauvegarder :** Streamlit Cloud efface ses fichiers à chaque redémarrage. Téléchargez votre sauvegarde `.json` avant de fermer.

## Organisation du code

| Fichier | Rôle |
|---|---|
| `streamlit_app.py` | Application (écrans DMAIC) |
| `lss_stats.py` | Moteur statistique |
| `lss_agents.py` | Agents IA, maturité, garde-fous |
| `lss_ai.py` | Connexion aux IA gratuites (Groq / Gemini) |
| `lss_report.py` | Génération de la soutenance PowerPoint |
| `modules_bb.py` | Charte, Gage R&R, régression, DOE, pilote, changement |
| `tab_centre_ia.py`, `tab_outils_stats.py`, `tab_resultats.py` | Onglets Centre IA, Outils statistiques, Résultats |
| `tests/run_app.py` | Test de bout en bout sans serveur : `python tests/run_app.py` |
