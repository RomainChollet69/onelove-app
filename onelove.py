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
            max_tokens=200
        )
        return response.choices[0].message["content"].strip()
    except openai.OpenAIError as e:
        st.error(f"Erreur avec OpenAI : {str(e)}")
        return "Désolé, une erreur est survenue."

def store_conversation_to_sheet(user_id, conversation, score, feedback):
    """
    Stocke la conversation complète avec horodatage et les résultats dans Google Sheets.
    Les colonnes enregistrées sont : user_id, timestamp, conversation (en JSON), score, feedback.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conversation_str = json.dumps(conversation, ensure_ascii=False)
    data_row = [user_id, timestamp, conversation_str, score, feedback]
    sheet.append_row(data_row)

def get_all_data_as_df():
    """
    Récupère toutes les données de la Google Sheet sous forme de DataFrame.
    """
    records = sheet.get_all_values()
    if not records or len(records) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(records[1:], columns=records[0])
    return df

# =============================================================================
# 4. GESTION DE LA SESSION
# =============================================================================
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "chat_history" not in st.session_state:
    # Initialisation de l'historique avec un prompt système pour guider le chatbot
    st.session_state.chat_history = [{
        "role": "system",
        "content": (
            "Tu es un chatbot expert en matchmaking. Tu dois poser au moins 30 questions à l'utilisateur, "
            "en t'adaptant à ses réponses, et approfondir certains aspects si besoin. "
            "Quand tu as posé la 30ème question, conclus en écrivant : 'FIN DE QUESTIONNAIRE'."
        )
    }]
if "question_count" not in st.session_state:
    st.session_state.question_count = 0  # Compteur de questions posées
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

def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    st.write("Veuillez vous identifier pour commencer le questionnaire interactif.")
    user_input = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if user_input.strip() == "":
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("chatbot")

def page_chatbot():
    st.title("Chatbot interactif – Questionnaire de matchmaking")
    
    # Si on n'a qu'un seul message (le message système), on ajoute un message assistant initial
    if len(st.session_state.chat_history) == 1:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": (
                "Bonjour ! Je suis ravi de te rencontrer. Je vais te poser une série d'au moins 30 questions "
                "pour mieux cerner ton profil et tes attentes. N'hésite pas à détailler tes réponses. "
                "Pour commencer, peux-tu me dire rapidement qui tu es et ce que tu recherches ?"
            )
        })
    
    st.write("La conversation se déroule ci-dessous. Répondez aux questions et le chatbot s'adaptera à vos réponses.")
    
    # Affichage de l'historique de la conversation (on ignore le message système)
    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        elif msg["role"] == "user":
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Vérifier si le questionnaire est terminé (si le dernier message contient "FIN DE QUESTIONNAIRE")
    if (st.session_state.chat_history[-1]["role"] == "assistant" and 
        "FIN DE QUESTIONNAIRE" in st.session_state.chat_history[-1]["content"].upper()):
        st.success("Le questionnaire est terminé !")
        if st.button("Voir les résultats"):
            go_to_page("result")
        return
    
    # Zone de saisie pour la réponse utilisateur
    with st.form(key="chat_input_form", clear_on_submit=True):
        user_message = st.text_input("Votre réponse :", "")
        submit = st.form_submit_button("Envoyer")
    
    if submit and user_message.strip():
        # Ajout de la réponse de l'utilisateur à l'historique
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message.strip()
        })
        with st.spinner("Le chatbot réfléchit..."):
            assistant_response = get_chatbot_response(st.session_state.chat_history)
        # Ajout de la réponse du chatbot
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # Compter la question si on détecte un point d'interrogation
        if "?" in assistant_response:
            st.session_state.question_count += 1
        
        # On arrête l'exécution ici pour forcer Streamlit à recharger la page
        st.stop()

def page_result():
    st.title("Analyse du questionnaire – Résultats et feedback")
    st.write("Nous analysons vos réponses pour générer un profil détaillé.")
    
    # Préparation du prompt pour analyser la conversation complète
    conversation_str = "\n\n".join(
        [f"{msg['role'].upper()} : {msg['content']}" for msg in st.session_state.chat_history if msg["role"] != "system"]
    )
    
    analysis_prompt = (
        "Analyse la conversation suivante entre un utilisateur et un chatbot de matchmaking. "
        "Sur la base des réponses de l'utilisateur, attribue un score de compatibilité sur 100 et donne un feedback personnalisé. "
        "Réponds sous forme de JSON, par exemple : {\"score\": 85, \"feedback\": \"...\"}.\n\n"
        f"Conversation :\n{conversation_str}"
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking et tu analyses un questionnaire."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = response.choices[0].message["content"].strip()
            st.code(analysis_text, language="json")
            
            # Tentative de parsing du JSON retourné
            result_json = json.loads(analysis_text)
            st.session_state.score = result_json.get("score", None)
            st.session_state.feedback = result_json.get("feedback", "")
        except Exception as e:
            st.error(f"Erreur lors de l'analyse de la conversation : {str(e)}")
            st.session_state.score = None
            st.session_state.feedback = "Impossible d'obtenir un feedback détaillé."

    if st.session_state.score is not None:
        st.subheader(f"Votre score de compatibilité : {st.session_state.score}/100")
    st.write("**Feedback personnalisé :**")
    st.write(st.session_state.feedback)
    
    # Stockage de la conversation et des résultats dans Google Sheets
    store_conversation_to_sheet(
        st.session_state.user_id,
        st.session_state.chat_history,
        st.session_state.score if st.session_state.score is not None else "N/A",
        st.session_state.feedback
    )
    
    if st.button("Voir les profils compatibles"):
        go_to_page("matching")

def page_matching():
    st.title("Profils compatibles – Matching avancé")
    st.write("Les profils ci-dessous ont un score proche du vôtre. Vous pouvez indiquer si vous les aimez ou non.")
    
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucune donnée n'a encore été enregistrée.")
        return
    
    # Conversion du score en numérique (si possible)
    try:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    except Exception:
        st.error("Erreur de conversion des scores.")
        return
    
    # Filtrage : on garde uniquement les profils dont le score est proche (±10 points)
    user_score = st.session_state.score if st.session_state.score is not None else 0
    min_score = user_score - 10
    max_score = user_score + 10
    filtered_df = df[(df["score"] >= min_score) & (df["score"] <= max_score)]
    
    # Exclure le profil de l'utilisateur courant
    filtered_df = filtered_df[filtered_df["user_id"] != st.session_state.user_id]
    
    if filtered_df.empty:
        st.info("Aucun profil compatible trouvé pour le moment.")
    else:
        # Affichage des profils sous forme de cartes interactives
        for idx, row in filtered_df.iterrows():
            with st.container():
                st.markdown(f"### Profil : {row['user_id']}")
                st.write(f"**Score :** {row['score']}/100")
                st.write("**Feedback résumé :**")
                st.write(row['feedback'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👍 J’aime - {row['user_id']}", key=f"like_{idx}"):
                        st.session_state.likes[row['user_id']] = "like"
                        st.success(f"Vous avez liké {row['user_id']}.")
                with col2:
                    if st.button(f"👎 Je n’aime pas - {row['user_id']}", key=f"dislike_{idx}"):
                        st.session_state.likes[row['user_id']] = "dislike"
                        st.warning(f"Vous n'avez pas aimé {row['user_id']}.")
                st.markdown("---")
    
    if st.button("Refaire le questionnaire"):
        # Réinitialiser la session pour un nouveau questionnaire
        st.session_state.page = "login"
        st.session_state.user_id = None
        st.session_state.chat_history = [{
            "role": "system",
            "content": (
                "Tu es un chatbot expert en matchmaking. Tu dois poser au moins 30 questions à l'utilisateur, "
                "en t'adaptant à ses réponses, et approfondir certains aspects si besoin. "
                "Quand tu as posé la 30ème question, conclus en écrivant : 'FIN DE QUESTIONNAIRE'."
            )
        }]
        st.session_state.question_count = 0
        st.session_state.score = None
        st.session_state.feedback = ""
        st.session_state.likes = {}
        st.experimental_rerun()

# =============================================================================
# 6. ROUTAGE PRINCIPAL DE L'APPLICATION
# =============================================================================
if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "chatbot":
    page_chatbot()
elif st.session_state.page == "result":
    page_result()
elif st.session_state.page == "matching":
    page_matching()
