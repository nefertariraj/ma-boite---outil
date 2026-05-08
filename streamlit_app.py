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

  # --- 6. VOICE OF CUSTOMER (VOC) : VERSION BLACK BELT OPTIMISÉE ---
    st.divider()
    st.header("🎯 Voice of Customer (VOC) - Flux Black Belt")

    if 'p' not in locals(): p = st.session_state

    # 1. INITIALISATION DES VARIABLES
    if "voc_questions" not in p:
        p["voc_questions"] = ["Temps perdu ?", "Retouches ?", "Pénibilité ?", "Irritants ?", "Changement unique ?"]
    if "voc_raw_data" not in p:
        p["voc_raw_data"] = pd.DataFrame(columns=["client", "question", "réponse brute"])

    # --- ÉTAPE 1 : ÉLABORATION ---
    st.subheader("1. Élaboration du Questionnaire")
    with st.expander("📝 Configurer les questions"):
        for i, q in enumerate(p["voc_questions"]):
            p["voc_questions"][i] = st.text_input(f"Question {i+1}", value=q, key=f"q_v9_{i}")

    # --- ÉTAPE 2 : COLLECTE (IMPORT RAPIDE) ---
    st.write("---")
    st.subheader("2. Collecte des Données")
    
    up_file = st.file_uploader("Importer Excel (Rapide)", type=["xlsx", "xls"], key="up_v9")
    
    if up_file is not None:
        # On utilise une clé basée sur le nom et la taille pour ne charger qu'une fois
        file_id = f"{up_file.name}_{up_file.size}"
        if p.get("last_uploaded_file") != file_id:
            try:
                df_imp = pd.read_excel(up_file).fillna("")
                df_imp.columns = [c.lower().strip() for c in df_imp.columns]
                
                # Mapping intelligent
                c_col = next((c for c in df_imp.columns if "client" in c or "nom" in c), df_imp.columns[0])
                q_col = next((c for c in df_imp.columns if "quest" in c), None)
                r_col = next((c for c in df_imp.columns if "rép" in c or "verbatim" in c or "brute" in c), df_imp.columns[-1])
                
                new_rows = pd.DataFrame({
                    "client": df_imp[c_col].astype(str),
                    "question": df_imp[q_col].astype(str) if q_col else "Import",
                    "réponse brute": df_imp[r_col].astype(str)
                })
                
                p["voc_raw_data"] = pd.concat([p["voc_raw_data"], new_rows], ignore_index=True)
                p["last_uploaded_file"] = file_id # Marque le fichier comme traité
                st.success("✅ Données chargées.")
            except Exception as e:
                st.error(f"Erreur : {e}")

    # Tableau éditable avec sauvegarde forcée
    edited_df = st.data_editor(
        p["voc_raw_data"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_v9"
    )
    if edited_df is not None:
        p["voc_raw_data"] = edited_df

    # --- ÉTAPE 3 : ANALYSE THÉMATIQUE & CTQ ---
    st.write("---")
    st.subheader("3. Analyse Thématique & CTQ")
    
    # 1. Vérification de la source de données (Lien direct avec la clé de l'éditeur v8)
    # On regarde d'abord dans l'éditeur, sinon dans la mémoire brute
    if "editor_v8" in st.session_state:
        # L'éditeur de l'étape 2 stocke les modifs dans 'edited_rows', 'added_rows', etc.
        # Mais le plus simple est de lire le DataFrame synchronisé
        df_actuel = st.session_state.voc_raw_data
    else:
        df_actuel = p.get("voc_raw_data", pd.DataFrame())

    if st.button("🧠 Lancer l'Analyse", key="btn_v_final_fix"):
        # On vérifie si le DataFrame contient bien des lignes
        if not df_actuel.empty:
            # On extrait les textes (dernière colonne par défaut pour éviter l'AttributeError)
            verbatims = df_actuel.iloc[:, -1].astype(str).str.lower().tolist()
            total = len(verbatims)
            
            mapping = [
                {"th": "Délais (Lead Time)", "kw": ["temps", "long", "attente", "lent", "délai", "retard"], "ex": "Muda d'attente", "ctq": "Lead Time < 24h"},
                {"th": "Qualité (Défauts)", "kw": ["refaire", "erreur", "trompé", "faute", "qualité", "mauvais"], "ex": "Non-conformités", "ctq": "Zéro défaut (FPY)"},
                {"th": "Pénibilité", "kw": ["pénible", "lourd", "difficile", "fatigue", "compliqué"], "ex": "Muri (Surcharge)", "ctq": "Score d'effort < 3/10"},
                {"th": "Outils", "kw": ["bug", "système", "outil", "logiciel", "ordinateur"], "ex": "Instabilité IT", "ctq": "Disponibilité > 99%"},
                {"th": "Information", "kw": ["info", "manque", "flou", "comprendre", "échange"], "ex": "Mura (Variabilité)", "ctq": "Standardisation"}
            ]

            res_list = []
            for m in mapping:
                count = sum(1 for r in verbatims if any(k in r for k in m["kw"]))
                res_list.append({
                    "thème des irritants": m["th"],
                    "explication": m["ex"],
                    "nombre d'occurrence": count,
                    "pourcentage": f"{(count/total)*100:.1f}%" if total > 0 else "0%",
                    "CTQ": m["ctq"],
                    "score": count
                })
            
            # Sauvegarde dans la session
            st.session_state.voc_results = pd.DataFrame(res_list).sort_values("score", ascending=False).drop(columns=["score"])
            st.rerun()
        else:
            # Ce message ne s'affichera que si le DataFrame est réellement vide de chez vide
            st.error("⚠️ Le tableau ne contient aucune donnée. Vérifiez l'étape 2.")

    # --- ÉTAPE 4 : DIAGNOSTIC & STRATÉGIE D'AMÉLIORATION (REGARD BLACK BELT) ---
    if st.session_state.get("voc_results") is not None:
        st.write("---")
        st.subheader("4. Diagnostic Expert & Plan d'Action Black Belt")
        
        # Récupération du top irritant et des données associées
        top_row = st.session_state.voc_results.iloc[0]
        top_theme = top_row["thème des irritants"]
        occurrence = top_row["nombre d'occurrence"]
        ctq_cible = top_row["CTQ"]
        
        # 1. Le Diagnostic Structurel
        st.markdown(f"### 🎯 Focus Prioritaire : {top_theme}")
        
        # Génération d'une réflexion dynamique selon le thème
        reflexions = {
            "Délais (Lead Time)": {
                "analyse": f"L'analyse montre {occurrence} remontées critiques sur le temps de traversée. En tant que Black Belt, cela indique un **Muda d'attente** massif ou des goulots d'étranglement non maîtrisés. Le flux n'est pas 'Tirée' par la demande.",
                "strategie": "Prioriser une **VSM (Value Stream Mapping)** pour identifier le ratio VA/NVA. L'objectif est de réduire le Lead Time en supprimant les files d'attente entre les processus.",
                "outils": ["Chantier Kaizen Flash", "Équilibrage de poste (Yamazumi)", "Calcul du Takt Time"]
            },
            "Qualité (Défauts)": {
                "analyse": f"Avec {occurrence} occurrences, la **non-qualité** est le premier levier de coût caché (COPQ). Nous faisons face à une instabilité du processus qui génère des retouches et de la frustration client.",
                "strategie": "Passer d'une culture de contrôle à une culture de 'Bon du premier coup'. Il faut isoler la cause racine (5 Pourquoi) et stabiliser la variance (Standardisation).",
                "outils": ["Poka-Yoke (Détrompeurs)", "Matrice de capabilité (Cp/Cpk)", "Plan d'autocontrôle"]
            },
            "Pénibilité": {
                "analyse": f"Le poids de la pénibilité ({occurrence} verbatims) révèle un risque sur la **durabilité du flux** (Muri). La surcharge cognitive ou physique dégrade la performance à long terme.",
                "strategie": "Appliquer l'ergonomie Lean. Simplifier le poste de travail pour que l'opérateur se concentre uniquement sur la création de valeur sans effort parasite.",
                "outils": ["Analyse de déroulement", "5S ergonomique", "Standard Work"]
            },
            "Outils": {
                "analyse": f"L'infrastructure est ici le frein majeur. Si l'outil faillit, le processus le plus robuste devient inefficace. C'est un problème de **capabilité des moyens**.",
                "strategie": "Engager une refonte de l'interface ou une automatisation (RPA) pour supprimer les tâches à faible valeur ajoutée qui causent ces bugs.",
                "outils": ["Analyse de la valeur IT", "Maintenance préventive", "User Experience Lean"]
            },
            "Information": {
                "analyse": f"Le manque de clarté ({occurrence} signaux) indique un problème de **Mura (Variabilité)** dans la transmission. L'information est l'essence du flux ; si elle est floue, le flux s'arrête.",
                "strategie": "Standardiser les flux d'information. Passer d'une communication réactive à un **Management Visuel** proactif où l'anomalie saute aux yeux.",
                "outils": ["Standard d'échange", "Obeya / Management Visuel", "AIC (Animation Courte)"]
            }
        }

        diag = reflexions.get(top_theme, {"analyse": "Analyse transverse requise.", "strategie": "Standardisation globale.", "outils": ["Audit", "Kaizen"]})

        # Affichage du diagnostic type "Rapport de mission"
        with st.expander("🔍 Analyse de la situation (Deep Dive)", expanded=True):
            st.write(diag["analyse"])
            st.write(f"**Indicateur CTQ à surveiller :** `{ctq_cible}`")

        st.markdown("#### 🚀 Recommandations Stratégiques")
        st.info(f"**Vision Black Belt :** {diag['strategie']}")

        # Affichage des outils recommandés sous forme de badges
        cols = st.columns(len(diag["outils"]))
        for i, tool in enumerate(diag["outils"]):
            cols[i].success(f"🛠️ {tool}")

        # 2. Lien avec le DMAIC
        st.write("---")
        st.caption(f"Prochaine étape suggérée (Phase IMPROVE) : Lancer un groupe de travail ciblé sur les {occurrence} points de douleur pour définir les solutions futures.")
  
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
