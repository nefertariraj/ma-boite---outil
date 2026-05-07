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

       # --- 5. SIPOC & Flowchart ---
p_idx = st.session_state.get('current_project_idx')

if p_idx is not None:
    # CETTE LIGNE EST LA PLUS IMPORTANTE : elle définit 'p'
    p = st.session_state.projects[p_idx]
    
    st.divider()
    st.subheader("5. SIPOC & Flux de processus")

    # Maintenant Python sait ce qu'est 'p', donc cette ligne ne plantera plus :
    if "sipoc_data" not in p or not isinstance(p["sipoc_data"], list) or not p["sipoc_data"]:
        p["sipoc_data"] = [
            {"Supplier": "", "Input": "", "Process": "", "Output": "", "Customer": ""}
        ]

    # Le reste du formulaire
    with st.form(key=f"sipoc_form_final_{p_idx}"):
        st.info("Saisissez les étapes ci-dessous.")
        
        column_config = {
            "Supplier": st.column_config.TextColumn("Fournisseur"),
            "Input": st.column_config.TextColumn("Entrée"),
            "Process": st.column_config.TextColumn("Processus"),
            "Output": st.column_config.TextColumn("Sortie"),
            "Customer": st.column_config.TextColumn("Client"),
        }

        edited_sipoc = st.data_editor(
            p["sipoc_data"],
            num_rows="dynamic",
            key=f"sipoc_editor_final_{p_idx}",
            use_container_width=True,
            column_config=column_config,
            column_order=("Supplier", "Input", "Process", "Output", "Customer")
        )
        
        submit_sipoc = st.form_submit_button("✅ Enregistrer et Générer le Schéma")

    if submit_sipoc:
        p["sipoc_data"] = edited_sipoc
        st.success("Données SIPOC mises à jour !")
        st.rerun()

    # 3. Traitement de la validation
    if submit_sipoc:
        p["sipoc_data"] = edited_sipoc
        st.success("Données SIPOC mises à jour !")
        st.rerun()

    # 4. Génération du Schéma Graphviz
    # On vérifie qu'il y a des données exploitables (au moins un Process et un Customer)
    df_chart = pd.DataFrame(p["sipoc_data"])
    
    # On nettoie les lignes vides pour le graphique
    if not df_chart.empty and 'Process' in df_chart.columns:
        df_clean = df_chart.dropna(subset=['Process', 'Customer'])
        df_clean = df_clean[(df_clean['Process'] != "") & (df_clean['Customer'] != "")]

        if not df_clean.empty:
            st.write("### 📉 Aperçu du Flux (Swimlanes)")
            
            def generate_viz(df):
                dot = """
                digraph G {
                    rankdir=TB;
                    newrank=true; 
                    node [shape=rect, style=filled, fillcolor="#F9F9F9", fontname="Arial", fontsize="10"];
                    edge [color="#2D3748", penwidth=1.5];
                """
                # Groupement par Customer (Swimlanes)
                actors = df['Customer'].unique()
                for i, actor in enumerate(actors):
                    dot += f'    subgraph cluster_{i} {{\n'
                    dot += f'        label = "{actor.upper()}";\n'
                    dot += f'        style=filled; color="#F1F5F9"; fontname="Arial-Bold";\n'
                    
                    steps = df[df['Customer'] == actor]
                    for idx, row in steps.iterrows():
                        dot += f'        "step_{idx}" [label="{row["Process"]}"];\n'
                    dot += '    }\n'
                
                # Liens chronologiques
                indices = df.index.tolist()
                for j in range(len(indices) - 1):
                    dot += f'    "step_{indices[j]}" -> "step_{indices[j+1]}";\n'
                
                dot += "}"
                return dot

            try:
                st.graphviz_chart(generate_viz(df_clean))
            except Exception as e:
                st.error(f"Erreur de rendu graphique : {e}")
        else:
            st.info("Remplissez les colonnes 'Processus' et 'Client' pour voir le schéma.")
        else:
        st.warning("Sélectionnez un projet pour voir le SIPOC.")
            
        # --- 6. VOICE OF CUSTOMER (VOC) ---
        st.divider()
        st.subheader("6. Voice of Customer (VOC)")
        
        p_idx = st.session_state.current_project_idx

        # --- A. ZONE D'IMPORTATION ---
        st.write("📤 **Importation intelligente (Excel ou PDF)**")
        uploaded_file = st.file_uploader(
            "Importez vos enquêtes :", 
            type=["xlsx", "pdf", "csv"],
            key=f"voc_uploader_{p_idx}" 
        )

        if uploaded_file is not None:
            if st.button("🪄 Extraire les données via IA", key=f"btn_extract_voc_{p_idx}"):
                with st.spinner("Analyse en cours..."):
                    extracted_data = [
                        {"Client": "C-001", "Verbatim": "Les délais sont trop longs", "Problème": "Délai", "Impact": "Satisfaction", "Fréquence": "Fréquent", "Gravité": "Élevée"}
                    ]
                    p["voc_data"] = extracted_data
                    st.rerun()

        st.write("---")

        # --- B. TABLEAU DE SAISIE VOC ---
        if "voc_data" not in p:
            p["voc_data"] = [{"Client": "", "Verbatim": "", "Problème": "", "Impact": "", "Fréquence": "Occasionnel", "Gravité": "Moyenne"}]

        voc_editor_key = f"voc_table_editor_{p_idx}"
        
        # Correction ici : on simplifie le column_config pour éviter le TypeError
        edited_voc = st.data_editor(
            p["voc_data"],
            num_rows="dynamic",
            column_config={
                "Fréquence": st.column_config.SelectboxColumn(
                    "Fréquence", 
                    options=["Rare", "Occasionnel", "Fréquent", "Critique"]
                ),
                "Gravité": st.column_config.SelectboxColumn(
                    "Gravité", 
                    options=["Faible", "Moyenne", "Élevée", "Critique"]
                ),
                "Verbatim": st.column_config.TextColumn(
                    "Verbatim", 
                    help="Citation directe du client"
                )
            },
            use_container_width=True,
            key=voc_editor_key
        )
        
        if st.button("✅ Valider les données du tableau", key=f"btn_save_voc_final_{p_idx}"):
            p["voc_data"] = edited_voc
            st.success("Données VOC enregistrées !")
            st.rerun()

        # --- C. ANALYSE IA FINALE ---
        st.write("---")
        if st.button("🔍 Catégoriser les Verbatims", key=f"ai_voc_analysis_btn_{p_idx}"):
            all_verbatims = " ".join([str(row.get("Verbatim", "")) for row in p["voc_data"] if row.get("Verbatim")])
            if all_verbatims.strip():
                st.session_state.voc_analysis = f"### 🎯 Analyse IA\nBasée sur : {all_verbatims[:50]}..."
                st.rerun()

        if "voc_analysis" in st.session_state:
            st.markdown(st.session_state.voc_analysis)
            
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
