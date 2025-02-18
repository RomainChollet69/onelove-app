import streamlit as st
import json
import pandas as pd
import datetime
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import openai

# =============================================================================
# 1. CONFIGURATION DES SECRETS & API
# =============================================================================
if "openai" in st.secrets and "api_key" in st.secrets["openai"]:
    st.success("✅ Clé API OpenAI chargée avec succès !")
else:
    st.error("❌ Erreur : Impossible de charger la clé API OpenAI.")

api_key = st.secrets["openai"]["api_key"]
openai.api_key = api_key

# =============================================================================
# 2. CONFIGURATION GOOGLE SHEETS
# =============================================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
client = gspread.authorize(creds)

# Assurez-vous que votre Google Sheet a pour en-têtes :
# user_id | timestamp | data | score | feedback
SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"
sheet = client.open_by_key(SHEET_KEY).sheet1

# =============================================================================
# 3. FONCTIONS UTILES
# =============================================================================

def get_chatbot_response(conversation):
    """
    Envoie l'historique de conversation à OpenAI pour obtenir la réponse du chatbot.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation,
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message["content"].strip()
    except openai.OpenAIError as e:
        st.error(f"Erreur avec OpenAI : {str(e)}")
        return "Désolé, une erreur est survenue."

def store_data_to_sheet(user_id, data_dict, score, feedback):
    """
    Enregistre dans Google Sheets le profil de l'utilisateur.
    Colonnes : user_id | timestamp | data (JSON) | score | feedback
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_str = json.dumps(data_dict, ensure_ascii=False)
    row = [user_id, timestamp, data_str, score, feedback]
    sheet.append_row(row)

def get_all_data_as_df():
    """
    Récupère toutes les données de la Google Sheet sous forme de DataFrame.
    """
    records = sheet.get_all_values()
    if not records or len(records) < 2:
        return pd.DataFrame()
    return pd.DataFrame(records[1:], columns=records[0])

def compute_compatibility(user_static, other_static):
    """
    Calcule un pourcentage de compatibilité entre deux utilisateurs à partir des réponses statiques.
    Pondérations :
      - Orientation sexuelle : 1.5
      - Genre : 1.0
      - Fumeur : 2.0
      - Souhaite des enfants : 2.5
      - Critères rédhibitoires (fumeur) : 2.0
      - Critères rédhibitoires (enfants) : 2.0
      - Rythme de vie : 2.0
      - Valeurs en couple : 3.0
      - Journée idéale : 2.5
      - Niveau d'engagement : 3.0
    Score maximum théorique = 19.5 points.
    Pourcentage = (score / 19.5) * 100
    """
    total = 0
    max_total = 19.5
    if user_static.get("orientation") == other_static.get("orientation"):
        total += 1.5
    if user_static.get("gender") == other_static.get("gender"):
        total += 1.0
    if user_static.get("fumeur") == other_static.get("fumeur"):
        total += 2.0
    if user_static.get("souhaite_enfants") == other_static.get("souhaite_enfants"):
        total += 2.5
    # Critères rédhibitoires pour fumer
    cf1 = user_static.get("critere_fumeur", False)
    cf2 = other_static.get("critere_fumeur", False)
    cond1 = (not cf1) or (other_static.get("fumeur") == "Non")
    cond2 = (not cf2) or (user_static.get("fumeur") == "Non")
    if cond1 and cond2:
        total += 2.0
    # Critères rédhibitoires pour enfants
    ce1 = user_static.get("critere_enfants", False)
    ce2 = other_static.get("critere_enfants", False)
    cond1 = (not ce1) or (other_static.get("souhaite_enfants") == "Oui")
    cond2 = (not ce2) or (user_static.get("souhaite_enfants") == "Oui")
    if cond1 and cond2:
        total += 2.0
    try:
        r1 = float(user_static.get("rythme", 5))
        r2 = float(other_static.get("rythme", 5))
        total += 2.0 * (1 - abs(r1 - r2) / 9)
    except:
        pass
    try:
        v1 = float(user_static.get("valeurs", 5))
        v2 = float(other_static.get("valeurs", 5))
        total += 3.0 * (1 - abs(v1 - v2) / 9)
    except:
        pass
    try:
        j1 = float(user_static.get("journee", 5))
        j2 = float(other_static.get("journee", 5))
        total += 2.5 * (1 - abs(j1 - j2) / 9)
    except:
        pass
    try:
        e1 = float(user_static.get("engagement", 5))
        e2 = float(other_static.get("engagement", 5))
        total += 3.0 * (1 - abs(e1 - e2) / 9)
    except:
        pass
    return round((total / max_total) * 100)

# =============================================================================
# 4. INITIALISATION DE LA SESSION
# =============================================================================
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "static_answers" not in st.session_state:
    st.session_state.static_answers = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0  # Limite pour le chatbot
if "score" not in st.session_state:
    st.session_state.score = None
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "chat_input" not in st.session_state:
    st.session_state["chat_input"] = ""
