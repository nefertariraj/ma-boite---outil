import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION DE LA PAGE & STYLE ---
st.set_page_config(page_title="LSS - Personal Toolbox", layout="wide")

# Personnalisation des couleurs (Modifiable dans les paramètres)
if 'primary_color' not in st.session_state:
    st.session_state.primary_color = "#1E3A8A" # Bleu nuit moderne

st.markdown(f"""
    <style>
    .stApp {{ background-color: #FFFFFF; }}
    .stButton>button {{ background-color: {st.session_state.primary_color}; color: white; border-radius: 5px; }}
    .info-box {{ background-color: #F0F4F8; padding: 15px; border-left: 5px solid {st.session_state.primary_color}; border-radius: 5px; margin-bottom: 10px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; }}
    .stTabs [data-baseweb="tab"] {{ font-weight: bold; color: #4B5563; }}
    </style>
    """, unsafe_allow_html=True)

# --- GESTION DES DONNÉES & SÉCURITÉ ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'projects' not in st.session_state:
    st.session_state.projects = []
if 'current_project_idx' not in st.session_state:
    st.session_state.current_project_idx = None

# --- ÉCRAN DE CONNEXION ---
if not st.session_state.authenticated:
    st.title("🔐 Lean Six Sigma - Personal Toolbox")
    st.write("Veuillez vous identifier pour accéder à vos projets sécurisés.")
    
    with st.container(border=True):
        user = st.text_input("Identifiant (Email Google)")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter via Google Drive"):
            if user and pwd: # Simulation de la validation Google
                st.session_state.authenticated = True
                st.success("Connexion réussie. Accès à votre Drive autorisé.")
                st.rerun()
    st.stop()

# --- BARRE LATÉRALE (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Paramètres")
    st.color_picker("Couleur de l'outil", st.session_state.primary_color, key="color_picker")
    st.session_state.primary_color = st.session_state.color_picker
    
    st.divider()
    if st.button("📁 Sauvegarder sur Google Drive"):
        st.toast("Projets synchronisés sur votre Drive !")
    
    st.download_button("📥 Exporter en Excel", data="Données simulées", file_name="Projet_LSS.xlsx")
    
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

# --- NAVIGATION PRINCIPALE ---
if st.session_state.current_project_idx is None:
    # PAGE D'ACCUEIL : GESTION DES PROJETS
    st.title("🚀 Mes Projets Lean Six Sigma")
    
    # Création de projet
    with st.expander("➕ Initialiser un nouveau projet Black Belt"):
        p_name = st.text_input("Nom du projet")
        if st.button("Créer le projet"):
            new_p = {
                "name": p_name,
                "status": "Define",
                "problem": "",
                "ctq": [],
                "team": pd.DataFrame(columns=["Poste", "Nom"]),
                "benefits": ""
            }
            st.session_state.projects.append(new_p)
            st.rerun()

    # Liste des projets
    cols = st.columns(3)
    for idx, p in enumerate(st.session_state.projects):
        with cols[idx % 3]:
            with st.container(border=True):
                st.subheader(p["name"])
                st.caption(f"Phase actuelle : {p['status']}")
                if st.button("Ouvrir", key=f"open_{idx}"):
                    st.session_state.current_project_idx = idx
                    st.rerun()

else:
    # VUE PROJET (DMAIC)
    p = st.session_state.projects[st.session_state.current_project_idx]
    
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
            p_input = st.text_area("Saisie libre", value=p["problem"], height=150, key=f"prob_in_{st.session_state.current_project_idx}")
            
            if st.button("🪄 Retranscrire via IA"):
                # On enregistre le texte et on génère les suggestions proprement
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
                        # On force un rafraîchissement propre
                        st.rerun()
            
            st.divider()
            
            # On affiche la zone de modification uniquement si un CTQ est sélectionné
            if "selected_ctq" in p and p["selected_ctq"]:
                st.write("✍️ **Ajustez votre CTQ final :**")
                
                # Correction : On utilise une clé unique 'edit_ctq'
                new_val = st.text_input(
                    "Libellé du CTQ", 
                    value=p["selected_ctq"], 
                    key=f"edit_ctq_{st.session_state.current_project_idx}"
                )
                
                # On ne met à jour que si la valeur change vraiment
                if new_val != p["selected_ctq"]:
                    p["selected_ctq"] = new_val
                    st.rerun()

                st.info(f"**CTQ validé :** {p['selected_ctq']}")
            
            
            # 3. Zone de modification manuelle
            if "selected_ctq" in p:
                st.write("✍️ **Ajustez votre CTQ final :**")
                # Cette case permet de modifier le texte suggéré ou d'en écrire un nouveau
                final_ctq = st.text_input(
                    "Libellé du CTQ", 
                    value=p["selected_ctq"],
                    help="Reformulez ici pour que ce soit précis et mesurable."
                )
                p["selected_ctq"] = final_ctq
                st.info(f"**CTQ enregistré :** {p['selected_ctq']}")

        # 2. Équipe
        st.divider()
        st.subheader("2. Équipe Projet")
        p["team"] = st.data_editor(p["team"], num_rows="dynamic", use_container_width=True)
        
        # 3. Bénéfices
        st.divider()
        st.subheader("3. Bénéfices attendus")
        st.text_area("Bénéfices (IA assistée)", key="ben_in")
        
        # 4. Outils Visuels
        st.divider()
        st.subheader("4. Cartographie & Planning")
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            st.info("📊 Diagramme de Gantt")
            # Simulation Gantt
            fig = go.Figure(data=[go.Bar(x=[10, 20, 30, 15, 10], y=['D', 'M', 'A', 'I', 'C'], orientation='h')])
            st.plotly_chart(fig, use_container_width=True)
        with sub_col2:
            st.info("🗺️ SIPOC Visuel")
            st.text_area("Entrez les étapes (S-I-P-O-C)", "Fournisseurs > Entrées > Processus > Sorties > Clients")

    # --- PHASE MEASURE (Aperçu) ---
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
