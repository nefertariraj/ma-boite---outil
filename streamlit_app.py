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

    tabs = st.tabs(["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"])

    # --- PHASE DEFINE ---
    with tabs[0]:
        st.header("Phase Define")
        
        # 1. Problème & CTQ
        st.subheader("1. Énoncé du Problème & CTQ")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p title="X correspond aux causes">Décrivez le problème en détail :</p>', unsafe_allow_html=True)
            # Utilisation de .get pour éviter le KeyError si le projet est ancien
            p_input = st.text_area("Saisie libre", value=p.get("problem", ""), height=150, key=f"prob_in_{st.session_state.current_project_idx}")
            
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
                new_val = st.text_input("Libellé du CTQ", value=p["selected_ctq"], key=f"edit_ctq_{st.session_state.current_project_idx}")
                
                if new_val != p["selected_ctq"]:
                    p["selected_ctq"] = new_val
                    st.rerun()
                st.info(f"**CTQ validé :** {p['selected_ctq']}")

        # 2. Équipe Projet
        st.divider()
        st.subheader("2. Équipe Projet")
        team_key = f"editor_team_{st.session_state.current_project_idx}"
        edited_team = st.data_editor(
            p.get("team_data", [{"Poste": "", "Nom": ""}]), 
            num_rows="dynamic",
            use_container_width=True,
            key=team_key
        )
        if st.button("✅ Valider l'équipe", key=f"save_team_{st.session_state.current_project_idx}"):
            p["team_data"] = edited_team
            st.success("Équipe enregistrée !")
            st.rerun()

        # --- 4. BÉNÉFICES ATTENDUS & MATRICE D'OPPORTUNITÉ ---
    st.divider()
    st.subheader("4. Bénéfices Attendus & Matrice d'Opportunité")

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
        st.subheader("7. Stakeholder Analysis (Matrice d'adhésion)")

        # Initialisation des données si elles n'existent pas
        if "stakeholders" not in p:
            # On décale vers la droite ici
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
            # On décale aussi vers la droite ici
            p["stakeholders"] = edited_stakeholders
            st.success("Analyse sauvegardée !")

       # --- 5. SIPOC & FLUX CROISÉ COMPACT ---
    p_idx = st.session_state.get('current_project_idx')

    if p_idx is not None:
        p = st.session_state.projects[p_idx]
        
        st.divider()
        st.subheader("5. SIPOC & Flux de processus")

        COLONNES_SIPOC = ["Supplier", "Input", "Process", "Output", "Customer"]
        
        if "sipoc_data" not in p or not isinstance(p["sipoc_data"], list):
            p["sipoc_data"] = [dict.fromkeys(COLONNES_SIPOC, "")]

        with st.form(key=f"form_sipoc_compact_{p_idx}"):
            df_init = pd.DataFrame(p["sipoc_data"])
            for col in COLONNES_SIPOC:
                if col not in df_init.columns:
                    df_init[col] = ""
            
            edited_sipoc = st.data_editor(
                df_init[COLONNES_SIPOC],
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_sipoc_comp_{p_idx}",
                column_config={c: st.column_config.TextColumn(c) for c in COLONNES_SIPOC}
            )
            submit_sipoc = st.form_submit_button("✅ Actualiser le flux")

        if submit_sipoc:
            p["sipoc_data"] = edited_sipoc.to_dict('records')
            st.rerun()

        df_viz = pd.DataFrame(p["sipoc_data"])
        df_viz = df_viz[(df_viz["Process"].astype(str).str.strip() != "") & 
                        (df_viz["Customer"].astype(str).str.strip() != "")]
        
        if not df_viz.empty:
            st.write("---")
            acteurs = df_viz["Customer"].unique().tolist()
            cols = st.columns(len(acteurs))
            
            for i, acteur in enumerate(acteurs):
                cols[i].markdown(f"<p style='font-weight:bold; font-size:14px; margin-bottom:0;'>{acteur.upper()}</p>", unsafe_allow_html=True)
                cols[i].divider()

            # Rendu des tâches
            for idx, row in df_viz.iterrows():
                current_col = acteurs.index(row["Customer"])
                
                # Création d'une ligne de hauteur réduite
                row_cols = st.columns(len(acteurs))
                
                # Vérification de l'action suivante pour la flèche
                has_next = idx < len(df_viz) - 1
                if has_next:
                    next_actor = df_viz.iloc[idx + 1]["Customer"]
                    next_col = acteurs.index(next_actor)

                for i in range(len(acteurs)):
                    with row_cols[i]:
                        if i == current_col:
                            # Affichage de la tâche dans un bloc compact
                            st.markdown(f"""
                                <div style="border: 1px solid #e0e0e0; border-radius: 5px; padding: 5px 10px; background-color: #f8f9fa; font-size: 14px;">
                                    {row['Process']}
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Gestion des flèches de liaison
                            if has_next:
                                if next_col == current_col:
                                    # Flèche vers le bas (même acteur)
                                    st.markdown("<p style='text-align:center; margin:0; line-height:1;'>↓</p>", unsafe_allow_html=True)
                                elif next_col > current_col:
                                    # Flèche vers la droite
                                    st.markdown("<p style='text-align:right; margin:0; line-height:1;'>➡</p>", unsafe_allow_html=True)
                                else:
                                    # Flèche vers la gauche
                                    st.markdown("<p style='text-align:left; margin:0; line-height:1;'>⬅</p>", unsafe_allow_html=True)
                        else:
                            # Espace minimal pour les colonnes vides
                            st.write("")

  # --- 6. VOICE OF CUSTOMER (VOC) : VERSION FINALE SÉCURISÉE ---
    st.divider()
    st.header("🎯 Voice of Customer (VOC) - Flux Black Belt")

    # Initialisation de la session
    if 'p' not in locals(): p = st.session_state

    # Initialisation des structures de données si elles n'existent pas
    if "voc_questions" not in p:
        p["voc_questions"] = [
            "Qu’est ce qui vous fait perdre du temps ?",
            "Qu’est ce qui vous oblige à refaire une tâche ?",
            "A quel moment le processus devient pénible ?",
            "Qu’est ce qui vous énerve le plus ?",
            "Si vous pouviez changer une seule chose ?"
        ]
    if "voc_raw_data" not in p:
        p["voc_raw_data"] = pd.DataFrame(columns=["client", "question", "réponse brute"])

    # --- 1. ÉLABORATION DU QUESTIONNAIRE ---
    st.subheader("1. Élaboration du Questionnaire")
    with st.expander("📝 Configurer les questions", expanded=False):
        for i in range(5):
            p["voc_questions"][i] = st.text_input(f"Question {i+1}", value=p["voc_questions"][i], key=f"q_final_v7_{i}")

    # --- 2. COLLECTE DES DONNÉES ---
    st.write("---")
    st.subheader("2. Collecte des Données")
    
    # Zone d'importation
    up_file = st.file_uploader("Importer un fichier Excel", type=["xlsx", "xls"], key="uploader_v7")
    
    if up_file:
        # On utilise un bouton unique pour l'import pour éviter les boucles infinies
        if st.button("📥 Charger les données du fichier"):
            try:
                df_imp = pd.read_excel(up_file).fillna("")
                df_imp.columns = [c.lower().strip() for c in df_imp.columns]
                
                # Identification des colonnes
                c_col = next((c for c in df_imp.columns if "client" in c or "nom" in c), df_imp.columns[0])
                q_col = next((c for c in df_imp.columns if "quest" in c), None)
                r_col = next((c for c in df_imp.columns if "rép" in c or "verbatim" in c or "brute" in c), df_imp.columns[-1])
                
                new_rows = pd.DataFrame({
                    "client": df_imp[c_col].astype(str),
                    "question": df_imp[q_col].astype(str) if q_col else "Import Excel",
                    "réponse brute": df_imp[r_col].astype(str)
                })
                
                p["voc_raw_data"] = pd.concat([p["voc_raw_data"], new_rows], ignore_index=True)
                st.success("Données ajoutées au tableau ci-dessous.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la lecture : {e}")

    # Le tableau est le réceptacle central
    # On capture les changements de l'utilisateur en direct
    edited_df = st.data_editor(
        p["voc_raw_data"],
        num_rows="dynamic",
        use_container_width=True,
        key="v7_data_editor"
    )
    
    # On synchronise le dictionnaire p avec l'éditeur
    if edited_df is not None:
        p["voc_raw_data"] = edited_df

    # --- 3. ANALYSE THÉMATIQUE & CTQ ---
    st.write("---")
    st.subheader("3. Analyse Thématique (Affinity Diagram) & CTQ")
    
    if st.button("🧠 Lancer l'Analyse Thématique"):
        df_src = p["voc_raw_data"]
        
        if not df_src.empty:
            total = len(df_src)
            # Dictionnaire de mapping pour l'analyse
            mapping_lean = [
                {"th": "Délais (Lead Time)", "kw": ["temps", "long", "attente", "lent", "délai", "retard", "planning"], "ex": "Gaspillage d'attente (Muda)", "ctq": "Délai de réponse < 2h"},
                {"th": "Qualité (Non-Conformité)", "kw": ["refaire", "erreur", "trompé", "fautes", "recommencer", "qualité", "mauvais"], "ex": "Retouches et défauts", "ctq": "First Pass Yield 100%"},
                {"th": "Complexité (Pénibilité)", "kw": ["pénible", "lourd", "difficile", "compliqué", "clics", "fatigue", "pression"], "ex": "Processus lourd (Muri)", "ctq": "Processus en 3 clics max"},
                {"th": "Outils (Systèmes)", "kw": ["énerve", "logiciel", "bug", "système", "outil", "ordinateur", "panne"], "ex": "Instabilité des moyens", "ctq": "Uptime IT > 99.9%"},
                {"th": "Flux d'information", "kw": ["info", "manque", "comprendre", "flou", "changé", "sais pas", "échanges"], "ex": "Variabilité (Mura)", "ctq": "Standard d'info digitalisé"}
            ]

            final_res = []
            for m in mapping_lean:
                # Calcul basé sur le contenu actuel du tableau
                count = sum(1 for r in df_src["réponse brute"].astype(str).lower() if any(k in r for k in m["kw"]))
                final_res.append({
                    "thème des irritants": m["th"],
                    "explication": m["ex"],
                    "nombre d'occurrence": count,
                    "pourcentage": f"{(count/total)*100:.1f}%" if total > 0 else "0%",
                    "CTQ": m["ctq"],
                    "raw_count": count
                })

            # Sauvegarde persistante de l'analyse triée
            p["voc_analysis_result"] = pd.DataFrame(final_res).sort_values("raw_count", ascending=False).drop(columns=["raw_count"])
        else:
            st.warning("⚠️ Le tableau de collecte est vide.")

    # Affichage permanent si l'analyse a été lancée
    if "voc_analysis_result" in p:
        st.table(p["voc_analysis_result"])

        # --- 4. PROPOSITIONS D'AMÉLIORATION ---
        st.write("---")
        st.subheader("4. Propositions d'Amélioration (Expertise Black Belt)")
        
        # On récupère le thème dominant
        main_theme = p["voc_analysis_result"].iloc[0]["thème des irritants"]
        st.info(f"🎯 **Priorité identifiée : {main_theme}**")

        stratégies = {
            "Délais (Lead Time)": [
                "Implémenter un **système Kanban** pour réguler le flux et supprimer les attentes.",
                "Réaliser un **chantier SMED** pour réduire les temps de changement de tâche.",
                "Aligner la production sur le **Takt Time** (cadence client).",
                "Automatiser les transferts de dossiers via un **Workflow RPA**."
            ],
            "Qualité (Non-Conformité)": [
                "Déployer des **Poka-Yoke** (anti-erreurs) sur les formulaires de saisie.",
                "Standardiser les processus via des **SOP visuels** univoques.",
                "Lancer un **cycle PDCA** sur la cause racine du défaut le plus fréquent.",
                "Mettre en place un **Autocontrôle** systématique en fin de chaque étape."
            ],
            "Complexité (Pénibilité)": [
                "Appliquer le **5S Digital** pour épurer les interfaces et fichiers.",
                "Réduire la **Non-Valeur Ajoutée (NVA)** en supprimant les doubles validations.",
                "Revoir l'ergonomie du poste pour limiter la **charge cognitive**.",
                "Simplifier le processus en fusionnant les étapes à faible impact."
            ]
        }

        # Idées par défaut si le thème sort du cadre standard
        ideas = stratégies.get(main_theme, ["Plan d'action Kaizen", "Standardisation", "Management Visuel", "Formation"])

        c1, c2 = st.columns(2)
        with c1:
            st.success(f"💡 **Idée 1 :** {ideas[0]}")
            st.success(f"💡 **Idée 2 :** {ideas[1]}")
        with c2:
            st.success(f"💡 **Idée 3 :** {ideas[2]}")
            st.success(f"💡 **Idée 4 :** {ideas[3]}")
  
    # --- PHASE MEASURE ---
    with tabs[1]:
        st.header("Phase Measure")
        st.write(f"**CTQ Sélectionné :** {p.get('selected_ctq', 'Non défini')}")
        
        st.subheader("Value Stream Mapping (VSM)")
        st.write("Indiquez les indicateurs par étape :")
        vsm_data = pd.DataFrame({
            "Étape": ["Etape 1", "Etape 2"],
            "Cycle Time": [0, 0],
            "Wait Time": [0, 0],
            "VA": [0, 0],
            "NVA": [0, 0]
        })
        st.data_editor(vsm_data, use_container_width=True)
        st.button("Générer le flux visuel")

    # --- AUTRES PHASES (Structure prête) ---
    with tabs[2]: st.info("Module ANALYZE : Ishikawa & Tests Statistiques IA en attente de données.")
    with tabs[3]: st.info("Module IMPROVE : Matrice de sélection multicritères.")
    with tabs[4]: st.info("Module CONTROL : Graphiques Avant/Après & Gains financiers.")
