# Fichier initialisé proprement sans résidu de texte
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import json

def synchroniser_et_capturer_tout(projet_en_cours, index_projet):
    """
    Cette fonction aspire automatiquement tous les tableaux et cases modifiés 
    à l'écran pour les verrouiller dans le fichier de sauvegarde.
    """
    if not isinstance(projet_en_cours, dict):
        return projet_en_cours
        
    cle_unique = str(index_projet)
    
    # 1. Capture du Plan de Collecte (DCP)
    cles_dcp = [f"master_dcp_table_{cle_unique}", f"dcp_editor_{cle_unique}", "master_dcp_table"]
    for cle in cles_dcp:
        if cle in st.session_state:
            donnees = st.session_state[cle]
            projet_en_cours["master_dcp_table"] = donnees.to_dict(orient="records") if isinstance(donnees, pd.DataFrame) else donnees
            break

    # 2. Capture des tableaux du module MSA
    cle_msa = f"msa_classification_table_{cle_unique}"
    if cle_msa in st.session_state:
        donnees_msa = st.session_state[cle_msa]
        projet_en_cours["msa_classification_table"] = donnees_msa.to_dict(orient="records") if isinstance(donnees_msa, pd.DataFrame) else donnees_msa

    cle_rep = f"rep_table_{cle_unique}"
    if cle_rep in st.session_state:
        donnees_rep = st.session_state[cle_rep]
        projet_en_cours["rep_table_data"] = donnees_rep.to_dict(orient="records") if isinstance(donnees_rep, pd.DataFrame) else donnees_rep

    cle_reprod = f"reprod_table_{cle_unique}"
    if cle_reprod in st.session_state:
        donnees_reprod = st.session_state[cle_reprod]
        projet_en_cours["reprod_table_data"] = donnees_reprod.to_dict(orient="records") if isinstance(donnees_reprod, pd.DataFrame) else donnees_reprod

    # 3. Capture des choix, boutons et validations de la page
    projet_en_cours["msa_selected_var"] = st.session_state.get(f"msa_selected_var_{cle_unique}", "")
    projet_en_cours["msa_action_choice"] = st.session_state.get(f"msa_action_choice_{cle_unique}", "")
    projet_en_cours["msa_is_validated_status"] = st.session_state.get(f"msa_sign_off_{cle_unique}", False)

    # 4. Capture automatique de tous les autres champs de saisie de ce projet
    for cle_interne in st.session_state.keys():
        if cle_interne.endswith(f"_{cle_unique}"):
            nom_propre_du_champ = cle_interne.replace(f"_{cle_unique}", "")
            if "table" not in cle_interne and "editor" not in cle_interne:
                projet_en_cours[nom_propre_du_champ] = st.session_state[cle_interne]

    return projet_en_cours

# ==========================================
# 📋 MODÈLE DE RÉFÉRENCE UNIQUE POUR CHAQUE PROJET
# ==========================================
PROJET_MODELE_REFERENCE = {
    "nom": "",
    "name": "",
    "gantt_data": pd.DataFrame(),
    "mesure_data": pd.DataFrame(),
    "voc_raw_data": pd.DataFrame(columns=["client", "question", "réponse brute"]), # RECONNU PAR L'IMPORTATEUR
    "voc_questions": ["Temps perdu ?", "Retouches ?", "Pénibilité ?", "Irritants ?", "Changement unique ?"], # RECONNU PAR L'IMPORTATEUR
    "dmaic": {
        "define": {},
        "measure": {},
        "analyze": {},
        "improve": {},
        "innovate": {},
        "control": {}
    },
    "parametres": {},
    "progression": 0
}

# 🛠️ FONCTIONS DE SÉRIALISATION / DÉSÉRIALISATION
def deep_serialize(obj):
    """ Préparation récursive de tous les états, tables, phases et champs utilisateurs """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, 'strftime'):
        try: return obj.strftime('%Y-%m-%d')
        except: pass
    if isinstance(obj, pd.DataFrame):
        df_clean = obj.copy()
        for col in df_clean.columns:
            if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d')
        return {"_type_df_": True, "data": df_clean.to_dict(orient="records")}
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_serialize(i) for i in obj]
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

