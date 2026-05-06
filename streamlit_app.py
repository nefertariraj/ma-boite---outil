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
    st.title("⚙️ Paramètres")
    color = st.color_picker("Couleur de l'outil", st.session_state.primary_color)
    st.session_state.primary_color = color
    st.divider()
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.session_state.current_project_idx = None
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
        st.subheader("5. SIPOC & Cartographie par Responsable")
        
        sipoc_key = f"editor_sipoc_{st.session_state.current_project_idx}"
        
        if "sipoc_data" not in p:
            p["sipoc_data"] = [
                {"Supplier": "Acteur A", "Input": "", "Process": "Étape 1", "Output": "", "Customer": ""},
                {"Supplier": "Acteur B", "Input": "", "Process": "Étape 2", "Output": "", "Customer": ""}
            ]

        # 1. Zone du Tableau (Pleine largeur)
        st.info("💡 Le schéma ci-dessous s'organise selon la colonne 'Supplier' (Responsable).")
        edited_sipoc = st.data_editor(
            p["sipoc_data"],
            num_rows="dynamic",
            use_container_width=True,
            key=sipoc_key
        )
        
        # Bouton de validation
        if st.button("✅ Valider les données & Actualiser le schéma", key=f"btn_sipoc_{st.session_state.current_project_idx}"):
            p["sipoc_data"] = edited_sipoc
            st.success("Données enregistrées !")
            st.rerun()

        st.write("---") # Ligne de séparation visuelle

        # --- 2. Zone du Schéma (Pleine largeur avec Export & Zoom) ---
        st.write("---")
        st.write("🖼️ **Vue synoptique du flux par Responsable (Swimlanes)**")
        
        lanes = {}
        steps_order = []
        for i, row in enumerate(p["sipoc_data"]):
            resp = str(row.get("Supplier", "Inconnu")).strip() or "Inconnu"
            step = str(row.get("Process", "")).strip()
            if step:
                clean_step = "".join(e for e in step if e.isalnum() or e in " _-")
                clean_resp = "".join(e for e in resp if e.isalnum() or e in " _-")
                if clean_resp not in lanes: lanes[clean_resp] = []
                node_id = f"step_{i}"
                lanes[clean_resp].append(f'{node_id}["{clean_step}"]')
                steps_order.append(node_id)

        if steps_order:
            mermaid_code = "graph LR\n" 
            for resp, nodes in lanes.items():
                mermaid_code += f"  subgraph {resp}\n"
                for node in nodes: mermaid_code += f"    {node}\n"
                mermaid_code += "  end\n"
            if len(steps_order) > 1:
                mermaid_code += f"  " + " --> ".join(steps_order) + "\n"

            # Intégration de Mermaid avec fonctionnalités Export et Zoom
            st.components.v1.html(
                f"""
                <div id="mermaid-container" style="background-color: white; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <div id="viz" class="mermaid">
                        {mermaid_code}
                    </div>
                </div>
                
                <div style="margin-top: 10px; display: flex; gap: 10px;">
                    <button onclick="downloadJPG()" style="padding: 8px 16px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 5px;">📥 Télécharger en JPG</button>
                    <button onclick="openFullscreen()" style="padding: 8px 16px; cursor: pointer; background-color: #2196F3; color: white; border: none; border-radius: 5px;">🔍 Agrandir / Plein écran</button>
                </div>

                <canvas id="canvas" style="display:none;"></canvas>

                <script type="module">
                    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});

                    window.openFullscreen = function() {{
                        var elem = document.getElementById("mermaid-container");
                        if (elem.requestFullscreen) {{ elem.requestFullscreen(); }}
                    }};

                    window.downloadJPG = function() {{
                        const svg = document.querySelector('#mermaid-container svg');
                        const canvas = document.getElementById('canvas');
                        const ctx = canvas.getContext('2d');
                        const svgData = new XMLSerializer().serializeToString(svg);
                        const img = new Image();
                        const svgBlob = new Blob([svgData], {{type: 'image/svg+xml;charset=utf-8'}});
                        const url = URL.createObjectURL(svgBlob);

                        img.onload = function() {{
                            canvas.width = img.width * 2; // Qualité supérieure
                            canvas.height = img.height * 2;
                            ctx.fillStyle = "white";
                            ctx.fillRect(0, 0, canvas.width, canvas.height);
                            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                            const jpgUrl = canvas.toDataURL("image/jpeg", 0.9);
                            const link = document.createElement("a");
                            link.download = "SIPOC_Flux.jpg";
                            link.href = jpgUrl;
                            link.click();
                        }};
                        img.src = url;
                    }};
                </script>
                """,
                height=700,
            )
        else:
            st.info("Remplissez le tableau pour générer le flux.")
            
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
