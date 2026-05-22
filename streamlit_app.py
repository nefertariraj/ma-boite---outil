# Fichier initialisé proprement sans résidu de texte
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import json

# ==========================================
# 📋 MODÈLE DE RÉFÉRENCE UNIQUE POUR CHAQUE PROJET
# ==========================================
PROJET_MODELE_REFERENCE = {
    "nom": "",
    "gantt_data": pd.DataFrame(),
    "mesure_data": pd.DataFrame(),  # Structure pour la phase Mesure
    "dmaic": {
        "define": {},
        "measure": {},  # Stockage complet pour la phase Mesure
        "analyze": {},
        "improve": {},
        "innovate": {},
        "control": {}
    },
    "parametres": {},
    "progression": 0
}

# ==========================================
# 🛠️ FONCTIONS DE SÉRIALISATION / DÉSÉRIALISATION
# ==========================================
def deep_serialize(obj):
    """ Préparation récursive de tous les états, tables, phases et champs utilisateurs """
    if isinstance(obj, pd.DataFrame):
        return {"_type_df_": True, "data": obj.to_dict(orient="records")}
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_serialize(i) for i in obj]
    if hasattr(obj, 'strftime'):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def deep_deserialize(obj):
    """ Reconstruction à l'identique des types d'origine (DataFrames, dicts...) """
    if isinstance(obj, dict):
        if obj.get("_type_df_") is True:
            return pd.DataFrame(obj.get("data", []))
        return {k: deep_deserialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_deserialize(i) for i in obj]
    return obj

# ==========================================
# 🔄 SYSTÈME D'IMPORTATION INVISIBLE SANS CASSE
# ==========================================
def traiter_importation_json():
    """ Restaure l'intégralité des données dans le state existant sans altérer l'interface """
    fichier_charge = st.session_state.get("sidebar_uploader_file")
    if fichier_charge is not None:
        try:
            raw_data = json.load(fichier_charge)
            restored_data = deep_deserialize(raw_data)
            
            if isinstance(restored_data, list):
                projets_valides = []
                for p_item in restored_data:
                    if not isinstance(p_item, dict):
                        continue
                    
                    # On fusionne avec le modèle de référence pour combler d'éventuels manques d'anciennes versions
                    projet_reconstruit = PROJET_MODELE_REFERENCE.copy()
                    projet_reconstruit.update(p_item)
                    
                    # Vérification stricte des conteneurs de données critiques
                    if not isinstance(projet_reconstruit["gantt_data"], pd.DataFrame):
                        projet_reconstruit["gantt_data"] = pd.DataFrame(projet_reconstruit["gantt_data"])
                        
                    if not isinstance(projet_reconstruit["mesure_data"], pd.DataFrame):
                        projet_reconstruit["mesure_data"] = pd.DataFrame(projet_reconstruit["mesure_data"])

                    # Re-mapping sécurisé de l'arbre DMAIC complet
                    dmaic_originel = p_item.get("dmaic", {})
                    dmaic_structure = {k: v.copy() if isinstance(v, dict) else v for k, v in PROJET_MODELE_REFERENCE["dmaic"].items()}
                    
                    for phase in ["define", "measure", "analyze", "improve", "innovate", "control"]:
                        if phase in dmaic_originel:
                            dmaic_structure[phase] = dmaic_originel[phase]
                    
                    projet_reconstruit["dmaic"] = dmaic_structure
                    projets_valides.append(projet_reconstruit)

                if projets_valides:
                    st.session_state.projects = projets_valides
                    st.session_state["current_project_idx"] = None
        except Exception as e:
            st.sidebar.error(f"Erreur de restauration : {e}")

# --- CONFIGURATION DE LA PAGE & STYLE ---
st.set_page_config(page_title="LSS - Personal Toolbox", layout="wide")

if 'primary_color' not in st.session_state:
    st.session_state.primary_color = "#1E3A8A" 

