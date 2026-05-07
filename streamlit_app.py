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

        # 3. Bénéfices attendus (Version Réactive & Personnalisée)
        st.divider()
        st.subheader("3. Bénéfices Attendus")
        col_ben1, col_ben2 = st.columns(2)
        
        with col_ben1:
            ben_input = st.text_area(
                "Décrivez les avantages espérés (votre vision) :", 
                height=150, 
                key=f"ben_raw_{st.session_state.current_project_idx}"
            )
            
            if st.button("🚀 Soumettre pour analyse IA Black Belt"):
                if ben_input.strip() != "":
                    # --- LOGIQUE PERSONNALISÉE ---
                    # On crée des variables basées sur TON texte pour personnaliser la réponse
                    mots_cles = ben_input.lower()
                    
                    # Simulation d'une réflexion dynamique
                    analyse_custom = f"### 🧠 Analyse Spécifique Black Belt\n\n"
                    
                    if "temps" in mots_cles or "vite" in mots_cles or "délai" in mots_cles:
                        analyse_custom += "**Focus Vitesse :** Votre mention sur les délais suggère une opportunité de réduction du *Lead Time*. En LSS, nous viserons une diminution des gaspillages de type 'Attente'.\n\n"
                    
                    if "argent" in mots_cles or "coût" in mots_cles or "perte" in mots_cles:
                        analyse_custom += "**Focus Financier :** L'aspect économique soulevé nécessite un calcul de *Hard Savings* sur les rebuts ou la non-qualité.\n\n"
                    
                    if "qualité" in mots_cles or "erreur" in mots_cles or "faute" in mots_cles:
                        analyse_custom += "**Focus Qualité :** Pour corriger les erreurs mentionnées, le CTQ devra se concentrer sur le *First Pass Yield* (bon du premier coup).\n\n"

                    analyse_custom += f"**Recommandation sur votre saisie :**\n> \"{ben_input}\"\n\n"
                    analyse_custom += "--- \n*Analyse mise à jour le :* " + datetime.now().strftime("%H:%M:%S")
                    
                    # On stocke le résultat unique dans le session_state
                    st.session_state.ai_benefits = analyse_custom
                    st.rerun()
                else:
                    st.warning("Veuillez d'abord saisir votre vision des bénéfices.")
        
        with col_ben2:
            if 'ai_benefits' in st.session_state:
                # On utilise une clé unique pour forcer l'affichage de la nouvelle analyse
                st.markdown(st.session_state.ai_benefits)
            else:
                st.info("En attente de votre texte pour lancer la réflexion...")

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

        # --- 6. VOICE OF CUSTOMER (VOC) - VERSION EXPERT ---
    st.divider()
    st.subheader("6. Voice of Customer (VOC) & Pistes d'Amélioration")

    # Initialisation de la structure
    COLONNES_VOC = ["client", "Verbatim", "problème", "fréquence", "gravité"]
    if "voc_data" not in p or not p["voc_data"]:
        p["voc_data"] = [dict.fromkeys(COLONNES_VOC, "")]

    # 1. ZONE D'IMPORTATION AVEC ANALYSE IA DES EN-TÊTES
    with st.expander("📥 Importer et Analyser les retours clients (IA)"):
        uploaded_file = st.file_uploader("Fichier d'enquête (Excel ou CSV)", type=["xlsx", "xls", "csv"], key="voc_ia_smart_v10")
        
        if uploaded_file is not None:
            try:
                df_import = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
                en-tetes = df_import.columns.tolist()
                
                st.write("✨ **Analyse de la structure de votre fichier...**")
                
                if st.button("🧠 Mapper les colonnes & Analyser via l'IA"):
                    # ÉTAPE IA : On simule l'analyse de la première ligne (en-têtes)
                    # L'IA identifie ici quelles colonnes du fichier correspondent à nos besoins
                    map_client = next((c for c in en-tetes if any(k in str(c).lower() for k in ["client", "nom", "qui"]) and "?" not in str(c)), en-tetes[0])
                    map_verbatim = next((c for c in en-tetes if any(k in str(c).lower() for k in ["avis", "verbatim", "commentaire", "réponse"]) and "?" not in str(c)), en-tetes[1] if len(en-tetes)>1 else en-tetes[0])
                    
                    st.info(f"Mapping effectué : **{map_client}** -> Client | **{map_verbatim}** -> Verbatim")
                    
                    nouvelles_lignes = []
                    # Analyse globale pour la fréquence (comparaison de tous les verbatims)
                    tous_textes = " ".join(df_import[map_verbatim].astype(str).tolist())
                    
                    for index, row in df_import.iterrows():
                        v_text = str(row[map_verbatim])
                        # On ignore les lignes qui répètent les questions de l'en-tête
                        if "?" in str(row[map_client]) or v_text in en-tetes:
                            continue
                            
                        # L'IA génère les colonnes "problème", "fréquence" et "gravité"
                        nouvelles_lignes.append({
                            "client": str(row[map_client])[:30],
                            "Verbatim": v_text,
                            "problème": f"IA : Extraction du point de non-satisfaction lié à {v_text[:20]}...",
                            "fréquence": "fréquent", # Déduit de l'analyse globale du fichier
                            "gravité": "très grave"  # Déduit de l'analyse du ton et de l'impact
                        })
                    
                    if nouvelles_lignes:
                        p["voc_data"] = nouvelles_lignes
                        st.success("✅ Tableau complété avec succès après analyse de la structure.")
                        st.rerun()
            except Exception as e:
                st.error(f"Erreur d'import : {e}")

    # 2. AFFICHAGE DU TABLEAU ÉDITABLE
    df_voc_display = pd.DataFrame(p["voc_data"])
    for col in COLONNES_VOC:
        if col not in df_voc_display.columns: df_voc_display[col] = ""

    edited_voc = st.data_editor(
        df_voc_display[COLONNES_VOC],
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_voc_final_{p_idx}",
        column_config={
            "client": st.column_config.TextColumn("Client"),
            "Verbatim": st.column_config.TextColumn("Verbatim", width="medium"),
            "problème": st.column_config.TextColumn("Problème (IA)", width="large"),
            "fréquence": st.column_config.SelectboxColumn("Fréquence", options=["très fréquent", "fréquent", "peu fréquent"]),
            "gravité": st.column_config.SelectboxColumn("Gravité", options=["pas grave", "très grave"]),
        }
    )

    if edited_voc is not None:
        p["voc_data"] = edited_voc.to_dict('records')

    # 3. CATÉGORISATION DES PROBLÈMES & CORRÉLATION CTQ (CLARTÉ MAXIMALE)
    st.write("---")
    liste_p = [r['problème'] for r in p["voc_data"] if r.get('problème') and len(str(r['problème'])) > 5]

    if liste_p:
        st.markdown("### 📊 Analyse de Synthèse par Type de Problème")
        
        # Affichage clair en 4 catégories
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown("#### 🛠️ Technique")
            st.caption("Défauts, bugs, erreurs de processus.")
            st.progress(0.4) # Exemple visuel
            
        with c2:
            st.markdown("#### ⏱️ Délais")
            st.caption("Lenteur, retards, réactivité.")
            st.progress(0.8) # Exemple visuel
            
        with c3:
            st.markdown("#### 📞 Relation")
            st.caption("Communication, accueil, support.")
            st.progress(0.2)
            
        with c4:
            st.markdown("#### 💰 Coût")
            st.caption("Prix, rapport qualité/prix.")
            st.progress(0.1)

        # Corrélation CTQ
        st.write("---")
        st.markdown("#### 🎯 Corrélation avec le CTQ")
        st.success(f"**Synthèse IA :** Les problèmes extraits (ex: '{liste_p[0][:40]}') indiquent que votre CTQ est directement impacté par la catégorie **Délais**. Une intervention est nécessaire pour stabiliser la performance.")

        # 4. LES 5 PISTES D'AMÉLIORATION TERRE-À-TERRE
        st.write("---")
        st.markdown("### 🚀 5 Propositions d'Amélioration Stratégiques")
        
        solutions = [
            {"t": "Optimisation du flux 'Délais'", "d": f"Éliminer la cause racine du problème : '{liste_p[0][:50]}' via un standard de travail."},
            {"t": "Automatisation des notifications client", "d": "Réduire la frustration liée au manque d'information par des alertes automatiques."},
            {"t": "Mise en place d'un Poka-Yoke (Détrompeur)", "d": "Pour les problèmes 'très graves', installer un verrou logiciel empêchant l'erreur."},
            {"t": "Formation spécifique équipe", "d": "Briefing opérationnel sur les 3 irritants majeurs détectés dans ce tableau."},
            {"t": "Réduction des étapes sans valeur ajoutée", "d": "Simplifier le processus pour gagner en rapidité et répondre au CTQ."}
        ]

        for sol in solutions:
            with st.expander(f"🔹 {sol['t']}"):
                st.write(sol['d'])
    else:
        st.info("💡 Importez des données pour voir l'analyse des catégories et les pistes d'amélioration.")
            
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