if "interaction_choice" not in st.session_state:
    st.session_state.interaction_choice = None

def go_to_page(page_name):
    st.session_state.page = page_name

# =============================================================================
# 5. PAGES DE L'APPLICATION
# =============================================================================

# ----- PAGE 1 : Login -----
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    user_input = st.text_input("Entrez votre prénom (ou email) :")
    if st.button("Commencer"):
        if not user_input.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("static")

# ----- PAGE 2 : Questionnaire Statique -----
def page_static():
    st.title("Questionnaire de compatibilité")
    st.write("Veuillez répondre aux questions suivantes :")
    
    st.session_state.static_answers["orientation"] = st.radio(
        "Quelle est votre orientation sexuelle ?",
        ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Pansexuel(le)", "Autre"],
        key="orientation"
    )
    st.session_state.static_answers["gender"] = st.radio(
        "Quel est votre genre ?",
        ["Homme", "Femme", "Autre"],
        key="gender"
    )
    st.session_state.static_answers["fumeur"] = st.radio(
        "Êtes-vous fumeur ?",
        ["Oui", "Non"],
        key="fumeur"
    )
    st.session_state.static_answers["souhaite_enfants"] = st.radio(
        "Souhaitez-vous avoir des enfants ?",
        ["Oui", "Non"],
        key="souhaite_enfants"
    )
    st.session_state.static_answers["critere_fumeur"] = st.checkbox(
        "Je refuse un partenaire fumeur",
        key="critere_fumeur"
    )
    st.session_state.static_answers["critere_enfants"] = st.checkbox(
        "Je refuse un partenaire qui ne souhaite pas avoir d'enfants",
        key="critere_enfants"
    )
    st.session_state.static_answers["rythme"] = st.slider(
        "Votre rythme de vie (1 = très calme, 10 = très actif)",
        1, 10, 5,
        key="rythme"
    )
    st.session_state.static_answers["valeurs"] = st.slider(
        "Importance des valeurs en couple (1 à 10)",
        1, 10, 5,
        key="valeurs"
    )
    st.session_state.static_answers["journee"] = st.slider(
        "Votre journée idéale (1 = tranquille, 10 = intense)",
        1, 10, 5,
        key="journee"
    )
    st.session_state.static_answers["engagement"] = st.slider(
        "Niveau d’engagement recherché (1 à 10)",
        1, 10, 5,
        key="engagement"
    )
    
    if st.button("Suivant"):
        go_to_page("chatbot")

# ----- PAGE 3 : Chatbot interactif (max 3 questions) -----
def page_chatbot():
    st.title("Questions complémentaires")
    # Initialiser la conversation si vide
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "system",
            "content": ("Tu es un chatbot de matchmaking. Pose jusqu'à 3 questions complémentaires maximum, "
                        "puis termine par 'FIN DE QUESTIONNAIRE'.")
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Salut ! Peux-tu décrire en quelques mots ce que tu recherches en amour ?"
        })
    
    # Affichage de la conversation (hors message système)
    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Si le chatbot a terminé, proposer d'accéder aux résultats
    if (st.session_state.chat_history[-1]["role"] == "assistant" and
        "FIN DE QUESTIONNAIRE" in st.session_state.chat_history[-1]["content"].upper()):
        st.success("Le questionnaire est terminé !")
        if st.button("Voir les résultats"):
            go_to_page("result")
        return
    
    # Utilisation d'un formulaire pour la saisie
    with st.form(key="chat_form"):
        user_answer = st.text_input("Votre réponse:")
        submitted = st.form_submit_button("Envoyer")
    
    if submitted and user_answer.strip():
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_answer.strip()
        })
        # Vérifier si la dernière question de l'assistant contenait un "?"
        if len(st.session_state.chat_history) >= 2:
            last_assistant_msg = st.session_state.chat_history[-2]["content"]
            if "?" in last_assistant_msg:
                st.session_state.question_count += 1
        # Si 3 questions sont posées, forcer la fin du questionnaire
        if st.session_state.question_count == 3:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "FIN DE QUESTIONNAIRE"
            })
            return
        else:
            with st.spinner("Le chatbot réfléchit..."):
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state.chat_history,
                    temperature=0.7,
                    max_tokens=300
                )
            assistant_text = response.choices[0].message["content"].strip()
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": assistant_text
            })
            return
    
    if st.button("Terminer maintenant"):
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "FIN DE QUESTIONNAIRE"
        })
        return

# ----- PAGE 4 : Résultats et choix d'interaction -----
def page_result():
    st.title("Résultats du questionnaire")
    st.write("Analyse de vos réponses pour générer votre profil.")
    st.session_state.static_answers["interaction_choice"] = st.radio(
        "Choisissez comment vous souhaitez interagir avec votre match :",
        ["discuter", "s'appeler", "se rencontrer"],
        key="interaction_choice"
    )
    
    static_info = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_info = "\n".join([f"{msg['role'].upper()} : {msg['content']}" 
                           for msg in st.session_state.chat_history if msg["role"] != "system"])
    full_text = 
