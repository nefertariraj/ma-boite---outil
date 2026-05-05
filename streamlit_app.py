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

with tabs[0]:
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
        st.subheader("4. Stakeholder Analysis")
        stake_key = f"editor_stake_{st.session_state.current_project_idx}"
        edited_stake = st.data_editor(
            p.get("stakeholders", [{"Nom": "", "Impact": ""}]),
            num_rows="dynamic",
            use_container_width=True,
            key=stake_key
        )
        if st.button("✅ Valider les stakeholders", key=f"save_stake_{st.session_state.current_project_idx}"):
            p["stakeholders"] = edited_stake
            st.success("Stakeholders enregistrés !")
            st.rerun()

        # 5. SIPOC & Schéma de Processus
        st.divider()
        st.subheader("5. SIPOC")
        sipoc_key = f"editor_sipoc_{st.session_state.current_project_idx}"
        edited_sipoc = st.data_editor(
            p.get("sipoc_data", [{"S": "", "I": "", "P": "", "O": "", "C": ""}]),
            num_rows="dynamic",
            use_container_width=True,
            key=sipoc_key
        )
        if st.button("✅ Valider le SIPOC", key=f"save_sipoc_{st.session_state.current_project_idx}"):
            p["sipoc_data"] = edited_sipoc
            st.success("SIPOC enregistré !")
            st.rerun()

        with col_viz:
            st.write("🖼️ Schéma du Process")
            # Extraction des étapes pour le schéma
            steps = [row["Process"] for row in p["sipoc_data"] if row.get("Process") and row["Process"].strip() != ""]
            if steps:
                mermaid_code = "graph TD\n" + " --> ".join([f'"{s}"' for s in steps])
                st.components.v1.html(
                    f"""
                    <div class="mermaid" style="display: flex; justify-content: center;">
                    {mermaid_code}
                    </div>
                    <script type="module">
                    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
                    </script>
                    """,
                    height=400,
                )
            else:
                st.write("Ajoutez des étapes dans 'Process' pour voir le schéma.")

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
