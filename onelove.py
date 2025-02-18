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

# Configuration de l'API OpenAI
api_key = st.secrets["openai"]["api_key"]
openai.api_key = api_key

# =============================================================================
# 2. CONFIGURATION GOOGLE SHEETS
# =============================================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
client = gspread.authorize(creds)

# Remplacez par l'ID de votre Google Sheet
SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"
sheet = client.open_by_key(SHEET_KEY).sheet1

# =============================================================================
# 3. FONCTIONS UTILES
# =============================================================================

def get_chatbot_response(conversation):
    """
    Envoie l'historique de conversation à l'API OpenAI pour obtenir la réponse du chatbot.
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
    Stocke les données (réponses QCM + conversation) dans Google Sheets, avec horodatage.
    Colonnes : user_id, timestamp, data (JSON), score, feedback.
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

# =============================================================================
# 4. INITIALISATION DE LA SESSION
# =============================================================================
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "basic_answers" not in st.session_state:
    st.session_state.basic_answers = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0
if "score" not in st.session_state:
    st.session_state.score = None
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "likes" not in st.session_state:
    st.session_state.likes = {}

def go_to_page(page_name):
    st.session_state.page = page_name

# =============================================================================
# 5. PAGES DE L'APPLICATION
# =============================================================================

# ----- PAGE 1 : Login -----
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA (Version Test)")
    st.write("Veuillez vous identifier pour commencer.")
    user_input = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if not user_input.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("basics")

# ----- PAGE 2 : Questions de base (QCM) -----
def page_basics():
    st.title("Questions de base (Version Courte)")
    st.write("Veuillez répondre aux questions suivantes :")
    
    orientation = st.radio("Quelle est ton orientation sexuelle ?",
                           ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Autre"])
    gender = st.radio("Quel est ton genre ?",
                      ["Homme", "Femme", "Autre"])
    smoker = st.radio("Es-tu fumeur/fumeuse ?",
                      ["Oui", "Non"])
    
    if st.button("Suivant"):
        st.session_state.basic_answers["orientation"] = orientation
        st.session_state.basic_answers["gender"] = gender
        st.session_state.basic_answers["smoker"] = smoker
        go_to_page("chatbot")

# ----- PAGE 3 : Chatbot (3 questions max) -----
def page_chatbot():
    st.title("Chatbot – Questions complémentaires (max 3)")
    st.write("Le chatbot va te poser jusqu'à 3 questions supplémentaires.")
    
    # Initialisation du chatbot si vide
    if not st.session_state.chat_history:
        # Message système
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "Tu es un chatbot de matchmaking. Pose au maximum 3 questions à l'utilisateur "
                "pour approfondir son profil, puis termine en écrivant : 'FIN DE QUESTIONNAIRE'."
            )
        })
        # Premier message assistant
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Bonjour ! Dis-moi ce que tu recherches le plus chez un partenaire ?"
        })
    
    # Afficher la conversation (sauf le message système)
    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Vérifier si la dernière réponse contient FIN DE QUESTIONNAIRE
    if (st.session_state.chat_history[-1]["role"] == "assistant" and
        "FIN DE QUESTIONNAIRE" in st.session_state.chat_history[-1]["content"].upper()):
        st.success("Le questionnaire est terminé !")
        if st.button("Voir les résultats"):
            go_to_page("result")
        return
    
    # Formulaire pour la réponse utilisateur
    with st.form(key="chat_input_form", clear_on_submit=True):
        user_message = st.text_input("Votre réponse :")
        submit = st.form_submit_button("Envoyer")
    
    if submit and user_message.strip():
        # Ajouter la réponse utilisateur
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message.strip()
        })
        # Appeler OpenAI
        with st.spinner("Le chatbot réfléchit..."):
            assistant_response = get_chatbot_response(st.session_state.chat_history)
        
        # Ajouter la réponse du chatbot
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # Vérifier s'il y a un point d'interrogation => question
        if "?" in assistant_response:
            st.session_state.question_count += 1
        
        # Si on a atteint 3 questions, on force la fin
        if st.session_state.question_count >= 3:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "FIN DE QUESTIONNAIRE"
            })

# ----- PAGE 4 : Résultats -----
def page_result():
    st.title("Analyse du questionnaire – Résultats")
    st.write("Nous analysons tes réponses pour générer un feedback.")
    
    # Préparation des données
    basics_str = "\n".join([f"{k}: {v}" for k, v in st.session_state.basic_answers.items()])
    conversation_str = "\n".join(
        [f"{msg['role'].upper()} : {msg['content']}" for msg in st.session_state.chat_history if msg["role"] != "system"]
    )
    
    prompt_analysis = (
        "Analyse les informations suivantes (QCM + conversation) pour dresser un profil rapide de l'utilisateur, "
        "attribue un score de compatibilité sur 100 et donne un feedback. Réponds en JSON du type : "
        "{\"score\": 75, \"feedback\": \"...\"}\n\n"
        "Réponses QCM:\n" + basics_str + "\n\n"
        "Conversation:\n" + conversation_str
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking. Analyse ce profil rapidement."},
                    {"role": "user", "content": prompt_analysis}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = response.choices[0].message["content"].strip()
            st.code(analysis_text, language="json")
            # Tenter de parser le JSON
            result_json = json.loads(analysis_text)
            st.session_state.score = result_json.get("score", 0)
            st.session_state.feedback = result_json.get("feedback", "")
        except Exception as e:
            st.error(f"Erreur lors de l'analyse : {str(e)}")
            st.session_state.score = 0
            st.session_state.feedback = "Impossible d'obtenir un feedback."
    
    # Afficher le score et le feedback
    st.subheader(f"Score : {st.session_state.score}/100")
    st.write("**Feedback** :", st.session_state.feedback)
    
    # Enregistrer dans Google Sheets
    data_to_store = {
        "basic_answers": st.session_state.basic_answers,
        "chat_history": st.session_state.chat_history
    }
    store_data_to_sheet(
        st.session_state.user_id,
        data_to_store,
        st.session_state.score,
        st.session_state.feedback
    )
    
    if st.button("Voir les profils compatibles"):
        go_to_page("matching")

# ----- PAGE 5 : Matching -----
def page_matching():
    st.title("Profils compatibles")
    st.write("Voici les profils dont le score est proche du tien (±10).")
    
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucune donnée n'a encore été enregistrée.")
        return
    
    try:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    except:
        st.error("Erreur de conversion des scores.")
        return
    
    user_score = st.session_state.score if st.session_state.score else 0
    min_score = user_score - 10
    max_score = user_score + 10
    
    # Exclure le profil courant
    filtered_df = df[(df["score"] >= min_score) & (df["score"] <= max_score)]
    filtered_df = filtered_df[filtered_df["user_id"] != st.session_state.user_id]
    
    if filtered_df.empty:
        st.info("Aucun profil compatible trouvé.")
    else:
        for idx, row in filtered_df.iterrows():
            with st.container():
                st.markdown(f"### Profil : {row['user_id']}")
                st.write(f"**Score :** {row['score']}/100")
                st.write("**Feedback résumé :**", row['feedback'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👍 J’aime - {row['user_id']}", key=f"like_{idx}"):
                        st.session_state.likes[row['user_id']] = "like"
                        st.success(f"Tu as liké {row['user_id']}.")
                with col2:
                    if st.button(f"👎 Je n’aime pas - {row['user_id']}", key=f"dislike_{idx}"):
                        st.session_state.likes[row['user_id']] = "dislike"
                        st.warning(f"Tu n'as pas aimé {row['user_id']}.")
                st.markdown("---")
    
    if st.button("Refaire le questionnaire"):
        st.session_state.page = "login"
        st.session_state.user_id = None
        st.session_state.basic_answers = {}
        st.session_state.chat_history = []
        st.session_state.question_count = 0
        st.session_state.score = None
        st.session_state.feedback = ""
        st.session_state.likes = {}

# =============================================================================
# 6. ROUTAGE PRINCIPAL
# =============================================================================
if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "basics":
    page_basics()
elif st.session_state.page == "chatbot":
    page_chatbot()
elif st.session_state.page == "result":
    page_result()
elif st.session_state.page == "matching":
    page_matching()