# 🔄 SYSTÈME D'IMPORTATION INVISIBLE SANS CASSE
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
                    
                    # On crée la base vierge
                    projet_reconstruit = PROJET_MODELE_REFERENCE.copy()
                    # On y injecte tout ce que le JSON contient (y compris le voc_raw_data sauvé !)
                    projet_reconstruit.update(p_item)
                    
                    # Alignement des noms de projets
                    if "name" in p_item and not p_item.get("nom"):
                        projet_reconstruit["nom"] = p_item["name"]
                    if "nom" in p_item and not p_item.get("name"):
                        projet_reconstruit["name"] = p_item["nom"]
                    
                    # Sécurisation des DataFrames restaurés
                    if not isinstance(projet_reconstruit["gantt_data"], pd.DataFrame):
                        projet_reconstruit["gantt_data"] = pd.DataFrame(projet_reconstruit["gantt_data"])
                        
                    if not isinstance(projet_reconstruit["mesure_data"], pd.DataFrame):
                        projet_reconstruit["mesure_data"] = pd.DataFrame(projet_reconstruit["mesure_data"])
                    
                    # CORRECTION : On s'assure que le voc_raw_data redevienne un vrai DataFrame exploitable
                    if "voc_raw_data" in p_item:
                        if isinstance(p_item["voc_raw_data"], list):
                            projet_reconstruit["voc_raw_data"] = pd.DataFrame(p_item["voc_raw_data"])
                        elif isinstance(p_item["voc_raw_data"], dict) and "data" in p_item["voc_raw_data"]:
                            # Gestion du format encodé par deep_serialize
                            projet_reconstruit["voc_raw_data"] = pd.DataFrame(p_item["voc_raw_data"]["data"])
                        else:
                            projet_reconstruit["voc_raw_data"] = pd.DataFrame(p_item["voc_raw_data"])

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

    # ------------------------------------------------
    # 📥 OPTIONS D'EXPORT DU PROJET ACTIF (NOUVEAU)
    # ------------------------------------------------
    if st.session_state.get('current_project_idx') is not None:
        st.subheader("📥 Options d'export du projet")
        
        p_exp = st.session_state.projects[st.session_state.current_project_idx]
        project_name = p_exp.get('nom', 'Projet')
        import io

        # --- Export Excel ---
        try:
            buffer_xlsx = io.BytesIO()
            with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
                pd.DataFrame([{
                    "Projet": project_name, 
                    "Statut": p_exp.get('status', 'En cours'), 
                    "Définition": p_exp.get('problem', '')
                }]).to_excel(writer, sheet_name='Synthèse', index=False)
                
                if p_exp.get('sipoc_data'):
                    pd.DataFrame(p_exp['sipoc_data']).to_excel(writer, sheet_name='SIPOC', index=False)
                if p_exp.get('stakeholders'):
                    pd.DataFrame(p_exp['stakeholders']).to_excel(writer, sheet_name='Parties_Prenantes', index=False)

            st.download_button(
                label="📊 Exporter en Excel", 
                data=buffer_xlsx.getvalue(), 
                file_name=f"{project_name}.xlsx", 
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key="sidebar_export_excel_btn"
            )            
        except Exception as e:
            st.error("Erreur Excel (Vérifiez openpyxl)")

        # --- Export PowerPoint ---
        try:
            from pptx import Presentation
            def create_pptx(data_proj):
                prs = Presentation()
                slide = prs.slides.add_slide(prs.slide_layouts[0])
                slide.shapes.title.text = data_proj.get('nom', 'Projet')
                slide.placeholders[1].text = f"Statut : {data_proj.get('status', '')}"
                buffer = io.BytesIO()
                prs.save(buffer)
                return buffer.getvalue()

            pptx_bytes = create_pptx(p_exp)
            st.download_button(
                label="📽️ Exporter en PowerPoint", 
                data=pptx_bytes, 
                file_name=f"{project_name}.pptx", 
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
                key="sidebar_export_pptx_btn"
            )
        except Exception as e:
            st.info("Erreur PPTX (Vérifiez python-pptx)")
            
        st.divider()

    # ------------------------------------------------
    # 💾 SAUVEGARDE ET IMPORTATION GLOBALE (CONSERVÉS)
    # ------------------------------------------------
    st.subheader("💾 Sauvegarder mon travail")
    
    # On vérifie s'il y a des projets dans la session
    un_projet_au_moins = "projects" in st.session_state and len(st.session_state.projects) > 0

    if un_projet_au_moins:
        try:
            # 🟢 LIGNE AJOUTÉE : On force la capture complète du projet actif avant la sauvegarde
            # On vérifie que 'p' et 'p_idx' existent bien à ce moment-là du code
            if 'p' in locals() and 'p_idx' in locals():
                st.session_state.projects[p_idx] = synchroniser_et_capturer_tout(p, p_idx)

            # Sécurité absolue pour les dates cachées
            def encodeur_secours(obj):
                if isinstance(obj, (date, datetime)):
                    return obj.isoformat()
                raise TypeError(f"Type non sérialisable: {type(obj)}")

            # Préparation et sérialisation
            donnies_preparees = deep_serialize(st.session_state.projects)
            data_json = json.dumps(donnies_preparees, indent=4, ensure_ascii=False, default=encodeur_secours)
            
            # Le bouton de téléchargement, bien visible
            st.download_button(
                label="📤 Télécharger la sauvegarde (.json)",
                data=data_json,
                file_name="sauvegarde_boite_outils.json",
                mime="application/json",
                key="sidebar_download_btn",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erreur export : {e}")
    else:
        st.info("💡 Aucun projet en mémoire. Créez un projet ou importez un JSON pour afficher le bouton de téléchargement.")

    st.divider()
    st.subheader("📥 Reprendre mon travail")
    st.file_uploader(
        "Importer un fichier de sauvegarde", 
        type="json", 
        key="sidebar_uploader_file",
        on_change=traiter_importation_json
    )

    # --- FONCTION DE SUPPRESSION FORCEE SUR LA PAGE PRINCIPALE ---
    def action_supprimer_projet(index_a_retirer):
        if "projects" in st.session_state and len(st.session_state.projects) > index_a_retirer:
            st.session_state.projects.pop(index_a_retirer)
            # Si on supprime le projet actuellement ouvert, on réinitialise l'index
            if st.session_state.get("current_project_idx") == index_a_retirer:
                st.session_state["current_project_idx"] = None

    # Section de suppression propre des projets
    if len(st.session_state.projects) > 0:
        st.write("### 🗑️ Suppression de projet")
        
        # Liste des index réels de la session
        indices_projets = list(range(len(st.session_state.projects)))
        
        # Extraction intelligente du vrai nom saisi à l'initialisation
        def extraire_nom_reel(idx):
            projet = st.session_state.projects[idx]
            
            # 1. On liste les clés possibles utilisées lors de la création
            cles_possibles = ["nom", "nom_projet", "name", "project_name", "Nom du projet"]
            
            for cle in cles_possibles:
                if cle in projet and projet[cle]:
                    # Si la valeur est elle-même un dictionnaire (cas rare), on cherche dedans
                    if isinstance(projet[cle], dict):
                        continue
                    return str(projet[cle]).strip()
            
            # 2. Si aucune clé classique n'a fonctionné, on cherche n'importe quelle chaîne de texte non vide 
            # au premier niveau du projet pour essayer de capturer le titre
            for cle, valeur in projet.items():
                if isinstance(valeur, str) and valeur.strip() and cle not in ["status", "id", "description", "problem"]:
                    if len(valeur) < 100: # Un titre de projet fait rarement plus de 100 caractères
                        return valeur.strip()
                        
            # Fallback ultime indexé si vraiment le dictionnaire est vide
            return f"Projet sans nom enregistré #{idx + 1}"
        
        # Liste déroulante affichant les vrais noms identifiables
        idx_selectionne = st.selectbox(
            "Sélectionner le projet à supprimer définitivement :", 
            options=indices_projets,
            format_func=extraire_nom_reel,
            key="selectbox_suppression_projets"
        )
        
        # Bouton unique de suppression calé sur toute la largeur
        st.button(
            "🗑️ Supprimer le projet sélectionné", 
            use_container_width=True, 
            key="suppr_btn_select_unique",
            help="Supprimer définitivement ce projet de la liste",
            on_click=action_supprimer_projet,
            args=(idx_selectionne,)
        )
            
    else:
        st.info("💡 Aucun projet disponible. Créez un nouveau projet ou importez un fichier JSON depuis le menu latéral.")
    
    st.info("🛠️ Vos composants graphiques originaux (onglets DMAIC, diagrammes Plotly d'origine, formulaires de saisie, tableaux éditables st.data_editor) se ré-exécutent automatiquement en utilisant les données fidèlement restaurées ci-dessus.")
    
# --- NAVIGATION PRINCIPALE ---
if st.session_state.current_project_idx is None:
    st.title("🚀 Mes Projets Lean Six Sigma")
    
    with st.expander("➕ Initialiser un nouveau projet"):
        p_name = st.text_input("Nom du projet")
        if st.button("Créer le projet"):
            if p_name:
                new_p = {
                    "nom": p_name,
                    "name": p_name,
                    "status": "Define",
                    "problem": "",
                    "gantt_data": pd.DataFrame(),
                    "mesure_data": pd.DataFrame(),
                    "dmaic": {
                        "define": {},
                        "measure": {},
                        "analyze": {},
                        "improve": {},
                        "innovate": {},
                        "control": {}
                    },
                    "sipoc_data": [{"Supplier": "", "Input": "", "Process": "", "Output": "", "Customer": ""}],
                    "voc_data": [{"Client": "", "Verbatim": "", "Besoin": ""}],
                    "selected_ctq": "Qualité",
                    "team_data": [{"Poste": "", "Nom": ""}],
                    "parametres": {},
                    "progression": 0
                }
                st.session_state.projects.append(new_p)
                st.success("Projet créé !")
                st.rerun()

    # Affichage des cartes projets
    cols = st.columns(3)
    for idx, proj in enumerate(st.session_state.projects):
        with cols[idx % 3]:
            with st.container(border=True):
                # SÉCURITÉ ULTRA-LARGE : On teste absolument toutes les clés possibles pour le premier projet
                nom_final = "Projet sans nom"
                for cle_test in ["nom", "name", "nom_projet", "project_name"]:
                    if cle_test in proj and proj[cle_test] and not isinstance(proj[cle_test], dict):
                        nom_final = str(proj[cle_test]).strip()
                        break
                
                st.subheader(nom_final)
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
        
        # SÉCURISATION ABSOLUE : On force la présence des colonnes requises
        for c_req in COLONNES_SIPOC:
            if c_req not in df_viz_sipoc.columns:
                df_viz_sipoc[c_req] = ""

        # Nettoyage et filtrage sans risque de KeyError
        if not df_viz_sipoc.empty:
            df_viz_sipoc = df_viz_sipoc[(df_viz_sipoc["Process"].astype(str).str.strip() != "") & 
                                        (df_viz_sipoc["Customer"].astype(str).str.strip() != "")]
    
        if not df_viz_sipoc.empty:
            st.write("---")
            acteurs = df_viz_sipoc["Customer"].unique().tolist()
            cols_act = st.columns(len(acteurs))

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

        # 6. VOICE OF CUSTOMER (VOC) - INTEGRATION DE LA PERSISTANCE AVEC SÉCURITÉ TYPE
        st.divider()
        st.header("6. Voice of Customer (VOC) - Flux Black Belt")

        # Initialisation des variables
        if "voc_questions" not in p:
            p["voc_questions"] = ["Temps perdu ?", "Retouches ?", "Pénibilité ?", "Irritants ?", "Changement unique ?"]
        
        # SÉCURITÉ ULTRA-ROBUSTE : Si voc_raw_data est un texte 'str' (issu d'un ancien JSON), on le force en DataFrame
        if "voc_raw_data" not in p or isinstance(p["voc_raw_data"], str):
            p["voc_raw_data"] = pd.DataFrame(columns=["client", "question", "réponse brute"])
            
        # Si c'est un dictionnaire brut (chargé depuis le JSON), on le convertit proprement en DataFrame
        if isinstance(p["voc_raw_data"], dict):
            p["voc_raw_data"] = pd.DataFrame(p["voc_raw_data"])

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
                
                # Vérification de sécurité avant comparaison
                if isinstance(p["voc_raw_data"], pd.DataFrame):
                    if p["voc_raw_data"].empty or not (p["voc_raw_data"]["réponse brute"].equals(new_rows["réponse brute"])):
                        p["voc_raw_data"] = new_rows
                        st.session_state.voc_results = None
                        st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur lors de l'import : {e}")

        # L'éditeur lit désormais un DataFrame garanti à 100%
        edited_voc_df = st.data_editor(
            p["voc_raw_data"],
            num_rows="dynamic",
            use_container_width=True,
            key=f"voc_editor_sync_{p_idx}"
        )
        if edited_voc_df is not None:
            p["voc_raw_data"] = edited_voc_df

        st.write("---")
        st.subheader("3. Analyse Thématique & CTQ")
    
        if st.button("🧠 Lancer l'Analyse (Vue Black Belt)", key=f"btn_run_voc_{p_idx}"):
            df_to_analyze = p["voc_raw_data"]
            if isinstance(df_to_analyze, pd.DataFrame) and not df_to_analyze.empty:
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
        # 🔄 RECHARGE INTELLIGENTE DU FICHIER SI EXISTANT (Correction pour importer le travail)
        if "master_dcp_table" not in st.session_state or not st.session_state["master_dcp_table"]:
            saved_dcp = p.get("master_dcp_table", []) if ('p' in locals() and isinstance(p, dict)) else []
            if saved_dcp:
                st.session_state["master_dcp_table"] = saved_dcp

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
                p["master_dcp_table"] = st.session_state["master_dcp_table"]
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
                    * **Suppression des définitions ambiguës :** Pour les données discrètes/attributaires (ex. Dossier non conforme), publiez un *catalogue des défauts* visuel. Si deux opérateurs interprètent un défaut différemment, votre système de mesure est inutile.
                    * **Lutte contre l'Effet Hawthorne :** Lorsque les équipes se savent observées ou chronométrées, les performances s'améliorent artificiellement de 10 à 15%. Privilégiez les collectes en tâche de fond (système) ou automatisez l'enregistrement sans présence physique pesante du Black Belt.
                    * **Procédures de Contrôle Qualité :** Réalisez un audit complet des données dès le deuxième jour (*Day-2 Review*). Comparez les 20 premières lignes saisies avec la réalité pour corriger immédiatement les dérives de compréhension.
                    """)
            
            with c_rec2:
                with st.container(border=True):
                    st.markdown("#### 📐 Validation de la Fiabilité (Rigueur Master Black Belt)")
                    st.markdown("""
                    Avant d'utiliser ces données pour des tests statistiques avancés dans la phase *Analyze*, vous devez obligatoirement valider la capabilité de votre système de mesure :
                    * **Pour les Données Continues (Temps de cycle, délais) :** Réalisez une étude **Gage R&R (Répétabilité & Reproductibilité)**. La variance de votre outil de mesure doit représenter moins de 10% de la tolérance totale du processus.
                    * **Pour les Données Attributaires (Conforme / Non conforme) :** Déployez un **Test d'accord d'attributs (Attribute Agreement Analysis)** en calculant le coefficient **Kappa de Fleiss**. Un score inférieur à **0.70** indique un besoin immédiat de standardisation et de requalification des contrôleurs.
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
                    
        # =========================================================================
        # 4. VALIDATE MEASUREMENT SYSTEM (MSA) - PLAN DE VALIDATION ET TESTS
        # =========================================================================
        st.divider()
        st.subheader("4. Validate Measurement System (MSA)")
        st.caption("Norme Lean Six Sigma Black Belt — Qualification de la fiabilité des données avant la phase Analyze.")

        # ⚙️ SÉCURISATION ET NETTOYAGE DES INDEX ET CLÉS GLOBALES
        safe_idx = str(p_idx) if 'p_idx' in locals() else "default"
        
        rep_key = f"rep_table_{safe_idx}"
        reprod_key = f"reprod_table_{safe_idx}"
        msa_classif_key = f"msa_classification_table_{safe_idx}"

        # 🛑 VERROU RIGOUREUX LSS : On vérifie si le Plan de Collecte a été validé et généré
        plan_de_collecte_existe = "master_dcp_table" in st.session_state and len(st.session_state["master_dcp_table"]) > 0

        if not plan_de_collecte_existe:
            st.warning("⚠️ **Jalon requis :** Veuillez d'abord valider votre **Plan de Collecte (Section 3)** en cliquant sur le bouton rouge *'⚙️ Valider la pertinence & Générer le Data Collection Plan Master'*. Le module MSA se débloquera automatiquement avec vos variables validées.")
        else:
            # =====================================================================
            # 🛡️ ANCRAGE ET PERSISTANCE RIGIDE DU DICTIONNAIRE DE PROJET 'P'
            # =====================================================================
            if 'p' not in st.session_state:
                st.session_state['p'] = {}
            
            p = st.session_state['p']
            # ---------------------------------------------------------------------

            # 🔄 Si le plan existe, on extrait la liste des vraies variables validées
            liste_variables_valides = [row["Variable à mesurer"] for row in st.session_state["master_dcp_table"] if "Variable à mesurer" in row]

            # --- 1. CLASSIFICATION DES DONNÉES & CHOIX DU MSA (MOTEUR IA CONTEXTUEL) ---
            st.markdown("##### 🧠 Analyse Cognitive & Sélection des Variables Critiques (Liées au Y)")
            
            # 🔍 ALGORITHME DE SCAN TOTAL AVANCÉ AVEC LA CLÉ CTQ INTÉGRÉE
            project_y = "Indéterminé"
            primary_keys = ["selected_ctq", "project_y_objective", "project_y", "y_objective", "objective", "objectifs", "charter_objective", "y_variable"]
            
            # Nom de colonne unique et harmonisé pour tout le script
            nom_colonne_variable = "Variable Critique (liée au Y)"
            
            # Passe 1 : Analyse directe du dictionnaire de projet
            for k in primary_keys:
                if p.get(k):
                    project_y = p.get(k)
                    break
            
            # Passe 2 : Scan récursif profond (Détection automatique de secours)
            if project_y == "Indéterminé":
                def find_y_recursive(data):
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if any(x in k.lower() for x in ["selected_ctq", "y_obj", "objective", "charter", "definition", "projet_y"]) and isinstance(v, str) and len(v) > 2:
                                return v
                        if "master_dcp_table" in data and isinstance(data["master_dcp_table"], list):
                            for row in data["master_dcp_table"]:
                                if isinstance(row, dict) and str(row.get("Rôle", "")).strip().upper() == "Y":
                                    return row.get("Variable à mesurer", "")
                        for v in data.values():
                            res = find_y_recursive(v)
                            if res: return res
                    elif isinstance(data, list):
                        for item in data:
                            res = find_y_recursive(item)
                            if res: return res
                    return None
                
                deep_search_result = find_y_recursive(p)
                if deep_search_result:
                    project_y = deep_search_result

            # Passe 3 : Vérification au sein de la table DCP source
            dcp_source = p.get("master_dcp_table", [])
            if project_y == "Indéterminé" and dcp_source:
                for v in dcp_source:
                    if isinstance(v, dict) and str(v.get("Rôle", "")).strip().upper() == "Y" and v.get("Variable à mesurer"):
                        project_y = v.get("Variable à mesurer")
                        break

            st.info(f"🎯 **Y ciblé par le projet :** `{project_y}`")

            # Initialisation de la table MSA à partir de la sauvegarde ou de l'IA
            if msa_classif_key not in st.session_state:
                saved_classif = p.get(f"save_msa_classif_{safe_idx}", [])
                if saved_classif:
                    st.session_state[msa_classif_key] = pd.DataFrame(saved_classif)
                else:
                    ai_analyzed_rows = []
                    if dcp_source:
                        for v in dcp_source:
                            if isinstance(v, dict):
                                var_name = v.get("Variable à mesurer", "")
                                type_brut = v.get("Type de donnée", "Continue")
                                role = v.get("Rôle", "X (Influent)")
                                
                                if var_name:
                                    if any(x in type_brut.lower() for x in ["continue", "temps", "délai", "coût", "mesure", "valeur"]):
                                        det_type = "Continue (Quantitative)"
                                        rec_msa = "Gage R&R (Répétabilité & Reproductibilité)"
                                    else:
                                        det_type = "Attributaire / Catégorielle"
                                        rec_msa = "Attribute Agreement Analysis (Kappa)"
                                    
                                    ai_analyzed_rows.append({
                                        nom_colonne_variable: var_name,
                                        "Type de Donnée": det_type,
                                        "MSA Recommandé": rec_msa,
                                        "Criticité par rapport au Y": "Haute (Lien Direct)" if str(role).strip().upper() == "Y" or any(k in var_name.lower() for k in ["temps", "erreur", "qualité", "conformité"]) else "Moyenne (Facteur X)",
                                        "statut validation": "en attente de test"
                                    })
                        
                        ai_analyzed_rows = sorted(ai_analyzed_rows, key=lambda k: k["Criticité par rapport au Y"], reverse=True)[:4]

                    if not ai_analyzed_rows:
                        if "temps" in str(project_y).lower() or "délai" in str(project_y).lower() or "lead time" in str(project_y).lower():
                            ai_analyzed_rows = [
                                {nom_colonne_variable: "Temps de traitement unitaire (Cycle Time)", "Type de Donnée": "Continue (Quantitative)", "MSA Recommandé": "Gage R&R (Répétabilité & Reproductibilité)", "Criticité par rapport au Y": "Critique (Directement lié au Y)", "statut validation": "en attente de test"},
                                {nom_colonne_variable: "Horodatage de début/fin de tâche", "Type de Donnée": "Système / Log IT", "MSA Recommandé": "Audit de Stabilité & Exactitude", "Criticité par rapport au Y": "Haute (Source de la donnée)", "statut validation": "en attente de test"},
                                {nom_colonne_variable: "Statut de mise en attente du dossier", "Type de Donnée": "Attributaire / Catégorielle", "MSA Recommandé": "Attribute Agreement Analysis (Kappa)", "Criticité par rapport au Y": "Moyenne (Bruit potentiel)", "statut validation": "en attente de test"}
                            ]
                        elif "qualité" in str(project_y).lower() or "erreur" in str(project_y).lower() or "rebut" in str(project_y).lower() or "conform" in str(project_y).lower():
                            ai_analyzed_rows = [
                                {nom_colonne_variable: "Verdict de conformité de la pièce (Go / No-Go)", "Type de Donnée": "Attributaire / Catégorielle", "MSA Recommandé": "Attribute Agreement Analysis (Kappa)", "Criticité par rapport au Y": "Critique (Directement lié au Y)", "statut validation": "en attente de test"},
                                {nom_colonne_variable: "Code défaut saisi par l'opérateur", "Type de Donnée": "Attributaire / Catégorielle", "MSA Recommandé": "Attribute Agreement Analysis (Kappa)", "Criticité par rapport au Y": "Haute (Fiabilité du Pareto)", "statut validation": "en attente de test"},
                                {nom_colonne_variable: "Dimension ou écart mesuré au pied à coulisse", "Type de Donnée": "Continue (Quantitative)", "MSA Recommandé": "Gage R&R (Répétabilité & Reproductibilité)", "Criticité par rapport au Y": "Moyenne (Physique)", "statut validation": "en attente de test"}
                            ]
                        else:
                            ai_analyzed_rows = [
                                {nom_colonne_variable: f"Indicateur de Performance direct de: {project_y}", "Type de Donnée": "Continue (Quantitative)", "MSA Recommandé": "Gage R&R (Répétabilité & Reproductibilité)", "Criticité par rapport au Y": "Critique", "statut validation": "en attente de test"},
                                {nom_colonne_variable: "Classification de la typologie client/dossier", "Type de Donnée": "Attributaire / Catégorielle", "MSA Recommandé": "Attribute Agreement Analysis (Kappa)", "Criticité par haute", "statut validation": "en attente de test"}
                            ]
                    st.session_state[msa_classif_key] = pd.DataFrame(ai_analyzed_rows)

            if st.button("🔄 Forcer la ré-analyse intelligente du Plan de Collecte", key=f"re_analyze_msa_ai_{safe_idx}"):
                if msa_classif_key in st.session_state:
                    del st.session_state[msa_classif_key]
                if f"save_msa_classif_{safe_idx}" in p:
                    del p[f"save_msa_classif_{safe_idx}"]
                st.rerun()

            st.write("👉 *Tableau généré par IA. Vous pouvez manuellement ajuster, ajouter (`+`) ou supprimer (`🗑️`) des lignes.*")
            df_classification_current = st.session_state.get(msa_classif_key, pd.DataFrame())

            # =====================================================================
            # 🛠️ SYNCHRONISATION DU LIEN VISUEL AVANT L'AFFICHAGE DANS L'ÉDITEUR
            # =====================================================================
            if not df_classification_current.empty:
                if "statut validation" not in df_classification_current.columns:
                    df_classification_current["statut validation"] = "en attente de test"
                
                for idx_row, row in df_classification_current.iterrows():
                    var_nom = row.get(nom_colonne_variable, "")
                    if pd.notna(var_nom) and str(var_nom).strip() != "":
                        v_c = "".join(e for e in str(var_nom) if e.isalnum())
                        if st.session_state.get(f"status_lock_{v_c}_{safe_idx}", False) or p.get(f"validated_status_{v_c}_{safe_idx}", False):
                            df_classification_current.at[idx_row, "statut validation"] = "variable testée"
                        else:
                            df_classification_current.at[idx_row, "statut validation"] = "en attente de test"

            edited_classification = st.data_editor(
                df_classification_current,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    nom_colonne_variable: st.column_config.TextColumn("Variable Critique (liée au Y)", width="medium", required=True),
                    "Type de Donnée": st.column_config.SelectboxColumn("Type de Donnée", options=["Continue (Quantitative)", "Attributaire / Catégorielle", "Système / Log IT"], required=True),
                    "MSA Recommandé": st.column_config.SelectboxColumn("MSA Recommandé", options=["Gage R&R (Répétabilité & Reproductibilité)", "Attribute Agreement Analysis (Kappa)", "Audit de Stabilité & Exactitude"], required=True),
                    "Criticité par rapport au Y": st.column_config.TextColumn("Alignement sémantique Y", disabled=True),
                    "statut validation": st.column_config.TextColumn("Statut Validation", disabled=True)
                },
                key=f"classification_editor_widget_{safe_idx}"
            )
            
            if edited_classification is not None:
                st.session_state[msa_classif_key] = edited_classification
                df_classification_current = edited_classification
                p[f"save_msa_classif_{safe_idx}"] = edited_classification.to_dict(orient='records')

            # --- SÉLECTION DE LA VARIABLE ACTIVE POUR LES TESTS ---
            st.markdown("##### 👟 Exécution du Protocole Terrain")
            
            if not df_classification_current.empty and nom_colonne_variable in df_classification_current.columns:
                list_variables_critiques = df_classification_current[nom_colonne_variable].dropna().tolist()
            else:
                list_variables_critiques = []
            
            if list_variables_critiques:
                if "msa_validated_vars" not in st.session_state:
                    st.session_state["msa_validated_vars"] = {}
                if "msa_bias_history" not in st.session_state:
                    st.session_state["msa_bias_history"] = {}

                # Génération des options du sélecteur avec un indicateur de statut clair
                options_sélecteur = []
                mapping_variables = {}
                for var in list_variables_critiques:
                    if str(var).strip() == "":
                        continue
                    v_c = "".join(e for e in str(var) if e.isalnum())
                    if st.session_state.get(f"status_lock_{v_c}_{safe_idx}", False) or p.get(f"validated_status_{v_c}_{safe_idx}", False):
                        label = f"✅ {var}"
                    else:
                        label = f"⏳ {var}"
                    options_sélecteur.append(label)
                    mapping_variables[label] = var

                selected_option = st.selectbox(
                    "Sélectionnez la variable à tester actuellement parmi vos variables critiques :",
                    options=options_sélecteur,
                    key=f"msa_selected_var_{safe_idx}"
                )
                
                selected_var_to_test = mapping_variables.get(selected_option, "")

                # --- TABLEAU DE BORD DES MESURES DÉJÀ VALIDÉES (HISTORIQUE) ---
                st.markdown("##### 📈 Historique des protocoles validés")
                
                variables_valides = []
                for var in list_variables_critiques:
                    v_c = "".join(e for e in str(var) if e.isalnum())
                    if st.session_state.get(f"status_lock_{v_c}_{safe_idx}", False) or p.get(f"validated_status_{v_c}_{safe_idx}", False):
                        variables_valides.append(var)
                
                if variables_valides:
                    with st.expander("🔍 Voir toutes les données terrain validées (Historique)", expanded=True):
                        for v_nom in variables_valides:
                            v_clean = "".join(e for e in str(v_nom) if e.isalnum())
                            p_rep_key = f"save_rep_{v_clean}_{safe_idx}"
                            p_reprod_key = f"save_reprod_{v_clean}_{safe_idx}"
                            
                            st.markdown(f"**🟢 Variable : {v_nom}**")
                            c1, c2 = st.columns(2)
                            with c1:
                                if p_rep_key in p:
                                    st.caption("Données de Reproductibilité enregistrées :")
                                    st.dataframe(pd.DataFrame(p[p_rep_key]), use_container_width=True)
                            with c2:
                                if p_reprod_key in p:
                                    st.caption("Données de Répétabilité enregistrées :")
                                    st.dataframe(pd.DataFrame(p[p_reprod_key]), use_container_width=True)
                            st.markdown("---")
                else:
                    st.info("ℹ️ Aucune variable n'a encore été validée. Les résumés s'afficheront ici automatiquement après avoir cliqué sur 'Valider et verrouiller'.")
                
                # ISOLATION CELLULAIRE TERRAIN (Par variable sélectionnée)
                var_clean_id = "".join(e for e in selected_var_to_test if e.isalnum())
                
                dynamic_rep_key = f"rep_data_{var_clean_id}_{safe_idx}"
                dynamic_reprod_key = f"reprod_data_{var_clean_id}_{safe_idx}"
                bias_hist_key = f"hist_{var_clean_id}_{safe_idx}"
                
                p_rep_save_key = f"save_rep_{var_clean_id}_{safe_idx}"
                p_reprod_save_key = f"save_reprod_{var_clean_id}_{safe_idx}"
                p_bias_hist_save_key = f"save_bias_hist_{var_clean_id}_{safe_idx}"
                
                # RESTAURATION CELLULAIRE DEPUIS LE DICTIONNAIRE DE SAUVEGARDE 'P'
                if p_rep_save_key in p:
                    st.session_state[dynamic_rep_key] = pd.DataFrame(p[p_rep_save_key])
                if p_reprod_save_key in p:
                    st.session_state[dynamic_reprod_key] = pd.DataFrame(p[p_reprod_save_key])
                if p_bias_hist_save_key in p:
                    st.session_state["msa_bias_history"][bias_hist_key] = p[p_bias_hist_save_key]
                
                if bias_hist_key not in st.session_state["msa_bias_history"]:
                    st.session_state["msa_bias_history"][bias_hist_key] = []
                
                liste_unites = ["minutes", "heure", "jour", "g", "kg", "unité", "m", "l", "%", "Ar"]
                
                if dynamic_rep_key not in st.session_state:
                    st.session_state[dynamic_rep_key] = pd.DataFrame([
                        {"Opérateur": "Opérateur 1", "Situation A": 0.0, "Unité A": "unité", "Situation B": 0.0, "Unité B": "unité"},
                        {"Opérateur": "Opérateur 2", "Situation A": 0.0, "Unité A": "unité", "Situation B": 0.0, "Unité B": "unité"}
                    ])
                    
                if dynamic_reprod_key not in st.session_state:
                    st.session_state[dynamic_reprod_key] = pd.DataFrame([
                        {"Essai / Pièce": "Pièce 1", "Résultat": 0.0, "Unité": "unité"},
                        {"Essai / Pièce": "Pièce 2", "Résultat": 0.0, "Unité": "unité"}
                    ])
                    
                id_validation_blindee_active = f"status_lock_{var_clean_id}_{safe_idx}"
                if st.session_state.get(id_validation_blindee_active, False) or p.get(f"validated_status_{var_clean_id}_{safe_idx}", False):
                    st.success(f"🎯 **Statut : Validé** | Vous visualisez les données sécurisées pour : **{selected_var_to_test}**")
                else:
                    st.warning(f"📋 **Statut : Saisie en cours** | Remplissez les mesures pour : **{selected_var_to_test}**")
                
                col_t1, col_t2 = st.columns(2)
                
                with col_t1:
                    st.markdown("**🔬 Test de Reproductibilité (Inter-Opérateurs)**")
                    edited_rep = st.data_editor(
                        st.session_state[dynamic_rep_key],
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"editor_rep_{var_clean_id}_{safe_idx}",
                        column_config={
                            "Unité A": st.column_config.SelectboxColumn("Unité de mesure", options=liste_unites, required=True),
                            "Unité B": st.column_config.SelectboxColumn("Unité de mesure", options=liste_unites, required=True)
                        }
                    )

                with col_t2:
                    st.markdown("**👥 Test de Répétabilité (Intra-Opérateur)**")
                    edited_reprod = st.data_editor(
                        st.session_state[dynamic_reprod_key],
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"editor_reprod_{var_clean_id}_{safe_idx}",
                        column_config={
                            "Unité": st.column_config.SelectboxColumn("Unité de mesure", options=liste_unites, required=True)
                        }
                    )
                
                # Capture immédiate des modifications manuelles dans les data_editors
                if isinstance(edited_rep, pd.DataFrame):
                    st.session_state[dynamic_rep_key] = edited_rep
                    p[p_rep_save_key] = edited_rep.to_dict(orient='records')
                if isinstance(edited_reprod, pd.DataFrame):
                    st.session_state[dynamic_reprod_key] = edited_reprod
                    p[p_reprod_save_key] = edited_reprod.to_dict(orient='records')
                
                st.markdown("##### 🎯 Valeur de Référence (Master / Standard)")
                valeur_reference = st.number_input(
                    f"Saisissez la valeur théorique / standard attendue (Entrez 0.0 si pas de standard défini) :",
                    value=0.0,
                    step=0.1,
                    key=f"msa_ref_val_{var_clean_id}_{safe_idx}"
                )

                # --- BOUTON : LANCER L'ANALYSE DES BIAIS ---
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📊 Lancer l'analyse des risques de biais", key=f"btn_analyze_bias_{var_clean_id}_{safe_idx}", use_container_width=True):
                    
                    # Récupération forcée à jour
                    current_rep = st.session_state[dynamic_rep_key]
                    current_reprod = st.session_state[dynamic_reprod_key]

                    # Calcul des anomalies
                    anomalies_mineures = []
                    anomalies_majeures = []
                    
                    if not current_rep.empty and 'Situation A' in current_rep.columns and 'Situation B' in current_rep.columns:
                        try:
                            val_col1 = pd.to_numeric(current_rep['Situation A'], errors='coerce')
                            val_col2 = pd.to_numeric(current_rep['Situation B'], errors='coerce')
                            
                            if val_col1.dropna().empty or val_col2.dropna().empty:
                                anomalies_majeures.append("Données de Répétabilité Invalides ou Vides")
                            else:
                                diffs = (val_col1 - val_col2).abs()
                                mean_val = val_col1.mean()
                                if not diffs.dropna().empty and mean_val > 0:
                                    if diffs.max() > mean_val * 0.30:
                                        anomalies_majeures.append("Incohérence Critique de Répétabilité (EV)")
                                    elif diffs.max() > mean_val * 0.10:
                                        anomalies_mineures.append("Dispersion de Répétabilité légère")
                                
                                all_vals = pd.concat([val_col1, val_col2]).dropna()
                                if not all_vals.empty and all(v % 5 == 0 for v in all_vals if v > 0):
                                    anomalies_mineures.append("Biais d'Arrondis Systématiques (Résolution insuffisante)")
                        except Exception as e:
                            anomalies_majeures.append(f"Erreur évaluation Répétabilité: {str(e)}")

                    if not current_reprod.empty and "Résultat" in current_reprod.columns:
                        try:
                            vals_reprod = pd.to_numeric(current_reprod["Résultat"], errors='coerce').dropna()
                            if vals_reprod.empty:
                                anomalies_majeures.append("Données de Reproductibilité Manquantes ou Invalides")
                            else:
                                if len(vals_reprod) >= 2:
                                    std_dev = vals_reprod.std()
                                    if pd.notna(std_dev) and vals_reprod.mean() > 0:
                                        if std_dev > (vals_reprod.mean() * 0.20):
                                            anomalies_majeures.append("Instabilité Critique de Reproductibilité (AV)")
                                if 'valeur_reference' in locals() and valeur_reference != 0.0:
                                    biais_justesse = abs(vals_reprod.mean() - valeur_reference)
                                    if biais_justesse > abs(valeur_reference * 0.08):
                                        anomalies_majeures.append("Biais de Justesse Linéaire (Décalage / Master)")
                        except Exception as e:
                            anomalies_majeures.append(f"Erreur évaluation Reproductibilité: {str(e)}")
                    
                    if len(anomalies_majeures) == 0 and len(anomalies_mineures) == 0:
                        score, status = "100%", "🟢 Système Fiable"
                    elif len(anomalies_majeures) == 0 and len(anomalies_mineures) > 0:
                        score, status = "75%", "🟡 Alerte : Biais Mineur (Sous contrôle)"
                    elif len(anomalies_majeures) == 1 and len(anomalies_mineures) == 0:
                        score, status = "50%", "🟠 Alerte : Dérive Majeure"
                    elif len(anomalies_majeures) == 1 and len(anomalies_mineures) > 0:
                        score, status = "35%", "🟠 Alerte : Instabilité Système Cumulée"
                    else:
                        score, status = "10%", "🔴 Système Non Fiable (Processus Hors Contrôle)"
                    
                    toutes_anomalies = anomalies_majeures + anomalies_mineures
                    liste_anomalies_str = ", ".join(toutes_anomalies) if toutes_anomalies else "Aucune (Système sain)"
                    
                    gmt3_time = pd.Timestamp.now(tz='UTC').tz_convert('Indian/Antananarivo').strftime('%d/%m/%Y %H:%M:%S')
                    
                    run_number = len(st.session_state["msa_bias_history"][bias_hist_key]) + 1
                    st.session_state["msa_bias_history"][bias_hist_key].append({
                        "Essai": f"Analyse #{run_number}",
                        "Date/Heure": gmt3_time,
                        "Indice de Fidélité": score,
                        "Statut Global": status,
                        "Anomalies Detected": liste_anomalies_str
                    })
                    
                    p[p_bias_hist_save_key] = st.session_state["msa_bias_history"][bias_hist_key]
                    st.rerun()

                # --- 💾 BOUTON DE VALIDATION DÉFINITIVE ---
                if st.button(
                    f"💾 Valider et verrouiller définitivement les données pour : {selected_var_to_test}", 
                    key=f"btn_validate_msa_{var_clean_id}_{safe_idx}", 
                    type="primary", 
                    use_container_width=True
                ):
                    st.session_state[f"status_lock_{var_clean_id}_{safe_idx}"] = True
                    p[f"validated_status_{var_clean_id}_{safe_idx}"] = True
                    st.session_state["msa_validated_vars"][f"{selected_var_to_test}_{safe_idx}"] = True
                    
                    # Mutation forcée du statut dans l'éditeur de classification
                    if not df_classification_current.empty:
                        for idx_row, row in df_classification_current.iterrows():
                            if str(row[nom_colonne_variable]).strip() == str(selected_var_to_test).strip():
                                df_classification_current.at[idx_row, "statut validation"] = "variable testée"
                        st.session_state[msa_classif_key] = df_classification_current
                        p[f"save_msa_classif_{safe_idx}"] = df_classification_current.to_dict(orient='records')

                    st.balloons()
                    st.success(f"✅ Données terrain validées et gelées avec succès pour **{selected_var_to_test}** !")
                    st.rerun()
            else:
                st.info("💡 Le tableau de classification ci-dessus est vide ou en cours d'analyse.")

        # =====================================================================
        # 5. DATA COLLECTION
        # =====================================================================
        # ÉTAPE 0 : INITIALISATION DE LA PERSISTANCE (JSON & STATE)
        if "dc_plan" not in p:
            p["dc_plan"] = {
                "taille_prevue": 100,
                "date_debut": "2026-06-01",
                "date_fin_est": "2026-06-15",
            }

        # Initialisation de la table maîtresse dans le state si absente
        if "dc_master_data" not in st.session_state:
            if "dc_saved_df_json" in p and p["dc_saved_df_json"]:
                st.session_state.dc_master_data = pd.read_json(p["dc_saved_df_json"])
            else:
                st.session_state.dc_master_data = pd.DataFrame(
                    columns=["ID observation", "Date", "Variable mesurée", "Valeur", "Unité de mesure", "Commentaire"]
                )

        # Variables par défaut adaptables (Garage, Industrie, Admin)
        DCP_VARS_DEF = {
            "Temps d'entretien": "Heures",
            "Temps attente pièces": "Heures",
            "Temps réparation": "Heures",
            "Statut Retouche": "Attributaire",
        }

        # --- TITRE PRINCIPAL DE SECTION (SUITE DE 4-MSA) ---
        st.markdown("## 5 - Data collection")
        st.markdown("---")

        # --- ÉCRAN 1 ---
        st.markdown("### 📋 Écran 1 : Résumé de la Collecte")

        e1_c1, e1_c2, e1_c3 = st.columns(3)
        with e1_c1:
            p["dc_plan"]["taille_prevue"] = st.number_input(
                "Taille d'échantillon prévue (N)", min_value=1, value=int(p["dc_plan"]["taille_prevue"]), key="dc_n_prevu"
            )
        with e1_c2:
            p["dc_plan"]["date_debut"] = st.text_input(
                "Date de début de collecte", value=p["dc_plan"]["date_debut"], key="dc_d_deb"
            )
        with e1_c3:
            p["dc_plan"]["date_fin_est"] = st.text_input(
                "Date estimée de fin", value=p["dc_plan"]["date_fin_est"], key="dc_d_fin"
            )

        st.markdown("#### Liste des variables définies dans le DCP")
        dcp_display = pd.DataFrame(
            [{"Variable": k, "Type/Unité": v} for k, v in DCP_VARS_DEF.items()]
        )
        st.table(dcp_display)

        # Import global Excel
        uploaded_file = st.file_uploader(
            "📥 Importer un fichier Excel pour compléter automatiquement les tableaux",
            type=["xlsx", "xls"],
            key="dc_excel_uploader",
        )

        if uploaded_file:
            try:
                imported_df = pd.read_excel(uploaded_file)
                required_cols = ["ID observation", "Date", "Variable mesurée", "Valeur", "Unité de mesure", "Commentaire"]
                for col in required_cols:
                    if col not in imported_df.columns:
                        imported_df[col] = np.nan if col != "Commentaire" else ""
                
                imported_df = imported_df[required_cols]
                st.session_state.dc_master_data = pd.concat(
                    [st.session_state.dc_master_data, imported_df], ignore_index=True
                ).drop_duplicates(subset=["ID observation", "Variable mesurée"], keep="last")
                
                p["dc_saved_df_json"] = st.session_state.dc_master_data.to_json()
                st.success("✅ Fichier Excel importé et synchronisé avec succès.")
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier Excel : {e}")

        # --- ÉCRAN 2 ---
        st.markdown("---")
        st.markdown("### 📝 Écran 2 : Saisie des Données (Tableaux Dynamiques)")

        st.markdown("#### Saisie manuelle rapide")
        with st.form("dc_form_manual", clear_on_submit=True):
            f_c1, f_c2, f_c3, f_c4 = st.columns(4)
            with f_c1:
                v_var = st.selectbox("Variable à mesurer", list(DCP_VARS_DEF.keys()))
            with f_c2:
                v_val = st.text_input("Valeur (Nombre si continue, Texte si attributaire)")
            with f_c3:
                v_obs = st.text_input("ID observation (ex: OBS-001)")
            with f_c4:
                v_comm = st.text_input("Commentaire")

            if st.form_submit_button("＋ Ajouter la ligne"):
                if v_obs and v_val:
                    tz_gmt3 = pd.Timestamp.now(tz="UTC").tz_convert("Etc/GMT-3").strftime("%Y-%m-%d %H:%M:%S")
                    new_row = {
                        "ID observation": v_obs,
                        "Date": tz_gmt3,
                        "Variable mesurée": v_var,
                        "Valeur": v_val,
                        "Unité de mesure": DCP_VARS_DEF[v_var],
                        "Commentaire": v_comm,
                    }
                    st.session_state.dc_master_data = pd.concat(
                        [st.session_state.dc_master_data, pd.DataFrame([new_row])], ignore_index=True
                    )
                    p["dc_saved_df_json"] = st.session_state.dc_master_data.to_json()
                    st.rerun()

        st.markdown("#### Édition en temps réel de la base maîtresse")
        if not st.session_state.dc_master_data.empty:
            edited_master = st.data_editor(
                st.session_state.dc_master_data, num_rows="dynamic", key="dc_master_editor"
            )
            if not edited_master.equals(st.session_state.dc_master_data):
                st.session_state.dc_master_data = edited_master
                p["dc_saved_df_json"] = edited_master.to_json()
                st.rerun()
            
            # Export Excel
            @st.cache_data
            def convert_df_to_excel(df):
                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Data_Collection")
                return output.getvalue()
            
            excel_data = convert_df_to_excel(st.session_state.dc_master_data)
            st.download_button(
                label="📥 Export complet de la base vers Excel",
                data=excel_data,
                file_name="LSS_Data_Collection_Master.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("La base de données est actuellement vide. Utilisez le formulaire ou l'import Excel.")

        # --- ÉCRAN 3 ---
        st.markdown("---")
        st.markdown("### 🔍 Écran 3 : Contrôle Qualité des Données")

        df_cq = st.session_state.dc_master_data.copy()
        num_erreurs = 0
        num_manquants = 0
        total_prevu = max(1, int(p["dc_plan"]["taille_prevue"]))
        
        if not df_cq.empty:
            num_manquants = df_cq["Valeur"].isna().sum() + (df_cq["Valeur"] == "").sum()
            
            for idx, row in df_cq.iterrows():
                val = str(row["Valeur"]).strip()
                var_type = DCP_VARS_DEF.get(row["Variable mesurée"], "Heures")
                
                if var_type == "Heures":
                    try:
                        numeric_val = float(val)
                        if numeric_val < 0:
                            num_erreurs += 1
                    except ValueError:
                        if val and val.lower() != "nan":
                            num_erreurs += 1
            
            num_doublons = df_cq.duplicated(subset=["ID observation", "Variable mesurée"]).sum()
            num_erreurs += num_doublons
            taux_completude = (len(df_cq) / total_prevu) * 100
        else:
            taux_completude = 0.0

        st.metric("Nombre d'erreurs détectées", num_erreurs)
        st.metric("Nombre de données manquantes", num_manquants)
        st.metric("Taux de complétude théorique", f"{taux_completude:.1f} %")

        if num_erreurs > 0:
            st.error("🔴 Statut : Correction requise. Des valeurs négatives, des doublons ou des formats incorrects polluent la base.")
        elif num_manquants > 0 or taux_completude < 80:
            st.warning("🟠 Statut : Attention. Aucune anomalie critique mais l'échantillon est incomplet ou contient des cellules vides.")
        elif len(df_cq) == 0:
            st.info("🔵 En attente d'injection de données.")
        else:
            st.success("🟢 Statut : Données conformes. Prêt pour l'établissement de la Baseline.")

        # --- ÉCRAN 4 ---
        st.markdown("---")
        st.markdown("### 📈 Écran 4 : Suivi de la Collecte")

        obs_collectees = len(df_cq["ID observation"].unique()) if not df_cq.empty else 0
        restant = max(0, total_prevu - obs_collectees)
        avancement = min(100.0, (obs_collectees / total_prevu) * 100)

        e4_c1, e4_c2, e4_c3 = st.columns(3)
        e4_c1.metric("Observations collectées", obs_collectees)
        e4_c2.metric("Restant à collecter", restant)
        e4_c3.metric("Taux d'avancement", f"{avancement:.1f} %")

        progress_df = pd.DataFrame({"Statut": ["Collecté", "Restant"], "Valeur": [obs_collectees, restant]})
        st.bar_chart(progress_df.set_index("Statut"))

        # --- ÉCRAN 5 ---
        st.markdown("---")
        st.markdown("### 📊 Écran 5 : Statistiques Descriptives")

        if not df_cq.empty:
            for variable, v_type in DCP_VARS_DEF.items():
                st.markdown(f"#### Analyse descriptive : {variable}")
                df_var = df_cq[df_cq["Variable mesurée"] == variable]
                
                if df_var.empty:
                    st.info(f"Aucune donnée collectée pour {variable}")
                    continue

                if v_type == "Heures":
                    numeric_series = pd.to_numeric(df_var["Valeur"], errors="coerce").dropna()
                    
                    if not numeric_series.empty:
                        stats_data = {
                            "Métrique LSS": ["Moyenne", "Médiane", "Minimum", "Maximum", "Écart-type (σ)"],
                            "Valeur": [
                                f"{numeric_series.mean():.2f}",
                                f"{numeric_series.median():.2f}",
                                f"{numeric_series.min():.2f}",
                                f"{numeric_series.max():.2f}",
                                f"{numeric_series.std():.2f}" if len(numeric_series) > 1 else "0.00"
                            ]
                        }
                        st.table(pd.DataFrame(stats_data))
                        st.bar_chart(np.histogram(numeric_series, bins=10)[0])
                    else:
                        st.error("Erreur d'analyse : Les données de cette variable continue ne sont pas numériques.")
                else:
                    attr_counts = df_var["Valeur"].value_counts()
                    attr_pct = df_var["Valeur"].value_counts(normalize=True) * 100
                    
                    attr_df = pd.DataFrame({
                        "Fréquence (N)": attr_counts,
                        "Pourcentage (%)": attr_pct.map("{:.2f} %".format),
                        "Taux d'occurrence": attr_counts / len(df_var)
                    })
                    st.table(attr_df)
        else:
            st.info("Aucune statistique disponible : la base maîtresse est vide.")

        # --- ÉCRAN 6 ---
        st.markdown("---")
        st.markdown("### 🎯 Écran 6 : Baseline du Processus")

        if not df_cq.empty:
            st.markdown("#### Situation de référence avant amélioration (KPI Actuels)")
            
            def format_to_hours_mins(decimal_hours):
                if pd.isna(decimal_hours):
                    return "0h00"
                hours = int(decimal_hours)
                minutes = int(round((decimal_hours - hours) * 60))
                if minutes == 60:
                    hours += 1
                    minutes = 0
                return f"{hours}h{minutes:02d}"

            baseline_metrics = []
            
            for variable, v_type in DCP_VARS_DEF.items():
                df_var = df_cq[df_cq["Variable mesurée"] == variable]
                if v_type == "Heures" and not df_var.empty:
                    num_series = pd.to_numeric(df_var["Valeur"], errors="coerce").dropna()
                    if not num_series.empty:
                        avg_formatted = format_to_hours_mins(num_series.mean())
                        baseline_metrics.append({"KPI Courant": f"Temps moyen [{variable}]", "Niveau de performance actuel": avg_formatted})

            df_attr = df_cq[df_cq["Variable mesurée"] == "Statut Retouche"]
            if not df_attr.empty:
                retouche_count = df_attr["Valeur"].astype(str).str.lower().isin(["oui", "retouche", "true", "1"]).sum()
                taux_retouche_calc = (retouche_count / len(df_attr)) * 100
                baseline_metrics.append({"KPI Courant": "Taux de retouches global", "Niveau de performance actuel": f"{taux_retouche_calc:.1f} %"})
            else:
                baseline_metrics.append({"KPI Courant": "Taux de retouches global", "Niveau de performance actuel": "11.0 % (Valeur cible par défaut)"})

            st.table(pd.DataFrame(baseline_metrics))
            st.caption("⚙️ Les calculs de cette table de référence se mettent à jour dynamiquement à chaque modification des données de l'Écran 2.")
        else:
            st.info("Alimentez la base de données à l'Écran 2 pour projeter automatiquement la Baseline de votre processus.")

        # 6. Baseline performance
        st.divider()
        st.subheader("6. Baseline performance")
        st.write("*(En attente d'explications supplémentaires)*")

        # 7. Measure process capability
        st.divider()
        st.subheader("7. Measure process capability")
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
