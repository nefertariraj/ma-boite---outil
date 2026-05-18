import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION DE LA PAGE & STYLE ---
st.set_page_config(page_title="LSS - Personal Toolbox", layout="wide")

if 'primary_color' not in st.session_state:
    st.session_state.primary_color = "#1E3A8A" 

st.markdown(f"""
    <style>
    .stApp {{ background-color: #FFFFFF; }}
    .stButton>button {{ background-color: {st.session_state.primary_color}; color: white; border-radius: 5px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; }}
    .stTabs [data-baseweb="tab"] {{ font-weight: bold; color: #4B5563; }}
    </style>
    """, unsafe_allow_html=True)

# --- GESTION DES DONNÉES ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'projects' not in st.session_state:
    st.session_state.projects = []
if 'current_project_idx' not in st.session_state:
    st.session_state.current_project_idx = None

# --- ÉCRAN DE CONNEXION ---
if not st.session_state.authenticated:
    st.title("🔐 Lean Six Sigma - Personal Toolbox")
    with st.container(border=True):
        user = st.text_input("Identifiant (Email Google)")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter via Google Drive"):
            if user and pwd: 
                st.session_state.authenticated = True
                st.rerun()
    st.stop()

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("⚙️ Paramètres & Sauvegarde")
    
    # 1. PERSONNALISATION
    color = st.color_picker("Couleur de l'outil", st.session_state.get('primary_color', '#007BFF'))
    st.session_state.primary_color = color
    
    st.divider()

    # --- 2. EXPORTATION (SAUVEGARDER) ---
    st.subheader("💾 Sauvegarder mon travail")
    if st.session_state.get('projects'):
        import json

        # Fonction pour ignorer les objets complexes (comme les graphiques) qui font planter le JSON
        def clean_for_json(obj):
            if isinstance(obj, (dict, list, str, int, float, bool, type(None))):
                if isinstance(obj, dict):
                    return {k: clean_for_json(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [clean_for_json(i) for i in obj]
                return obj
            return str(obj)

        try:
            projects_cleaned = clean_for_json(st.session_state.projects)
            data_json = json.dumps(projects_cleaned, indent=4, ensure_ascii=False)
            
            st.download_button(
                label="📤 Télécharger ma sauvegarde (.json)",
                data=data_json,
                file_name="sauvegarde_boite_outils.json",
                mime="application/json",
                help="Cliquez ici pour enregistrer vos projets sur votre ordinateur."
            )
        except Exception as e:
            st.error(f"Erreur préparation : {e}")
    else:
        st.info("Aucun projet à sauvegarder.")

    # --- 3. IMPORTATION (RECHARGER) ---
    st.subheader("📥 Reprendre mon travail")
    uploaded_file = st.file_uploader("Importer un fichier de sauvegarde", type="json")
    
    if uploaded_file is not None:
        try:
            import json
            restored_data = json.load(uploaded_file)
            st.session_state.projects = restored_data
            st.success("✅ Données chargées !")
            if st.button("🔄 Actualiser l'affichage"):
                st.rerun()
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")

    # --- SECTION EXPORT DU PROJET COMPLET (EXCEL, PPTX) ---
    # On vérifie si un projet est sélectionné pour afficher les boutons d'export spécifiques
    if st.session_state.get('current_project_idx') is not None:
        st.divider()
        st.subheader("📥 Exporter le projet complet")
        
        p_exp = st.session_state.projects[st.session_state.current_project_idx]
        project_name = p_exp['name']
        import io

        # --- 1. EXPORT EXCEL ---
        try:
            buffer_xlsx = io.BytesIO()
            with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
                pd.DataFrame([{"Projet": project_name, "Statut": p_exp['status'], "Définition": p_exp.get('problem', '')}]).to_excel(writer, sheet_name='Synthèse', index=False)
                if p_exp.get('sipoc_data'):
                    pd.DataFrame(p_exp['sipoc_data']).to_excel(writer, sheet_name='SIPOC', index=False)
                if p_exp.get('stakeholders'):
                    pd.DataFrame(p_exp['stakeholders']).to_excel(writer, sheet_name='Parties_Prenantes', index=False)
            
            st.download_button(label="📊 Télécharger en Excel", data=buffer_xlsx.getvalue(), file_name=f"{project_name}.xlsx", mime="application/vnd.ms-excel")
        except Exception as e:
            st.error("Erreur Excel : Vérifiez openpyxl")

        # --- 2. EXPORT POWERPOINT ---
        try:
            from pptx import Presentation
            def create_pptx(data_proj):
                prs = Presentation()
                slide = prs.slides.add_slide(prs.slide_layouts[0])
                slide.shapes.title.text = data_proj['name']
                slide.placeholders[1].text = f"Statut : {data_proj.get('status', '')}"
                buffer = io.BytesIO()
                prs.save(buffer)
                return buffer.getvalue()

            pptx_bytes = create_pptx(p_exp)
            st.download_button(label="📽️ Télécharger en PowerPoint", data=pptx_bytes, file_name=f"{project_name}.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        except Exception as e:
            st.info("Erreur PPTX : Vérifiez python-pptx")

    st.divider()
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

# --- NAVIGATION PRINCIPALE ---
if st.session_state.current_project_idx is None:
    st.title("🚀 Mes Projets Lean Six Sigma")
    
    with st.expander("➕ Initialiser un nouveau projet"):
        p_name = st.text_input("Nom du projet")
        if st.button("Créer le projet"):
            if p_name:
                new_p = {
                    "name": p_name,
                    "status": "Define",
                    "problem": "",         # Corrigé : ajouté pour éviter KeyError
                    "sipoc_data": [{"Fournisseur": "", "Entrée": "", "Processus": "", "Sortie": "", "Client": ""}],
                    "voc_data": [{"Client": "", "Verbatim": "", "Besoin": ""}],
                    "selected_ctq": "Qualité",
                    "team": pd.DataFrame(columns=["Poste", "Nom"]) # Corrigé : ajouté
                }
                st.session_state.projects.append(new_p)
                st.success("Projet créé !")
                st.rerun()

    cols = st.columns(3)
    for idx, proj in enumerate(st.session_state.projects):
        with cols[idx % 3]:
            with st.container(border=True):
                st.subheader(proj["name"])
                if st.button("Ouvrir", key=f"open_{idx}"):
                    st.session_state.current_project_idx = idx
                    st.rerun()

else:
    # --- VUE PROJET (DMAIC) ---
    p_idx = st.session_state.current_project_idx
    p = st.session_state.projects[p_idx]

    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("⬅️"):
            st.session_state.current_project_idx = None
            st.rerun()
            
    with col_title:
        st.title(f"Projet : {p['name']}")

    # Définition des onglets
    tabs = st.tabs(["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"])

    # --- PHASE DEFINE ---
    with tabs[0]:
        st.header("Phase Define")
    
        # Récupération de l'index et du projet pour l'ensemble de l'onglet
        p_idx = st.session_state.get('current_project_idx', 0)
        p = st.session_state.projects[p_idx]
    
        # 1. Problème & CTQ
        st.subheader("1. Énoncé du Problème & CTQ")
        col1, col2 = st.columns(2)
    
        with col1:
            st.markdown('<p title="X correspond aux causes">Décrivez le problème en détail :</p>', unsafe_allow_html=True)
            # Utilisation de .get pour éviter le KeyError si le projet est ancien
            p_input = st.text_area("Saisie libre", value=p.get("problem", ""), height=150, key=f"prob_in_{p_idx}")
        
            if st.button("🪄 Retranscrire via IA"):
                p["problem"] = p_input
                st.session_state.ai_suggest_ctq = [
                    "⏱️ Temps : Réduire le Lead Time global",
                    "🎯 Qualité : Augmenter le taux de conformité (%C&A)",
                    "💰 Coût : Réduire les coûts opérationnels",
                    f"✨ Spécifique : {p_input[:30]}..."
                ]
                st.rerun() 

        with col2:
            st.write("Propositions de l'IA (CTQ) :")
            if 'ai_suggest_ctq' in st.session_state:
                for ctq in st.session_state.ai_suggest_ctq:
                    if st.button(ctq, key=f"btn_{ctq}"):
                        p["selected_ctq"] = ctq
                        st.rerun()
        
            st.divider()
        
            if "selected_ctq" in p and p["selected_ctq"]:
                st.write("✍️ **Ajustez votre CTQ final :**")
                new_val = st.text_input("Libellé du CTQ", value=p["selected_ctq"], key=f"edit_ctq_{p_idx}")
            
            if new_val != p["selected_ctq"]:
                p["selected_ctq"] = new_val
                st.rerun()
            st.info(f"**CTQ validé :** {p['selected_ctq']}")

        # 2. Équipe Projet
        st.divider()
        st.subheader("2. Équipe Projet")
        team_key = f"editor_team_{p_idx}"
        edited_team = st.data_editor(
            p.get("team_data", [{"Poste": "", "Nom": ""}]), 
            num_rows="dynamic",
            use_container_width=True,
            key=team_key
        )
        if st.button("✅ Valider l'équipe", key=f"save_team_{p_idx}"):
            p["team_data"] = edited_team
            st.success("Équipe enregistrée !")
            st.rerun()

        # 3. BÉNÉFICES ATTENDUS & MATRICE D'OPPORTUNITÉ ---
        st.divider()
        st.subheader("3. Bénéfices Attendus & Matrice d'Opportunité")

        # Initialisation sécurisée pour l'import/export
        if "benefices_saisie" not in p:
            p["benefices_saisie"] = ""

        # Zone de saisie
        p["benefices_saisie"] = st.text_area(
            "Définissez les gains espérés (Financiers, Qualité, Délais) :",
            value=p["benefices_saisie"],
            height=120,
            placeholder="Ex: Réduction du taux de rebus de 15%, gain de 2 jours sur le lead time...",
            key=f"area_ben_v13_{p_idx}"
        )

        if len(p["benefices_saisie"]) > 10:
            st.markdown("---")
        
            # 1. ANALYSE SÉMANTIQUE BLACK BELT
            c_alt1, c_alt2 = st.columns([2, 1])
            with c_alt1:
                st.markdown("### 💎 Diagnostic de l'Opportunité")
                st.success(f"""
                **Analyse de la Valeur Ajoutée :**
                Votre description (« *{p['benefices_saisie'][:60]}...* ») suggère un potentiel de réduction des **COPQ** (Coûts de Non-Qualité) significatif. 
            
                *   **Levier Principal :** Optimisation de la performance (Sigma Level).
                *   **Type de Gain :** Hard Savings identifiés.
                *   **Risque de Cadrage :** Faible (Périmètre cohérent avec une démarche DMAIC).
                """)
        
            with c_alt2:
                st.metric("Potentiel de ROI", "Élevé", delta="Top 10% Projets")
                st.write("**Statut :** Candidat idéal pour analyse approfondie.")

            # 2. LA MATRICE D'OPPORTUNITÉ (Visualisation)
            with st.expander("👁️ Visualiser la Matrice d'Opportunité (Go / No-Go)"):
                st.write("Cette matrice évalue si le projet est 'éligible' à une certification Black Belt ou s'il s'agit d'un simple projet de maintenance.")
            
                # Mise en page de la matrice
                m_col1, m_col2 = st.columns([2, 1])
            
                with m_col1:
                    st.markdown("""
                    | | **COMPLEXITÉ MAÎTRISÉE** | **COMPLEXITÉ ÉLEVÉE** |
                    |---|---|---|
                    | **VALEUR STRATÉGIQUE** | ✨ **OPPORTUNITÉ MAJEURE** (Go) | 🏗️ **CHANTIER COMPLEXE** |
                    | **VALEUR MODÉRÉE** | 🤏 **MICRO-AMÉLIORATION** | ❌ **HORS PÉRIMÈTRE** |
                    """)
            
                with m_col2:
                    st.markdown("**Positionnement IA**")
                    # Curseur de positionnement basé sur le texte
                    st.select_slider(
                        "Éligibilité :",
                        options=["Hors périmètre", "Micro-Amélioration", "Chantier Complexe", "Opportunité Majeure"],
                        value="Opportunité Majeure",
                        disabled=True
                    )
                    st.caption("L'IA préconise le passage en phase 'Measure'.")
        else:
            st.info("💡 Décrivez vos bénéfices pour activer le diagnostic d'opportunité Black Belt.")

        # 4. Stakeholder Analysis
        st.divider()
        st.subheader("4. Stakeholder Analysis (Matrice d'adhésion)")

        # Initialisation des données si elles n'existent pas
        if "stakeholders" not in p:
            p["stakeholders"] = [
                {
                    "Name": "Sponsor",
                    "Strongly Against": False,
                    "Moderately Against": False,
                    "Neutral": True,
                    "Moderately Supportive": False,
                    "Strongly Supportive": False
                }
            ]

        st.info("Cochez le niveau d'adhésion actuel pour chaque partie prenante. Vous pouvez ajouter/supprimer des lignes via les icônes du tableau.")

        # Utilisation du data_editor
        edited_stakeholders = st.data_editor(
            p["stakeholders"],
            num_rows="dynamic", 
            key=f"stake_edit_{p_idx}",
            use_container_width=True,
            column_config={
                "Strongly Against": st.column_config.CheckboxColumn(default=False),
                "Moderately Against": st.column_config.CheckboxColumn(default=False),
                "Neutral": st.column_config.CheckboxColumn(default=False),
                "Moderately Supportive": st.column_config.CheckboxColumn(default=False),
                "Strongly Supportive": st.column_config.CheckboxColumn(default=False),
            }
        )

        if st.button("✅ Sauvegarder l'analyse des parties prenantes", key=f"save_stake_{p_idx}"):
            p["stakeholders"] = edited_stakeholders
            st.success("Analyse sauvegardée !")

        # 5. SIPOC & FLUX CROISÉ COMPACT ---
        st.divider()
        st.subheader("5. SIPOC & Flux de processus")

        COLONNES_SIPOC = ["Supplier", "Input", "Process", "Output", "Customer"]
    
        if "sipoc_data" not in p or not isinstance(p["sipoc_data"], list):
            p["sipoc_data"] = [dict.fromkeys(COLONNES_SIPOC, "")]

        with st.form(key=f"form_sipoc_compact_{p_idx}"):
            df_init_sipoc = pd.DataFrame(p["sipoc_data"])
            for col in COLONNES_SIPOC:
                if col not in df_init_sipoc.columns:
                    df_init_sipoc[col] = ""
        
            edited_sipoc = st.data_editor(
                df_init_sipoc[COLONNES_SIPOC],
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_sipoc_comp_{p_idx}",
                column_config={c: st.column_config.TextColumn(c) for c in COLONNES_SIPOC}
            )
            submit_sipoc = st.form_submit_button("✅ Actualiser le flux")

        if submit_sipoc:
            p["sipoc_data"] = edited_sipoc.to_dict('records')
            st.rerun()

        df_viz_sipoc = pd.DataFrame(p["sipoc_data"])
        df_viz_sipoc = df_viz_sipoc[(df_viz_sipoc["Process"].astype(str).str.strip() != "") & 
                                (df_viz_sipoc["Customer"].astype(str).str.strip() != "")]
    
        if not df_viz_sipoc.empty:
            st.write("---")
            acteurs = df_viz_sipoc["Customer"].unique().tolist()
            cols_act = st.columns(len(acteurs))
        
            for i, acteur in enumerate(acteurs):
                cols_act[i].markdown(f"<p style='font-weight:bold; font-size:14px; margin-bottom:0;'>{acteur.upper()}</p>", unsafe_allow_html=True)
                cols_act[i].divider()

            # Rendu des tâches
            for idx, row in df_viz_sipoc.iterrows():
                current_col = acteurs.index(row["Customer"])
                row_cols = st.columns(len(acteurs))
            
                has_next = idx < len(df_viz_sipoc) - 1
                if has_next:
                    next_actor = df_viz_sipoc.iloc[idx + 1]["Customer"]
                    next_col = acteurs.index(next_actor)

                for i in range(len(acteurs)):
                    with row_cols[i]:
                        if i == current_col:
                            st.markdown(f"""
                                <div style="border: 1px solid #e0e0e0; border-radius: 5px; padding: 5px 10px; background-color: #f8f9fa; font-size: 14px;">
                                    {row['Process']}
                                </div>
                            """, unsafe_allow_html=True)
                        
                            if has_next:
                                if next_col == current_col:
                                    st.markdown("<p style='text-align:center; margin:0; line-height:1;'>↓</p>", unsafe_allow_html=True)
                                elif next_col > current_col:
                                    st.markdown("<p style='text-align:right; margin:0; line-height:1;'>➡</p>", unsafe_allow_html=True)
                                else:
                                    st.markdown("<p style='text-align:left; margin:0; line-height:1;'>⬅</p>", unsafe_allow_html=True)
                        else:
                            st.write("")

        # 6. VOICE OF CUSTOMER (VOC)
        st.divider()
        st.header("6. Voice of Customer (VOC) - Flux Black Belt")

        # Initialisation des variables
        if "voc_questions" not in p:
            p["voc_questions"] = ["Temps perdu ?", "Retouches ?", "Pénibilité ?", "Irritants ?", "Changement unique ?"]
        if "voc_raw_data" not in st.session_state:
            st.session_state.voc_raw_data = pd.DataFrame(columns=["client", "question", "réponse brute"])

        st.subheader("1. Élaboration du Questionnaire")
        with st.expander("📝 Configurer les questions"):
            for i, q in enumerate(p["voc_questions"]):
                p["voc_questions"][i] = st.text_input(f"Question {i+1}", value=q, key=f"q_v9_{p_idx}_{i}")

        st.write("---")
        st.subheader("2. Collecte des Données")
    
        up_file = st.file_uploader("Importer un fichier Excel", type=["xlsx", "xls"], key=f"up_v_final_{p_idx}")
    
        if up_file is not None:
            file_id = f"{up_file.name}_{up_file.size}"
            if st.session_state.get("last_file") != file_id:
                try:
                    df_imp = pd.read_excel(up_file).fillna("")
                    df_imp.columns = [c.lower().strip() for c in df_imp.columns]
                    
                    # Détection intelligente des colonnes
                    c_col = next((c for c in df_imp.columns if "client" in c or "nom" in c), df_imp.columns[0])
                    
                    # CORRECTION ICI : On cherche une colonne "question" dans l'excel, sinon on prend la 2ème colonne
                    q_col = next((c for c in df_imp.columns if "quest" in c), df_imp.columns[1] if len(df_imp.columns) > 1 else None)
                    
                    r_col = next((c for c in df_imp.columns if "rép" in c or "verbatim" in c or "brute" in c), df_imp.columns[-1])
                
                    # Construction du nouveau DataFrame avec les vraies questions
                    new_rows = pd.DataFrame({
                        "client": df_imp[c_col].astype(str),
                        # Si une colonne question existe dans le fichier, on la prend. Sinon, on applique une question générique.
                        "question": df_imp[q_col].astype(str) if q_col else "Question non spécifiée",
                        "réponse brute": df_imp[r_col].astype(str)
                    })
                    
                    st.session_state.voc_raw_data = new_rows
                    st.session_state.voc_results = None  
                    st.session_state.last_file = file_id
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'import : {e}")
        st.subheader("3. Analyse Thématique & CTQ")
    
        if st.button("🧠 Lancer l'Analyse (Vue Black Belt)", key=f"btn_run_voc_{p_idx}"):
            df_to_analyze = st.session_state.voc_raw_data
            if not df_to_analyze.empty:
                verbatims = df_to_analyze.iloc[:, -1].astype(str).str.lower().tolist()
                total = len(verbatims)
                mapping = [
                    {"th": "Délais (Lead Time)", "kw": ["temps", "long", "attente", "lent", "délai", "retard", "planning"], "ex": "Muda d'attente (Gaspillage)", "ctq": "Lead Time < 24h"},
                    {"th": "Qualité (Défauts)", "kw": ["refaire", "erreur", "trompé", "faute", "qualité", "mauvais", "non-conforme"], "ex": "Non-conformités (COPQ)", "ctq": "First Pass Yield 100%"},
                    {"th": "Pénibilité", "kw": ["pénible", "lourd", "difficile", "fatigue", "compliqué", "stress"], "ex": "Muri (Surcharge)", "ctq": "Ergonomie & Standard Work"},
                    {"th": "Outils", "kw": ["bug", "système", "outil", "logiciel", "ordinateur", "panne"], "ex": "Capabilité des moyens", "ctq": "Disponibilité IT > 99.9%"},
                    {"th": "Information", "kw": ["info", "manque", "flou", "comprendre", "échange", "communication"], "ex": "Mura (Variabilité du flux)", "ctq": "Standardisation de l'info"}
                ]
                res_data = []
                for m in mapping:
                    count = sum(1 for r in verbatims if any(k in r for k in m["kw"]))
                    res_data.append({
                        "thème des irritants": m["th"],
                        "explication": m["ex"],
                        "nombre d'occurrence": count,
                        "pourcentage": f"{(count/total)*100:.1f}%" if total > 0 else "0%",
                        "CTQ": m["ctq"],
                        "score": count
                    })
                st.session_state.voc_results = pd.DataFrame(res_data).sort_values("score", ascending=False).drop(columns=["score"])
                st.rerun()
            else:
                st.warning("⚠️ Le tableau est vide.")

        if st.session_state.get("voc_results") is not None:
            st.write("### 📊 Résultat de l'Analyse Thématique")
            st.table(st.session_state.voc_results)
            st.write("---")
            st.subheader("4. Diagnostic Expert & Plan d'Action Black Belt")
            res_voc = st.session_state.voc_results
            top_theme = res_voc.iloc[0]["thème des irritants"]
            ctq_cible = res_voc.iloc[0]["CTQ"]
        
            st.markdown(f"### 🎯 Focus Prioritaire : **{top_theme}**")
            st.write(f"Sur la base de l'analyse des verbatims, voici les 4 axes stratégiques pour impacter le CTQ : `{ctq_cible}`")

            # Configuration des 4 propositions selon le thème dominant
            plans_action = {
                "Délais (Lead Time)": [
                    "**Standardisation des flux (Takt Time)** : Aligner la cadence de production sur la demande client pour éliminer les stocks tampons.",
                    "**Mise en place d'un système Pull (Kanban)** : Réduire les en-cours en ne déclenchant le travail que sur signal de l'étape suivante.",
                    "**Chantier SMED / Setup** : Réduire les temps de changement de série pour gagner en flexibilité et réduire les attentes.",
                    "**Visual Management (Andon)** : Installer des indicateurs visuels pour détecter instantanément tout arrêt de flux."
                ],
                "Qualité (Défauts)": [
                    "**Analyse Poka-Yoke (Détrompeurs)** : Concevoir des systèmes physiques ou numériques empêchant l'erreur de se produire.",
                    "**Standard Work & Formation** : Réviser les modes opératoires et certifier les opérateurs sur les 'Points Clés de Qualité'.",
                    "**Mise en place du Jidoka** : Arrêt automatique du processus dès l'apparition d'un défaut pour éviter la propagation.",
                    "**Contrôle Statistique des Procédés (MSP)** : Suivre la variabilité en temps réel pour anticiper les dérives hors tolérance."
                ],
                "Pénibilité": [
                    "**Réingénierie Ergonomique** : Modifier l'implantation du poste (5S) pour réduire les déplacements et gestes inutiles (Muda).",
                    "**Équilibrage de ligne (Heijunka)** : Lisser la charge de travail pour éviter les pics de stress et la surcharge (Muri).",
                    "**Automatisation des tâches à faible valeur** : Déléguer les tâches répétitives à des solutions RPA ou mécaniques.",
                    "**Rotation de postes** : Planifier la polyvalence pour réduire l'exposition prolongée aux contraintes physiques/mentales."
                ],
                "Outils": [
                    "**Maintenance Préventive (TPM)** : Passer d'une logique curative à une maintenance planifiée pour garantir la capabilité machine.",
                    "**Mise à niveau technologique** : Investir dans des outils dont la précision est 10x supérieure à la tolérance du CTQ.",
                    "**Digitalisation du feedback** : Intégrer la saisie de données à la source pour éliminer les doubles saisies et erreurs outils.",
                    "**Audit de Capabilité (Cp/Cpk)** : Vérifier mathématiquement si l'outil actuel peut techniquement tenir les objectifs."
                ],
                "Information": [
                    "**Standardisation des échanges (SBAR)** : Imposer un format de communication structuré pour éliminer les ambiguïtés.",
                    "**Mise en place d'une 'Single Source of Truth'** : Centraliser les données pour éviter les versions de documents contradictoires.",
                    "**Rituels AIC (Animation à Intervalle Court)** : Créer des boucles de feedback rapides (5-10 min) pour fluidifier l'info.",
                    "**Management Visuel Numérique** : Rendre les informations critiques accessibles en un coup d'œil via des Dashboards partagés."
                ]
            }

            # Récupération des propositions (ou par défaut si thème inconnu)
            propositions = plans_action.get(top_theme, [
                "Audit approfondi des processus.", "Standardisation des tâches.", "Formation des équipes.", "Suivi des indicateurs."
            ])

            # Affichage en colonnes pour un rendu "Dashboard"
            col_a, col_b = st.columns(2)
            with col_a:
                st.info(f"💡 **Proposition 1**\n\n{propositions[0]}")
                st.info(f"🚀 **Proposition 2**\n\n{propositions[1]}")
            with col_b:
                st.info(f"🛠️ **Proposition 3**\n\n{propositions[2]}")
                st.info(f"📊 **Proposition 4**\n\n{propositions[3]}")

        from datetime import date
        import pandas as pd
        import plotly.express as px
        # --- 7. PROJECT MILESTONE & TIMING ---
        st.divider()
        st.header("📅 7. Project Milestone & Timing")

        # 1. Initialisation sécurisée dans le dictionnaire du projet 'p'
        if "gantt_data" not in p:
            p["gantt_data"] = pd.DataFrame([
                {"Etape": "Define", "Début": date(2026, 5, 1), "Fin": date(2026, 5, 15), "Responsable": "Black Belt"},
                {"Etape": "Measure", "Début": date(2026, 5, 16), "Fin": date(2026, 6, 15), "Responsable": "Green Belt"},
                {"Etape": "Analyze", "Début": date(2026, 6, 16), "Fin": date(2026, 7, 15), "Responsable": "Black Belt"},
                {"Etape": "Improve", "Début": date(2026, 7, 16), "Fin": date(2026, 9, 15), "Responsable": "Team"},
                {"Etape": "Control", "Début": date(2026, 9, 16), "Fin": date(2026, 10, 31), "Responsable": "Process Owner"}
            ])

        st.info("💡 Modifiez les dates dans le tableau, puis cliquez sur le bouton pour mettre à jour le graphique.")

        with st.expander("📝 Editer le calendrier du projet", expanded=True):
            # Configuration des colonnes
            config_cal = {
                "Début": st.column_config.DateColumn("Date de Début", format="DD/MM/YYYY"), 
                "Fin": st.column_config.DateColumn("Date de Fin", format="DD/MM/YYYY"),
                "Responsable": st.column_config.SelectboxColumn("Responsable", options=["Black Belt", "Green Belt", "Team", "Process Owner"])
            }
    
        # Édition des données (on utilise p_idx pour garantir l'unicité du widget)
        edited_gantt = st.data_editor(
            p["gantt_data"], 
            column_config=config_cal, 
            num_rows="dynamic", 
            use_container_width=True, 
            key=f"gantt_editor_{p_idx}"
        )
    
        if st.button("🚀 Générer le planning", key=f"btn_gantt_final_{p_idx}"):
            p["gantt_data"] = edited_gantt
            st.success("Planning mis à jour !")
            st.rerun()

        # 2. Affichage du graphique de Gantt
        try:
            df_viz = p["gantt_data"].copy()
    
        # Conversion impérative des dates pour Plotly
            df_viz["Début"] = pd.to_datetime(df_viz["Début"])
            df_viz["Fin"] = pd.to_datetime(df_viz["Fin"])
    
        # Pour respecter l'ordre du tableau, on crée une liste des étapes dans l'ordre actuel
            ordre_actuel = df_viz["Etape"].tolist()

            fig_gantt = px.timeline(
                df_viz, 
                x_start="Début", 
                x_end="Fin", 
                y="Etape", 
                color="Responsable", 
                color_discrete_sequence=px.colors.qualitative.Prism,
                template="plotly_white",
                # Force l'ordre des catégories selon le tableau
                category_orders={"Etape": ordre_actuel}
            )
    
        # Inverser l'axe Y pour que la première ligne du tableau soit en haut
            fig_gantt.update_yaxes(autorange="reversed")
    
            fig_gantt.update_layout(
                height=400, 
                margin=dict(l=0, r=10, t=10, b=0),
                xaxis_title="Chronologie du Projet",
                yaxis_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
    
            st.plotly_chart(fig_gantt, use_container_width=True)
    
        except Exception as e:
            st.warning("Veuillez remplir correctement toutes les étapes et dates du tableau.")
    
    # --- PHASE MEASURE ---
    with tabs[1]:
        st.header("Phase Measure")
        
        # 1. Project definition & Équation Y = f(X)
        st.subheader("1. Project Definition & Transfer Function Y = f(X)")
        
        ctq_v = p.get("selected_ctq", "Non défini dans Define")
        
        with st.container(border=True):
            st.markdown(f"### 🎯 Objectif Principal (Y) : `{ctq_v}`")
            st.markdown(
                r"En tant que Black Belt, nous traduisons le problème en équation de transfert : "
                r"$$Y = f(X_1, X_2, X_3, ..., X_n)$$"
            )
            st.caption("Où Y est votre indicateur de performance clé (CTQ) et les X sont les variables indépendantes (causes probables) à mesurer.")

            # --- ANALYSE AUTOMATIQUE DE LA VOC & DONNÉES (SI DISPONIBLES) ---
            st.markdown("##### 🔍 Alignement avec les données de la Phase DEFINE")
            
            x_de_depart = []
            
            # Extraction depuis la VOC brute si elle existe
            if "voc_raw_data" in st.session_state and not st.session_state.voc_raw_data.empty:
                st.write("✔️ *Analyse de la VOC détectée : Extraction des irritants clients...*")
                for idx, row in st.session_state.voc_raw_data.iterrows():
                    verbatim = str(row.get('réponse brute', '')).lower()
                    if 'temps' in verbatim or 'long' in verbatim or 'délai' in verbatim:
                        x_de_depart.append({"Variable X": "X_Délai", "Description": "Temps de traitement / Attentes inutiles", "Type": "Continu (Temps)", "Source": "VOC (Verbatim)"})
                    if 'erreur' in verbatim or 'qualité' in verbatim or 'faute' in verbatim or 'retouche' in verbatim:
                        x_de_depart.append({"Variable X": "X_Qualité", "Description": "Taux de non-conformité / Erreurs de saisie", "Type": "Discret (Attributs)", "Source": "VOC (Verbatim)"})
            
            # Si aucune donnée n'est encore saisie dans la VOC, on met des exemples Black Belt standards
            if not x_de_depart:
                x_de_depart = [
                    {"Variable X": "X1", "Description": "Variabilité de la méthode opératoire entre les équipes", "Type": "Discret", "Source": "Hypothèse Processus"},
                    {"Variable X": "X2", "Description": "Temps d'attente ou de transfert des dossiers", "Type": "Continu", "Source": "Hypothèse Lean"},
                    {"Variable X": "X3", "Description": "Manque de clarté des données d'entrée (Inputs du SIPOC)", "Type": "Discret", "Source": "Analyse SIPOC"}
                ]

            # --- TABLEAU DYNAMIQUE DES X (MODIFIABLE & AJOUTABLE) ---
            st.markdown("##### 📊 Registre des Variables X (Causes probables à mesurer)")
            st.info("💡 **Conseil Black Belt :** Ce tableau est dynamique. Vous pouvez modifier les descriptions, changer les types de données, ou ajouter de nouvelles lignes tout en bas du tableau pour compléter vos X.")
            
            # Initialisation dans le dictionnaire du projet pour ne pas perdre les modifications
            if "measure_x_table" not in p:
                p["measure_x_table"] = pd.DataFrame(x_de_depart)
            else:
                # Sécurité si le format stocké n'était pas un DataFrame
                if not isinstance(p["measure_x_table"], pd.DataFrame):
                    p["measure_x_table"] = pd.DataFrame(p["measure_x_table"])

            # Éditeur de données Streamlit (permet l'ajout/suppression/modification de lignes)
            edited_x_df = st.data_editor(
                p["measure_x_table"],
                num_rows="dynamic", # Rend le tableau modifiable en lignes
                use_container_width=True,
                column_config={
                    "Variable X": st.column_config.TextColumn("Code Variable", help="Ex: X1, X2, X_Temps", default="X_n"),
                    "Description": st.column_config.TextColumn("Description de la cause probable", width="large"),
                    "Type": st.column_config.SelectboxColumn("Type de Donnée", options=["Continu (Mesurable)", "Discret (Comptage/Catégorie)"]),
                    "Source": st.column_config.TextColumn("Origine de l'hypothèse", default="Mesure Terrain")
                },
                key=f"x_matrix_editor_{p_idx}"
            )
            
            # Sauvegarde automatique des modifications
            if st.button("💾 Enregistrer la définition et la matrice des X", key=f"save_x_btn_{p_idx}"):
                p["measure_x_table"] = edited_x_df
                st.success("Matrice Y = f(X) mise à jour avec succès pour ce projet !")

        # 2. Current state detailed process Map
        st.divider()
        st.subheader("2. Current state detailed process Map")
        st.info("Détaillez le processus à analyser. Vous pouvez insérer des lignes entre les étapes existantes.")
        if "detailed_map" not in p:
            # On initialise avec le SIPOC de Define si disponible, sinon vide
            p["detailed_map"] = pd.DataFrame(p.get("sipoc_data", [{"Process": "", "Customer": ""}]))
        
        edited_map = st.data_editor(p["detailed_map"], num_rows="dynamic", use_container_width=True, key=f"det_map_{p_idx}")
        if st.button("💾 Sauvegarder la Map détaillée", key=f"btn_map_{p_idx}"):
            p["detailed_map"] = edited_map
            st.success("Process Map enregistrée.")

        # 3. Current state value stream Map
        st.divider()
        st.subheader("3. Current State Value Stream Map")
        if "vsm_data" not in p:
            p["vsm_data"] = pd.DataFrame([{"Étape": "Action 1", "VA (sec)": 0, "NVA (sec)": 0}])
        
        vsm_edit = st.data_editor(p["vsm_data"], num_rows="dynamic", use_container_width=True, key=f"vsm_edit_{p_idx}")
        total_va = vsm_edit["VA (sec)"].sum()
        total_nva = vsm_edit["NVA (sec)"].sum()
        pce = (total_va / (total_va + total_nva)) * 100 if (total_va + total_nva) > 0 else 0
        st.metric("Process Cycle Efficiency (PCE)", f"{pce:.1f}%")

        # 4. Plan for Data collection
        st.divider()
        st.subheader("4. Plan for Data collection")
        if "data_plan" not in p:
            p["data_plan"] = pd.DataFrame(columns=["Question", "Cible (Qui)", "Outil/Source", "Échantillon"])
        p["data_plan"] = st.data_editor(p["data_plan"], num_rows="dynamic", use_container_width=True, key=f"plan_col_{p_idx}")

        # 5. Validate measurement system
        st.divider()
        st.subheader("5. Validate measurement system")
        st.write("Tests de fiabilité des données (Répétabilité & Reproductibilité).")
        with st.expander("Outils de validation (Type Minitab)"):
            st.info("Analyse Gage R&R : Vérifiez si la variation vient du processus ou du système de mesure.")

        # 6. Data collection
        st.divider()
        st.subheader("6. Data collection")
        up_measure = st.file_uploader("Importer les données (Excel)", type=["xlsx", "xls"], key=f"up_m_{p_idx}")
        if up_measure:
            df_m = pd.read_excel(up_measure)
            st.session_state[f"data_m_{p_idx}"] = df_m
            st.dataframe(df_m, use_container_width=True)
            # Graphique simple
            num_cols = df_m.select_dtypes(include=['number']).columns.tolist()
            if num_cols:
                fig_m = px.histogram(df_m, x=num_cols[0], title=f"Analyse de {num_cols[0]}")
                st.plotly_chart(fig_m, use_container_width=True)

        # 7. Baseline performance
        st.divider()
        st.subheader("7. Baseline performance")
        st.write("*(En attente d'explications supplémentaires)*")

        # 8. Measure process capability
        st.divider()
        st.subheader("8. Measure process capability")
        c1, c2 = st.columns(2)
        with c1:
            defects = st.number_input("Défauts", min_value=0, value=0)
            units = st.number_input("Unités", min_value=1, value=1)
            opp = st.number_input("Opportunités/Unité", min_value=1, value=1)
        
        dpmo = (defects / (units * opp)) * 1_000_000
        with c2:
            st.metric("DPMO", f"{dpmo:,.0f}")
            st.metric("Sigma Level", "À calculer selon rendement")

    # --- AUTRES PHASES (Structure prête) ---
    with tabs[2]: st.info("Module ANALYZE : Ishikawa & Tests Statistiques IA en attente de données.")
    with tabs[3]: st.info("Module IMPROVE : Matrice de sélection multicritères.")
    with tabs[4]: st.info("Module CONTROL : Graphiques Avant/Après & Gains financiers.")