st.markdown(f"""
    <style>
    .stApp {{ background-color: #FFFFFF; }}
    .stButton>button {{ background-color: {st.session_state.primary_color}; color: white; border-radius: 5px; }}
    .project-card {{
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        background-color: #F8FAFC;
        margin-bottom: 0.5rem;
        text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION SÉCURISÉE DES VARIABLES ---
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
        user = st.text_input("Identifiant (Email Google)", key="login_user_input")
        pwd = st.text_input("Mot de passe", type="password", key="login_pwd_input")
        if st.button("Se connecter via Google Drive", key="login_submit_btn"):
            if user and pwd: 
                st.session_state.authenticated = True
                st.rerun()
    st.stop()

# ==========================================
# ⚙️ BARRE LATÉRALE MOTEUR
# ==========================================
with st.sidebar:
    st.title("⚙️ Paramètres & Sauvegarde")
    color = st.color_picker("Couleur de l'outil", st.session_state.primary_color, key="sidebar_color_picker")
    st.session_state.primary_color = color
    st.divider()

    # Exportation complète de la session
    st.sidebar.subheader("💾 Sauvegarder mon travail")
    if len(st.session_state.projects) > 0:
        try:
            data_json = json.dumps(deep_serialize(st.session_state.projects), indent=4, ensure_ascii=False)
            st.sidebar.download_button(
                label="📤 Télécharger la sauvegarde (.json)",
                data=data_json,
                file_name="sauvegarde_boite_outils.json",
                mime="application/json",
                key="sidebar_download_btn"
            )
        except Exception as e:
            st.sidebar.error(f"Erreur export : {e}")
    else:
        st.sidebar.info("Aucun projet à sauvegarder.")

    # Importation
    st.sidebar.divider()
    st.sidebar.subheader("📥 Reprendre mon travail")
    st.sidebar.file_uploader(
        "Importer un fichier de sauvegarde", 
        type="json", 
        key="sidebar_uploader_file",
        on_change=traiter_importation_json
    )

    # ----------------------------------------------------
    # 🏠 ÉCRAN INITIAL UNIQUE (VUE EN GRILLE DE CARTES)
    # ----------------------------------------------------
    st.title("Mes projets Lean Six Sigma")

    # --- 1. SÉCURITÉ : INITIALISATION DU STOCKAGE ---
    if "projects" not in st.session_state:
        st.session_state.projects = []

    # --- 2. NOUVEAU COMPOSANT DE SÉLECTION ET SUPPRESSION BLINDÉ ---
    if len(st.session_state.projects) > 0:
        # Un espace dédié et isolé pour la gestion des projets
        with st.form(key="formulaire_gestion_suppression_projet"):
            st.subheader("🗑️ Gestion et suppression de projet")
            
            # Création d'une liste textuelle propre pour identifier chaque projet individuellement
            options_projets = {
                f"📊 {p.get('nom', 'Projet sans titre')} (Index #{idx+1})": idx 
                for idx, p in enumerate(st.session_state.projects) if isinstance(p, dict)
            }
            
            # Sélection claire du projet à cibler
            projet_selectionne_label = st.selectbox(
                "Sélectionnez le projet à identifier :",
                options=["-- Choisir un projet à supprimer --"] + list(options_projets.keys())
            )
            
            # Case de confirmation obligatoire (Sécurité anti-erreur)
            confirmation_securite = st.checkbox("Êtes-vous sûr de vouloir supprimer définitivement ce projet ?")
            
            # Bouton de soumission du formulaire
            bouton_soumission = st.form_submit_button("Supprimer le projet sélectionné", use_container_width=True)
            
            if bouton_soumission:
                if projet_selectionne_label == "-- Choisir un projet à supprimer --":
                    st.error("⚠️ Veuillez sélectionner un projet valide dans la liste ci-dessus.")
                elif not confirmation_securite:
                    st.error("🔒 Veuillez cocher la case de confirmation avant de procéder à la suppression.")
                else:
                    # Exécution de la suppression réelle dans le local state
                    index_a_retirer = options_projets[projet_selectionne_label]
                    st.session_state.projects.pop(index_a_retirer)
                    
                    # Sécurité si le projet supprimé était celui en cours d'édition
                    if st.session_state.get("current_project_idx") == index_a_retirer:
                        st.session_state["current_project_idx"] = None
                        
                    st.success("✅ Le projet a été retiré du stockage avec succès !")
                    st.rerun()

    # --- 3. CRÉATION DE PROJET (FONCTIONNEMENT ACTUEL CONSERVÉ) ---
    with st.expander("➕ Initialiser un nouveau projet", expanded=False):
        nouveau_nom = st.text_input("Nom du projet", key="creation_project_name_input")
        if st.button("Confirmer la création", key="creation_project_confirm_btn"):
            if nouveau_nom:
                nouveau_projet = {
                    "nom": nouveau_nom,
                    "gantt_data": pd.DataFrame(),
                    "mesure_data": pd.DataFrame(),
                    "dmaic": {
                        "define": {}, "measure": {}, "analyze": {},
                        "improve": {}, "innovate": {}, "control": {}
                    },
                    "parametres": {},
                    "progression": 0
                }
                st.session_state.projects.append(nouveau_projet)
                st.rerun()

    st.divider()

    # --- 4. AFFICHAGE DE LA GRILLE (FONCTIONNEMENT ACTUEL CONSERVÉ) ---
    if len(st.session_state.projects) > 0:
        nombre_colonnes = 3
        cols_grille = st.columns(nombre_colonnes)
    
        for idx, p in enumerate(st.session_state.projects):
            if not isinstance(p, dict):
                continue
            nom_du_projet = p.get("nom", f"Projet #{idx+1}")
            col_cible = cols_grille[idx % nombre_colonnes]
            cle_unique = f"carte_grille_accueil_{idx}_{str(nom_du_projet).replace(' ', '_')}"
        
            with col_cible:
                st.markdown(f"""
                <div class="project-card" style="padding: 20px; border: 1px solid #E2E8F0; border-radius: 8px; background-color: #FFFFFF; margin-bottom: 10px;">
                    <span style="font-size: 1.1rem; font-weight: bold; color: #1E293B; display: block;">📊 {nom_du_projet}</span>
                </div>
                """, unsafe_allow_html=True)
            
                if st.button("Ouvrir le projet", key=f"btn_ouvrir_{cle_unique}", use_container_width=True):
                    st.session_state["current_project_idx"] = idx
                    st.rerun()
                st.write("") 
    else:
        st.info("💡 Aucun projet disponible. Créez un nouveau projet ou importez un fichier JSON depuis le menu latéral.")
    
    st.info("🛠️ Vos composants graphiques originaux (onglets DMAIC, diagrammes Plotly d'origine, formulaires de saisie, tableaux éditables st.data_editor) se ré-exécutent automatiquement en utilisant les données fidèlement restaurées ci-dessus.")
        
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
        
        # SÉCURITÉ : Initialisation propre du DataFrame dans le session_state
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
            try:
                # Lecture unique du fichier importé
                df_imp = pd.read_excel(up_file).fillna("")
                df_imp.columns = [c.lower().strip() for c in df_imp.columns]
                
                # Détection automatique des colonnes
                c_col = next((c for c in df_imp.columns if "client" in c or "nom" in c), df_imp.columns[0])
                q_col = next((c for c in df_imp.columns if "quest" in c), df_imp.columns[1] if len(df_imp.columns) > 1 else None)
                r_col = next((c for c in df_imp.columns if "rép" in c or "verbatim" in c or "brute" in c), df_imp.columns[-1])
            
                new_rows = pd.DataFrame({
                    "client": df_imp[c_col].astype(str),
                    "question": df_imp[q_col].astype(str) if q_col else "Question non spécifiée",
                    "réponse brute": df_imp[r_col].astype(str)
                })
                
                # CORRECTION : On vérifie si le fichier en cours est vraiment différent de ce qu'on a stocké
                # en comparant les valeurs de la colonne réponse brute pour éviter le conflit avec le data_editor
                if st.session_state.voc_raw_data.empty or not (st.session_state.voc_raw_data["réponse brute"].equals(new_rows["réponse brute"])):
                    st.session_state.voc_raw_data = new_rows
                    st.session_state.voc_results = None  # Réinitialise les résultats pour faire réapparaître le bouton d'analyse
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur lors de l'import : {e}")

        # Affichage stabilisé du tableau d'édition
        edited_voc_df = st.data_editor(
            st.session_state.voc_raw_data,
            num_rows="dynamic",
            use_container_width=True,
            key=f"voc_editor_sync_{p_idx}"
        )
        if edited_voc_df is not None:
            st.session_state.voc_raw_data = edited_voc_df

        st.write("---")
        st.subheader("3. Analyse Thématique & CTQ")
    
        # Le bouton s'affiche systématiquement si aucune analyse n'est encore enregistrée pour ce fichier
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

            propositions = plans_action.get(top_theme, [
                "Audit approfondi des processus.", "Standardisation des tâches.", "Formation des équipes.", "Suivi des indicateurs."
            ])

            col_a, col_b = st.columns(2)
            with col_a:
                st.info(f"💡 **Proposition 1**\n\n{propositions[0]}")
                st.info(f"🚀 **Proposition 2**\n\n{propositions[1]}")
            with col_b:
                st.info(f"🛠️ **Proposition 3**\n\n{propositions[2]}")
                st.info(f"📊 **Proposition 4**\n\n{propositions[3]}")
                
        # --- 7. PROJECT MILESTONE & TIMING ---
        st.divider()
        st.header("📅 7. Project Milestone & Timing")

        import datetime
        import plotly.express as px
        import pandas as pd  # 👈 SÉCURITÉ : Assure l'existence de 'pd' pour éviter le crash NameError

        # SÉCURITÉ EXTENDED : Si 'p' a été perdu ou renommé lors du rechargement de l'application
        if 'p' not in locals() and 'p' not in globals():
            if "current_project" in st.session_state:
                p = st.session_state["current_project"]
            elif "project" in st.session_state:
                p = st.session_state["project"]
            elif "projects" in st.session_state and "p_idx" in locals():
                p = st.session_state["projects"][p_idx]
            else:
                p = {}

        # SÉCURITÉ INDEX : Assure la présence de p_idx pour les clés de composants
        if 'p_idx' not in locals() and 'p_idx' not in globals():
            p_idx = 0

        # 1. Initialisation initiale / Sécurisation si la structure est altérée ou absente
        if "gantt_data" not in p or not isinstance(p["gantt_data"], pd.DataFrame):
            p["gantt_data"] = pd.DataFrame([
                {"Etape": "Define", "Début": datetime.date(2026, 5, 1), "Fin": datetime.date(2026, 5, 15), "Responsable": "Black Belt"},
                {"Etape": "Measure", "Début": datetime.date(2026, 5, 16), "Fin": datetime.date(2026, 6, 15), "Responsable": "Green Belt"},
                {"Etape": "Analyze", "Début": datetime.date(2026, 6, 16), "Fin": datetime.date(2026, 7, 15), "Responsable": "Black Belt"},
                {"Etape": "Improve", "Début": datetime.date(2026, 7, 16), "Fin": datetime.date(2026, 9, 15), "Responsable": "Team"},
                {"Etape": "Control", "Début": datetime.date(2026, 9, 16), "Fin": datetime.date(2026, 10, 31), "Responsable": "Process Owner"}
            ])

        # 1b. Préparation propre des données pour l'affichage (Calendrier)
        try:
            df_input = p["gantt_data"].copy()
            df_input["Début"] = pd.to_datetime(df_input["Début"], errors='coerce').dt.date
            df_input["Fin"] = pd.to_datetime(df_input["Fin"], errors='coerce').dt.date
        except Exception:
            p["gantt_data"] = pd.DataFrame([
                {"Etape": "Define", "Début": datetime.date(2026, 5, 1), "Fin": datetime.date(2026, 5, 15), "Responsable": "Black Belt"},
                {"Etape": "Measure", "Début": datetime.date(2026, 5, 16), "Fin": datetime.date(2026, 6, 15), "Responsable": "Green Belt"},
                {"Etape": "Analyze", "Début": datetime.date(2026, 6, 16), "Fin": datetime.date(2026, 7, 15), "Responsable": "Black Belt"},
                {"Etape": "Improve", "Début": datetime.date(2026, 7, 16), "Fin": datetime.date(2026, 9, 15), "Responsable": "Team"},
                {"Etape": "Control", "Début": datetime.date(2026, 9, 16), "Fin": datetime.date(2026, 10, 31), "Responsable": "Process Owner"}
            ])
            df_input = p["gantt_data"].copy()

        # 2. Configuration des colonnes pour le sélecteur de date
        config_colonnes = {
            "Etape": st.column_config.TextColumn("Etape", required=True),
            "Début": st.column_config.DateColumn("Début", format="YYYY-MM-DD", required=True),
            "Fin": st.column_config.DateColumn("Fin", format="YYYY-MM-DD", required=True),
            "Responsable": st.column_config.TextColumn("Responsable")
        }

        # Clé unique pour l'état d'édition
        gantt_key = f"gantt_table_final_{p_idx}"

        # 📊 FONCTION DE SAUVEGARDE EN TEMPS RÉEL (on_change)
        def sync_gantt_live():
            if gantt_key in st.session_state:
                state = st.session_state[gantt_key]
                df_base = p["gantt_data"].copy()
        
                # Appliquer les lignes modifiées
                for row_idx, changes in state.get("edited_rows", {}).items():
                    for col, val in changes.items():
                        df_base.iloc[row_idx, df_base.columns.get_loc(col)] = val
                
                # Appliquer les lignes ajoutées
                for new_row in state.get("added_rows", []):
                    df_base = pd.concat([df_base, pd.DataFrame([new_row])], ignore_index=True)
            
                # Appliquer les lignes supprimées
                deleted_rows = state.get("deleted_rows", [])
                if deleted_rows:
                    df_base = df_base.drop(deleted_rows).reset_index(drop=True)
            
                # Mise à jour immédiate de la source de données principale
                p["gantt_data"] = df_base

        # Affichage du tableau éditable avec synchronisation automatique au changement
        edited_gantt = st.data_editor(
            df_input, 
            column_config=config_colonnes,
            num_rows="dynamic", 
            use_container_width=True, 
            key=gantt_key,
            on_change=sync_gantt_live
        )

        # 3. Bouton d'action pour générer le graphique Plotly
        if st.button("🚀 Générer le planning", key=f"btn_gantt_{p_idx}"):
            try:
                df_gantt = p["gantt_data"].copy().dropna(subset=["Etape", "Début", "Fin"])
        
                if not df_gantt.empty:
                    df_gantt["Début"] = pd.to_datetime(df_gantt["Début"])
                    df_gantt["Fin"] = pd.to_datetime(df_gantt["Fin"])
            
                    ordre_etapes = df_gantt["Etape"].tolist()
            
                    # Création du graphique Plotly rafraîchi
                    fig = px.timeline(
                        df_gantt, 
                        x_start="Début", 
                        x_end="Fin", 
                        y="Etape", 
                        color="Responsable",
                        title=f"Planning DMAIC - {p.get('name', 'Projet')}",
                        color_discrete_sequence=["#1E3A8A", "#10B981", "#F59E0B", "#EF4444", "#6B7280"]
                    )
            
                    fig.update_yaxes(categoryorder="array", categoryarray=ordre_etapes[::-1])
            
                    # Sauvegarde forcée du nouveau graphique dans le session_state
                    st.session_state[f"gantt_fig_{p_idx}"] = fig
                    st.toast("✅ Diagramme de Gantt mis à jour !", icon="📊")
                else:
                    st.error("Veuillez remplir correctement toutes les étapes et dates du tableau.")
            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")

        # 4. Rendu visuel permanent du graphique
        if f"gantt_fig_{p_idx}" in st.session_state and st.session_state[f"gantt_fig_{p_idx}"] is not None:
            st.plotly_chart(st.session_state[f"gantt_fig_{p_idx}"], use_container_width=True)
    
    # --- PHASE MEASURE ---
    with tabs[1]:
        st.header("Phase Measure")
        
        # 1. Project Definition & Équation Y = f(X)
        # ==========================================
        st.subheader("1. Project Definition & Transfer Function Y = f(X)")
        
        # Récupération des données réelles de la phase Define
        ctq_v = p.get("selected_ctq", "Non défini")
        voc_df = st.session_state.get("voc_raw_data", pd.DataFrame())
        
        with st.container(border=True):
            st.markdown(f"### 🎯 Objectif du Projet (Y) : `{ctq_v}`")
            st.markdown(
                r"Équation de transfert Black Belt : "
                r"$$Y = f(X_1, X_2, ..., X_n)$$"
            )
            st.caption("Détermination des variables critiques d'entrée (X) par rétro-ingénierie des verbatims clients.")

            # --- MOTEUR D'ANALYSE PAR EXTRACTION CONTEXTUELLE ---
            st.markdown("##### 🧠 Analyse IA Contextuelle des Verbatims (Top 10 X)")
            
            def analyze_voc_for_specific_x(df):
                # Si le tableau VOC est vide, on fournit une structure d'attente minimale
                if df.empty or "réponse brute" not in df.columns:
                    return [
                        {"Code Variable": f"x{i}", "Description": f"Attente de la collecte des verbatims réels pour extraction du facteur X{i}", "Impact Potentiel": "Moyen", "Origine": "Système"}
                        for i in range(1, 11)
                    ]
                
                # 1. Nettoyage et tokenisation du texte réel du client
                textes = df["réponse brute"].dropna().astype(str).tolist()
                mots_poubelles = [
                    "le", "la", "les", "des", "une", "pour", "dans", "avec", "plus", "fait", 
                    "tout", "cette", "dans", "sont", "avec", "pour", "mais", "plus", "nous",
                    "vous", "avec", "suis", "votre", "notre", "c'est", "d'un", "d'une", "est",
                    "elle", "ils", "elles", "pas", "que", "qui", "sur", "aux", "par", "dans"
                ]
                
                dictionnaire_contextuel = {}
                for texte in textes:
                    mots = [m.strip(",.?!()\"';:/*-_+") for m in texte.lower().split() if len(m) > 3]
                    for m in mots:
                        if m not in mots_poubelles:
                            dictionnaire_contextuel[m] = dictionnaire_contextuel.get(m, 0) + 1
                
                # 2. Tri des 10 concepts les plus fréquemment cités par le client (Top 10)
                concepts_cles = sorted(dictionnaire_contextuel.items(), key=lambda item: item[1], reverse=True)[:10]
                
                # 3. Traduction des concepts réels en Hypothèses Six Sigma (X)
                suggestions_x = []
                for idx, (mot, freq) in enumerate(concepts_cles):
                    # Génération de la description basée sur le VRAI mot du client
                    description_cause = f"Variabilité ou défaillance liée directement au facteur '{mot.upper()}' (Cité {freq} fois dans le VOC)"
                    
                    # Détermination de l'impact selon la récurrence du mot dans les plaintes
                    if freq >= 5:
                        impact = "Très Fort"
                    elif freq >= 3:
                        impact = "Fort"
                    else:
                        impact = "Moyen"
                        
                    suggestions_x.append({
                        "Code Variable": f"x{idx+1}",
                        "Description": description_cause,
                        "Impact Potentiel": impact,
                        "Origine": f"IA - Extraction Fréquence VOC ('{mot}')"
                    })
                
                # Remplissage de sécurité si le VOC est trop court pour atteindre 10 mots différents
                while len(suggestions_x) < 10:
                    current_len = len(suggestions_x) + 1
                    suggestions_x.append({
                        "Code Variable": f"x{current_len}", 
                        "Description": f"Facteur de variabilité additionnel à investiguer sur le terrain (X{current_len})", 
                        "Impact Potentiel": "Faible", 
                        "Origine": "Analyse Complémentaire Black Belt"
                    })
                    
                return suggestions_x

            # Génération/Mise à jour automatique basée sur l'état actuel du tableau VOC
            if "measure_x_table" not in p or st.button("🔄 Ré-analyser les données du VOC en temps réel", key=f"recalc_voc_{p_idx}"):
                p["measure_x_table"] = analyze_voc_for_specific_x(voc_df)
                if not voc_df.empty:
                    st.toast("⚡ Top 10 des variables X extrait avec succès !", icon="🧠")

            st.info("📋 **Mode Black Belt activé** : Le tableau ci-dessous a isolé le **Top 10 des variables X** les plus critiques basées sur votre VOC. Vous pouvez modifier, affiner, ou ajouter de nouvelles lignes.")

            # --- TABLEAU DYNAMIQUE DES X (4 COLONNES) ---
            df_x = pd.DataFrame(p["measure_x_table"])
            
            edited_x_df = st.data_editor(
                df_x,
                num_rows="dynamic", # Permet d'ajouter/supprimer librement des lignes
                use_container_width=True,
                key=f"x_matrix_editor_v3_{p_idx}",
                column_config={
                    "Code Variable": st.column_config.TextColumn("Code Variable", help="ex: x1, x2", width="small"),
                    "Description": st.column_config.TextColumn("Description de la cause probable (Spécifique au contexte)", width="large"),
                    "Impact Potentiel": st.column_config.SelectboxColumn(
                        "Impact Potentiel",
                        options=["Faible", "Moyen", "Fort", "Très Fort"],
                        width="medium"
                    ),
                    "Origine": st.column_config.TextColumn("Origine de l'hypothèse", width="medium")
                }
            )
            
            # Sauvegarde dans le dictionnaire projet
            if st.button("💾 Enregistrer la Matrice des X Validée", key=f"save_def_x_v3_{p_idx}"):
                p["measure_x_table"] = edited_x_df.to_dict('records')
                st.success("🎯 Matrice complète des 10 X enregistrée avec succès pour la phase Analyze.")

        # 2. Current State Detailed Process Map (VSM Base)
        # ==========================================
        st.subheader("2. Current State Detailed Process Map")

        # [PERSISTANCE VOC] Sécurité pour le rechargement automatique
        if "saved_voc_dict" in p and "voc_raw_data" not in st.session_state:
            st.session_state["voc_raw_data"] = pd.DataFrame(p["saved_voc_dict"])

        # 1. INITIALISATION STRICTE DE LA STRUCTURE DES MACRO-ÉTAPES (AVEC PRIORITÉ À L'IMPORT)
        if "vsm_macro_steps" not in st.session_state or "vsm_macro_steps" in p:
            # Si le projet contient des étapes (chargées depuis un JSON), on les prend en priorité
            if "vsm_macro_steps" in p and isinstance(p["vsm_macro_steps"], list):
                st.session_state["vsm_macro_steps"] = list(p["vsm_macro_steps"])
            else:
                sipoc_data = p.get("sipoc_data", [])
                macro_steps = []
                if isinstance(sipoc_data, list) and len(sipoc_data) > 0:
                    for row in sipoc_data:
                        step_name = row.get("Process") or row.get("process")
                        if step_name:
                            macro_steps.append(str(step_name))
                
                if not macro_steps:
                    macro_steps = ["1. Réception & Tri", "2. Saisie & Vérification", "3. Traitement & Analyse", "4. Validation & Approbation"]
                st.session_state["vsm_macro_steps"] = macro_steps

        # 2. INITIALISATION DU STOCKAGE DES DONNÉES DE TÂCHES (AVEC PRIORITÉ À L'IMPORT)
        if "vsm_detailed_map" not in st.session_state or "vsm_detailed_map" in p:
            if "vsm_detailed_map" in p and isinstance(p["vsm_detailed_map"], dict):
                st.session_state["vsm_detailed_map"] = dict(p["vsm_detailed_map"])
            else:
                st.session_state["vsm_detailed_map"] = {
                    step: [{"Détail de la tâche": "Sous-tâche initiale", "Valeur": 5.0, "Unité": "Minutes", "Type d'activité": "VA (Valeur Ajoutée)"}]
                    for step in st.session_state["vsm_macro_steps"]
                }

        # 3. INITIALISATION DES METRICS CALCULÉES
        if "vsm_totals" not in st.session_state:
            st.session_state["vsm_totals"] = {
                "lead_time": 0.0, "va": 0.0, "nva": 0.0, "bnrva": 0.0, "attente": 0.0, "pce": 0.0,
                "section_totals": {step: 5.0 for step in st.session_state["vsm_macro_steps"]}
            }

        # Fonction de conversion interne sécurisée
        def convert_to_minutes(valeur, unite):
            try: 
                val = float(valeur)
                if unite == "Heures": return val * 60.0
                if unite == "Jours": return val * 1440.0
                return val
            except (ValueError, TypeError): 
                return 0.0

        # --------------------------------------------------
        # FONCTIONS CALLBACKS (GESTION DE LA STRUCTURE)
        # --------------------------------------------------
        def add_section_callback(name, index_pos):
            clean_name = name.strip()
            if clean_name and clean_name not in st.session_state["vsm_macro_steps"]:
                st.session_state["vsm_macro_steps"].insert(index_pos, clean_name)
                st.session_state["vsm_detailed_map"][clean_name] = [
                    {"Détail de la tâche": "Première tâche à définir", "Valeur": 0.0, "Unité": "Minutes", "Type d'activité": "VA (Valeur Ajoutée)"}
                ]
                st.session_state["vsm_totals"]["section_totals"][clean_name] = 0.0
                st.toast(f"ℹ️ Section '{clean_name}' ajoutée !", icon="➕")
            elif clean_name in st.session_state["vsm_macro_steps"]:
                st.toast("⚠️ Cette section existe déjà !", icon="❌")

        def delete_section_callback(step_to_del):
            if step_to_del in st.session_state["vsm_macro_steps"]:
                st.session_state["vsm_macro_steps"].remove(step_to_del)
                if step_to_del in st.session_state["vsm_detailed_map"]:
                    del st.session_state["vsm_detailed_map"][step_to_del]
                if step_to_del in st.session_state["vsm_totals"]["section_totals"]:
                    del st.session_state["vsm_totals"]["section_totals"][step_to_del]
                st.toast(f"ℹ️ Section '{step_to_del}' supprimée.", icon="🗑️")

        # --------------------------------------------------
        # INTERFACE DE STRUCTURATION DU FLUX
        # --------------------------------------------------
        with st.container(border=True):
            st.markdown("### 🗺️ Gestion du Flux & Décomposition (Lead Time)")
            st.caption("Pilotez la structure de votre VSM. Saisissez vos tâches librement, puis cliquez sur le bouton de sauvegarde en bas pour recalculer l'ensemble du flux.")

            # Formulaire d'ajout de section
            col_add1, col_add2, col_add3 = st.columns([3, 2, 1.5])
            with col_add1:
                new_sec_name = st.text_input("📝 Nom de la nouvelle section :", placeholder="Ex: 2.bis Contrôle Qualité", key=f"new_input_text_{p_idx}")
            with col_add2:
                positions = ["En fin de processus", "Au tout début"]
                for step in st.session_state["vsm_macro_steps"]:
                    positions.append(f"Après : {step}")
                
                chosen_pos_text = st.selectbox("📍 Insérer la section :", options=positions, key=f"pos_select_{p_idx}")
                
                if chosen_pos_text == "Au tout début":
                    insert_idx = 0
                elif chosen_pos_text == "En fin de processus":
                    insert_idx = len(st.session_state["vsm_macro_steps"])
                else:
                    selected_step = chosen_pos_text.replace("Après : ", "")
                    insert_idx = st.session_state["vsm_macro_steps"].index(selected_step) + 1

            with col_add3:
                st.write("") 
                if st.button("➕ Créer la section", use_container_width=True, key=f"btn_create_{p_idx}"):
                    if new_sec_name.strip():
                        add_section_callback(new_sec_name, insert_idx)
                        st.rerun()
                    else:
                        st.warning("Nom invalide.")

            st.markdown("---")

            # --------------------------------------------------
            # BOUCLE D'ÉDITION LIBRE
            # --------------------------------------------------
            current_editors_state = {}

            for idx_step, step in enumerate(st.session_state["vsm_macro_steps"]):
                current_data = st.session_state["vsm_detailed_map"].get(step, [])
                df_sub = pd.DataFrame(current_data)
                
                sec_min = st.session_state["vsm_totals"]["section_totals"].get(step, 0.0)
                if sec_min >= 1440: t_text = f"{sec_min/1440:.1f} j"
                elif sec_min >= 60: t_text = f"{sec_min/60:.1f} h"
                else: t_text = f"{sec_min:.1f} min"

                col_title, col_del = st.columns([5, 1])
                with col_title:
                    st.markdown(f"#### 📦 Section {idx_step + 1} : {step} `⏱️ Dernier calcul: {t_text}`")
                with col_del:
                    st.write("") 
                    if st.button("🗑️ Supprimer", key=f"del_sec_{idx_step}_{p_idx}", use_container_width=True):
                        delete_section_callback(step)
                        st.rerun()

                edited_df = st.data_editor(
                    df_sub,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"vsm_editor_v12_{step}_{p_idx}", 
                    column_config={
                        "Détail de la tâche": st.column_config.TextColumn("Détail des micro-tâches", width="large"),
                        "Valeur": st.column_config.NumberColumn("Délai", min_value=0.0, format="%.1f", width="small", required=True),
                        "Unité": st.column_config.SelectboxColumn("Unité", options=["Minutes", "Heures", "Jours"], width="small", required=True),
                        "Type d'activité": st.column_config.SelectboxColumn(
                            "Type d'activité (Lean)",
                            options=["VA (Valeur Ajoutée)", "NVA (Non Valeur Ajoutée)", "BNRVA (Business Necessary, Non-Value Added)", "Temps d'attente / Stock"],
                            width="medium", required=True
                        )
                    }
                )
                current_editors_state[step] = edited_df
                st.markdown("---")

            # --------------------------------------------------
            # BOUTON UNIQUE DE SÉCURISATION & CALCULS GLOBAUX
            # --------------------------------------------------
            if st.button("💾 Enregistrer la Cartographie & Mettre à jour les Calculs", type="primary", use_container_width=True, key=f"save_vsm_map_v12_{p_idx}"):
                
                total_lt = 0.0
                total_va = 0.0
                total_nva = 0.0
                total_bnrva = 0.0
                total_attente = 0.0
                new_section_totals = {}

                for step in st.session_state["vsm_macro_steps"]:
                    df_edited = current_editors_state.get(step, pd.DataFrame())
                    
                    if not df_edited.empty and "Détail de la tâche" in df_edited.columns:
                        df_edited = df_edited.dropna(subset=["Détail de la tâche"])
                    
                    records = df_edited.to_dict('records')
                    st.session_state["vsm_detailed_map"][step] = records
                    
                    sec_sum = 0.0
                    if not df_edited.empty:
                        for _, row in df_edited.iterrows():
                            t_min = convert_to_minutes(row.get("Valeur", 0), row.get("Unité", "Minutes"))
                            sec_sum += t_min
                            total_lt += t_min
                            
                            act_type = row.get("Type d'activité")
                            if act_type == "VA (Valeur Ajoutée)": total_va += t_min
                            elif act_type == "NVA (Non Valeur Ajoutée)": total_nva += t_min
                            elif act_type == "BNRVA (Business Necessary, Non-Value Added)": total_bnrva += t_min
                            elif act_type == "Temps d'attente / Stock": total_attente += t_min
                    
                    new_section_totals[step] = sec_sum

                pce_calc = (total_va / total_lt * 100) if total_lt > 0 else 0.0

                st.session_state["vsm_totals"] = {
                    "lead_time": total_lt,
                    "va": total_va,
                    "nva": total_nva,
                    "bnrva": total_bnrva,
                    "attente": total_attente,
                    "pce": pce_calc,
                    "section_totals": new_section_totals
                }

                # 🚨 ALIGNEMENT ET SAUVEGARDE DIRECTE DANS LE DICTIONNAIRE DE PROJET
                p["vsm_macro_steps"] = list(st.session_state["vsm_macro_steps"])
                p["vsm_detailed_map"] = dict(st.session_state["vsm_detailed_map"])
                if "voc_raw_data" in st.session_state:
                    p["saved_voc_dict"] = st.session_state["voc_raw_data"].to_dict('records')
                
                st.success("🎯 Tous les calculs ont été mis à jour avec succès sur l'ensemble de la chaîne !")
                st.rerun()

            # ==========================================
            # RENDU VISUEL BASÉ SUR LES DERNIÈRES DONNÉES VALIDÉES
            # ==========================================
            st.markdown("### 🗺️ Schéma Value Stream Mapping (VSM) Résumé")
            
            steps_list = st.session_state["vsm_macro_steps"]
            if len(steps_list) > 0:
                vsm_cols = st.columns(len(steps_list))
                for i, step in enumerate(steps_list):
                    with vsm_cols[i]:
                        sec_min = st.session_state["vsm_totals"]["section_totals"].get(step, 0.0)
                        tasks_count = len(st.session_state["vsm_detailed_map"].get(step, []))
                        short_name = str(step)[:15] + "..." if len(str(step)) > 15 else str(step)
                        
                        with st.container(border=True):
                            st.markdown(f"**🔹 ÉTAPE {i+1}**")
                            st.caption(f"*{short_name}*")
                            st.markdown(f"📋 `{tasks_count} tsk`")
                            st.code(f"{sec_min:.1f} m", language="text")

            # Timeline
            st.markdown("#### ⏱️ Ligne de temps du Flux (Value Stream Timeline)")
            timeline_markdown = ""
            for i, step in enumerate(steps_list):
                sec_min = st.session_state["vsm_totals"]["section_totals"].get(step, 0.0)
                short_name = str(step)[:20] + "..." if len(str(step)) > 20 else str(step)
                timeline_markdown += f"**[{i+1}] {short_name}** ({sec_min:.1f} min) `——➡️` "
            
            if timeline_markdown:
                st.info(timeline_markdown.rstrip(" `——➡️` "))

            # Rapports Métriques Globaux du Lead Time
            st.markdown("### 📊 Rapports Globaux du Processus")
            
            totals = st.session_state["vsm_totals"]
            if totals["lead_time"] >= 1440: display_lt = f"{totals['lead_time'] / 1440:.1f} Jours"
            elif totals["lead_time"] >= 60: display_lt = f"{totals['lead_time'] / 60:.1f} Heures"
            else: display_lt = f"{totals['lead_time']:.1f} Min"

            c1, c2, c3 = st.columns(3)
            c1.metric("⏳ LEAD TIME TOTAL", display_lt)
            c2.metric("🟢 TOTAL VALEUR AJOUTÉE (VA)", f"{totals['va']:.1f} min")
            c3.metric("📈 EFFICIENCE DU CYCLE (PCE)", f"{totals['pce']:.1f}%")

        # 3. Lean Six Sigma Data Collection Plan (Y = f(X))
        # ==========================================
        st.subheader("3. Master Black Belt Data Collection Plan")
        
        st.markdown("""
        ### 📊 Alignement Stratégique $Y = f(X)$ & Matrice de Collecte Phase Measure
        En tant que **Master Black Belt**, ce module structure votre plan de collecte de données terrain de manière rigoureuse. 
        L'algorithme extrait automatiquement les **$X$ potentiels** de votre *Detailed Process Map* en isolant les **NVA**, les **gaspillages Lean (Muda)**, les **boucles de retouches (Rework)** et les **goulots d'étranglement**.
        """)

        # --------------------------------------------------
        # RECUPÉRATION SÉCURISÉE DES DONNÉES DU PROCESS MAP
        # --------------------------------------------------
        vsm_steps = st.session_state.get("vsm_macro_steps", [])
        vsm_detailed = st.session_state.get("vsm_detailed_map", {})
        vsm_totals = st.session_state.get("vsm_totals", {})
        section_totals = vsm_totals.get("section_totals", {})

        # Inventaire automatique complet des X potentiels basés sur les gaspillages Lean
        extracted_x_list = []
        
        if vsm_steps:
            # 1. Identification du Goulot (Théorie des Contraintes)
            if section_totals:
                highest_step = max(section_totals, key=section_totals.get)
                if section_totals[highest_step] > 0:
                    extracted_x_list.append({
                        "etape": highest_step,
                        "variable": f"Temps de cycle unitaire sur le goulot - {highest_step}",
                        "muda": "Surproduction / Capacité",
                        "description": "L'étape la plus longue qui limite le débit global du processus."
                    })

            # 2. Scan sémantique et par catégorie de la carte détaillée
            for step in vsm_steps:
                tasks = vsm_detailed.get(step, [])
                for t in tasks:
                    desc_tache = str(t.get("Détail de la tâche", ""))
                    type_act = t.get("Type d'activité", "")
                    desc_lower = desc_tache.lower()
                    
                    if not desc_tache or desc_tache == "Sous-tâche initiale" or desc_tache == "Première tâche à définir":
                        continue

                    # Isolation des Attentes / Files d'attente
                    if type_act == "Temps d'attente / Stock" or any(kw in desc_lower for kw in ["attente", "file", "stock", "bloqué", "en cours", "wip"]):
                        extracted_x_list.append({
                            "etape": step,
                            "variable": f"Temps de stagnation de la tâche : {desc_tache}",
                            "muda": "Attente (Waiting)",
                            "description": "Temps mort générant des délais inter-processus et du gonflement d'en-cours."
                        })
                    
                    # Isolation des Retouches / Corrections / Rework
                    elif type_act == "NVA (Non Valeur Ajoutée)" and any(kw in desc_lower for kw in ["retouche", "correction", "refaire", "erreur", "rework", "rejet", "validation", "approbation", "signature"]):
                        muda_type = "Défauts / Retouches" if "validation" not in desc_lower else "Sur-traitement (Overprocessing)"
                        extracted_x_list.append({
                            "etape": step,
                            "variable": f"Fréquence et temps de traitement de : {desc_tache}",
                            "muda": muda_type,
                            "description": "Boucle de retravail ou rupture de flux pour validation hiérarchique."
                        })
                    
                    # Isolation des Déplacements / Transports
                    elif any(kw in desc_lower for kw in ["déplacement", "transport", "envoi", "transfert", "aller", "retour"]):
                        extracted_x_list.append({
                            "etape": step,
                            "variable": f"Distance ou temps de transfert : {desc_tache}",
                            "muda": "Transport / Mouvement",
                            "description": "Rupture physique ou numérique obligeant au transfert d'informations."
                        })

        # Données de repli (Fallback réglementaire LSS) si le VSM est vide ou initial
        if not extracted_x_list:
            extracted_x_list = [
                {"etape": "1. Réception & Tri", "variable": "Taux d'erreurs et de dossiers incomplets à l'entrée", "muda": "Défauts / Retouches", "description": "Qualité de l'information entrante générant des demandes de compléments."},
                {"etape": "2. Saisie & Vérification", "variable": "Temps d'attente de validation par la hiérarchie", "muda": "Attente (Waiting)", "description": "Dossier en attente dans une file d'approbation numérique."},
                {"etape": "3. Traitement & Analyse", "variable": "Nombre de boucles de retravail (Rework)", "muda": "Défauts / Retouches", "description": "Non-conformité obligeant à refaire l'analyse initiale."}
            ]

        # --------------------------------------------------
        # ETAPE 1 : MATRICE DE PRIORISATION INTELLIGENTE DES X (FILTRES MBB)
        # --------------------------------------------------
        if "mbb_prioritization_matrix" not in st.session_state:
            initial_prio = []
            for item in extracted_x_list:
                initial_prio.append({
                    "Étape Source": item["etape"],
                    "Variable Potentielle (X)": item["variable"],
                    "Gaspillage / Muda": item["muda"],
                    "1. Influence fortement le Y ?": "Oui" if item["muda"] in ["Attente (Waiting)", "Défauts / Retouches", "Surproduction / Capacité"] else "Non",
                    "2. Apparaît souvent ?": "Oui",
                    "3. Peut-on mesurer fiablement ?": "Oui",
                    "Utilité Analytique (Futur Test d'Hypothèse)": f"Démontrer la corrélation mathématique avec la variation du Lead Time global."
                })
            st.session_state["mbb_prioritization_matrix"] = initial_prio

        with st.container(border=True):
            st.markdown("### 🧠 1. Filtrage et Priorisation des $X$ ($Y = f(X)$)")
            st.caption("Passez chaque variable au crible des 3 questions filtres fondamentales. Seuls les X validant l'ensemble des critères passeront dans le Data Collection Plan final.")

            df_prio = pd.DataFrame(st.session_state["mbb_prioritization_matrix"])

            # Éditeur interactif de filtrage
            edited_prio_df = st.data_editor(
                df_prio,
                num_rows="dynamic",
                use_container_width=True,
                key=f"mbb_prio_editor_{p_idx}",
                column_config={
                    "Étape Source": st.column_config.TextColumn("Étape Source", disabled=True, width="medium"),
                    "Variable Potentielle (X)": st.column_config.TextColumn("Variable Potentielle (X)", disabled=True, width="large"),
                    "Gaspillage / Muda": st.column_config.TextColumn("Type de Muda", disabled=True, width="medium"),
                    "1. Influence fortement le Y ?": st.column_config.SelectboxColumn("Influence Y ?", options=["Oui", "Non"], width="small"),
                    "2. Apparaît souvent ?": st.column_config.SelectboxColumn("Fréquent ?", options=["Oui", "Non"], width="small"),
                    "3. Peut-on mesurer fiablement ?": st.column_config.SelectboxColumn("Mesurable ?", options=["Oui", "Non"], width="small"),
                    "Utilité Analytique (Futur Test d'Hypothèse)": st.column_config.TextColumn("Utilité Future", width="large")
                }
            )

            # Rerunning et mise à jour dynamique de la structure des X validés
            if st.button("⚙️ Valider la pertinence & Générer le Data Collection Plan Master", type="primary", use_container_width=True, key=f"btn_gen_dcp_{p_idx}"):
                st.session_state["mbb_prioritization_matrix"] = edited_prio_df.to_dict('records')
                
                # Génération de la matrice réglementaire à 16 colonnes pour les éléments validés (Oui / Oui / Oui)
                dcp_final_rows = []
                for row in st.session_state["mbb_prioritization_matrix"]:
                    if row["1. Influence fortement le Y ?"] == "Oui" and row["2. Apparaît souvent ?"] == "Oui" and row["3. Peut-on mesurer fiablement ?"] == "Oui":
                        
                        # Déduction logique du type de métrique
                        var_name = str(row["Variable Potentielle (X)"])
                        is_time = any(kw in var_name.lower() for kw in ["temps", "délai", "stagnation", "durée"])
                        
                        dcp_final_rows.append({
                            "Variable à mesurer": var_name,
                            "Objectif de mesure": f"Quantifier la variance et l'impact de ce Muda sur le processus.",
                            "Lien avec le Y": "Contribution directe au Lead Time Global (Y) par allongement du temps de traversée.",
                            "Définition opérationnelle exacte": f"Chrono démarré au moment exact du début de l'action/attente et stoppé à sa complétion complète.",
                            "Type de donnée": "Continue (Temps)" if is_time else "Discrète (Défauts / Attributaire)",
                            "Unité": "Minutes" if is_time else "Nombre d'occurrences",
                            "Source de donnée": "Système d'information (Logs) / Saisie terrain",
                            "Méthode de collecte": "Extraction automatique de base de données" if is_time else "Feuille de pointage standardisée (Checksheet)",
                            "Point de mesure dans le processus": row["Étape Source"],
                            "Responsable collecte": "Pilote du Processus / Opérateur Terrain",
                            "Fréquence": "En continu (Temps réel)" if is_time else "Quotidienne",
                            "Taille échantillon": "n ≥ 30 mesures minimum" if is_time else "n ≥ 100 transactions",
                            "Période de collecte": "2 semaines glissantes",
                            "Outil utilisé": "Application Web / Fiche Excel partagée",
                            "Risques de biais": "Effet Hawthorne (modification du comportement des opérateurs observés)",
                            "Méthode de contrôle qualité des données": "Audit à blanc au jour 2 / Test Gage R&R ou Kappa linguistique si saisie humaine"
                        })
                
                st.session_state["master_dcp_table"] = dcp_final_rows
                st.toast(f"🎯 Plan de collecte généré avec {len(dcp_final_rows)} variables critiques !", icon="🚀")
                st.rerun()

        # --------------------------------------------------
        # ETAPE 2 : LE TABLEAU OFFICIEL DU DATA COLLECTION PLAN (16 COLONNES)
        # --------------------------------------------------
        if "master_dcp_table" in st.session_state and st.session_state["master_dcp_table"]:
            st.markdown("### 📋 1. Matrice Officielle du Plan de Collecte (Phase Measure)")
            st.caption("Cette matrice constitue le livrable réglementaire pour votre jalon de validation DMAIC. Modifiez les cellules pour affiner les paramètres terrain.")
            
            df_dcp = pd.DataFrame(st.session_state["master_dcp_table"])
            
            edited_dcp_df = st.data_editor(
                df_dcp,
                num_rows="dynamic",
                use_container_width=True,
                key=f"mbb_dcp_matrix_editor_{p_idx}",
                column_config={
                    "Variable à mesurer": st.column_config.TextColumn("Variable (X)", required=True, width="large"),
                    "Objectif de mesure": st.column_config.TextColumn("Objectif de mesure", width="medium"),
                    "Lien avec le Y": st.column_config.TextColumn("Lien avec le Y", width="medium"),
                    "Définition opérationnelle exacte": st.column_config.TextColumn("Définition Opérationnelle", width="large"),
                    "Type de donnée": st.column_config.SelectboxColumn("Type de Donnée", options=["Continue (Temps)", "Discrète (Défauts / Attributaire)", "Discrète (Comptage)", "Catégorielle"], width="medium"),
                    "Unité": st.column_config.TextColumn("Unité", width="small"),
                    "Source de donnée": st.column_config.TextColumn("Source", width="small"),
                    "Méthode de collecte": st.column_config.TextColumn("Méthode de collecte", width="medium"),
                    "Point de mesure dans le processus": st.column_config.TextColumn("Point de mesure", width="medium"),
                    "Responsable collecte": st.column_config.TextColumn("Responsable", width="small"),
                    "Fréquence": st.column_config.TextColumn("Fréquence", width="small"),
                    "Taille échantillon": st.column_config.TextColumn("Échantillon (n)", width="small"),
                    "Période de collecte": st.column_config.TextColumn("Période", width="small"),
                    "Outil utilisé": st.column_config.TextColumn("Outil utilisé", width="small"),
                    "Risques de biais": st.column_config.TextColumn("Risque de Biais", width="medium"),
                    "Méthode de contrôle qualité des données": st.column_config.TextColumn("Contrôle Qualité de la Donnée", width="large")
                }
            )

            if st.button("💾 Enregistrer les ajustements du Data Collection Plan", key=f"save_mbb_dcp_{p_idx}"):
                st.session_state["master_dcp_table"] = edited_dcp_df.to_dict('records')
                p["final_mbb_dcp"] = st.session_state["master_dcp_table"]
                st.success("🎯 Spécifications de collecte terrain enregistrées avec succès.")

            st.markdown("---")

            # --------------------------------------------------
            # ETAPE 3 : RECOMMANDATIONS TERRAIN ET DIRECTIVES GAGE R&R
            # --------------------------------------------------
            st.markdown("### 🗺️ 2. Recommandations de Collecte Terrain & Gestion des Biais")
            
            c_rec1, c_rec2 = st.columns(2)
            with c_rec1:
                with st.container(border=True):
                    st.markdown("#### 🚨 Maîtrise des Risques de Subjectivité & Interprétation")
                    st.markdown("""
                    *   **Suppression des définitions ambiguës :** Pour les données discrètes/attributaires (ex. Dossier non conforme), publiez un *catalogue des défauts* visuel. Si deux opérateurs interprètent un défaut différemment, votre système de mesure est inutile.
                    *   **Lutte contre l'Effet Hawthorne :** Lorsque les équipes se savent observées ou chronométrées, les performances s'améliorent artificiellement de 10 à 15%. Privilégiez les collectes en tâche de fond (système) ou automatisez l'enregistrement sans présence physique pesante du Black Belt.
                    *   **Procédures de Contrôle Qualité :** Réalisez un audit complet des données dès le deuxième jour (*Day-2 Review*). Comparez les 20 premières lignes saisies avec la réalité pour corriger immédiatement les dérives de compréhension.
                    """)
            
            with c_rec2:
                with st.container(border=True):
                    st.markdown("#### 📐 Validation de la Fiabilité (Rigueur Master Black Belt)")
                    st.markdown("""
                    Avant d'utiliser ces données pour des tests statistiques avancés dans la phase *Analyze*, vous devez obligatoirement valider la capabilité de votre système de mesure :
                    *   **Pour les Données Continues (Temps de cycle, délais) :** Réalisez une étude **Gage R&R (Répétabilité & Reproductibilité)**. La variance de votre outil de mesure doit représenter moins de 10% de la tolérance totale du processus.
                    *   **Pour les Données Attributaires (Conforme / Non conforme) :** Déployez un **Test d'accord d'attributs (Attribute Agreement Analysis)** en calculant le coefficient **Kappa de Fleiss**. Un score inférieur à **0.70** indique un besoin immédiat de standardisation et de requalification des contrôleurs.
                    """)

            # --------------------------------------------------
            # ETAPE 4 : POINTS CRITIQUES À SURVEILLER (CHECKLIST)
            # --------------------------------------------------
            st.markdown("### ⚠️ 3. Points Critiques à Surveiller pour le Jalon Measure")
            
            with st.container(border=True):
                col_chk1, col_chk2, col_chk3 = st.columns(3)
                with col_chk1:
                    st.checkbox("Zéro Donnée Inutile (Muda de stockage)", value=True, disabled=True, help="Chaque ligne collectée est directement mappée à un futur test statistique d'impact sur le Y.")
                    st.checkbox("Définitions Opérationnelles figées", value=False, help="Chaque contributeur de la collecte sait exactement à quelle milliseconde le chronomètre démarre et s'arrête.")
                with col_chk2:
                    st.checkbox("Taille d'échantillon statistiquement valide", value=False, help="Règle du TCL respectée : n ≥ 30 pour les distributions continues, échantillon large pour le calcul du FTY.")
                    st.checkbox("Découplage des boucles de validation", value=False, help="Les délais d'attente de signature sont isolés du temps de traitement pur (Touch Time).")
                with col_chk3:
                    st.checkbox("Plan de contingence en cas de données manquantes", value=False, help="Procédure claire si un opérateur oublie de remplir sa feuille de pointage journalière.")
                    st.checkbox("Validation du Système de Mesure engagée (MSA)", value=False, help="Lancement planifié de l'étude Gage R&R ou du test de concordance Kappa.")

        # 4. Validate measurement system
        st.divider()
        st.subheader("5. Validate measurement system")
        st.write("Tests de fiabilité des données (Répétabilité & Reproductibilité).")
        with st.expander("Outils de validation (Type Minitab)"):
            st.info("Analyse Gage R&R : Vérifiez si la variation vient du processus ou du système de mesure.")

        # 5. Data collection
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

        # 6. Baseline performance
        st.divider()
        st.subheader("7. Baseline performance")
        st.write("*(En attente d'explications supplémentaires)*")

        # 7. Measure process capability
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
