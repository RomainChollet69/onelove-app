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

def store_conversation_to_sheet(user_id, data, score, feedback):
    """
    Stocke les réponses statiques et la conversation complète avec horodatage dans Google Sheets.
    Les colonnes enregistrées sont : user_id, timestamp, data (en JSON), score, feedback.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_str = json.dumps(data, ensure_ascii=False)
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
if "static_answers" not in st.session_state:
    st.session_state.static_answers = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
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
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    st.write("Veuillez vous identifier pour commencer le questionnaire interactif.")
    user_input = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if not user_input.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("basics")

# ----- PAGE 2 : Questions de base (QCM / Slider) -----
def page_basics():
    st.title("Questions de base")
    st.write("Veuillez répondre aux questions suivantes :")
    
    orientation = st.radio("Quelle est ton orientation sexuelle ?",
                           ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Pansexuel(le)", "Autre"])
    orientation_detail = ""
    if orientation == "Autre":
        orientation_detail = st.text_input("Précise ton orientation :")
    
    gender = st.radio("Quel est ton genre ?",
                      ["Homme", "Femme", "Autre"])
    
    smoker = st.radio("Es-tu fumeur ?",
                      ["Oui", "Non"])
    
    relation = st.radio("Quel type de relation cherches-tu ?",
                        ["Relation sérieuse", "Relation occasionnelle", "Amitié", "Autre"])
    
    engagement = st.slider("À quel point es-tu engagé dans ta recherche de relation ? (1 = pas du tout, 10 = très engagé)",
                           1, 10, 5)
    
    if st.button("Suivant"):
        st.session_state.static_answers["orientation"] = orientation
        st.session_state.static_answers["orientation_detail"] = orientation_detail
        st.session_state.static_answers["gender"] = gender
        st.session_state.static_answers["smoker"] = smoker
        st.session_state.static_answers["relation"] = relation
        st.session_state.static_answers["engagement"] = engagement
        go_to_page("valeurs")

# ----- PAGE 3 : Questions sur les valeurs -----
def page_valeurs():
    st.title("Valeurs et attentes")
    st.write("Note l'importance des éléments suivants dans une relation (1 = peu important, 10 = très important) :")
    
    fidelity = st.slider("Fidélité", 1, 10, 5)
    communication = st.slider("Communication", 1, 10, 5)
    trust = st.slider("Confiance", 1, 10, 5)
    humor = st.slider("Humour", 1, 10, 5)
    
    if st.button("Suivant"):
        st.session_state.static_answers["fidelity"] = fidelity
        st.session_state.static_answers["communication"] = communication
        st.session_state.static_answers["trust"] = trust
        st.session_state.static_answers["humor"] = humor
        go_to_page("psychologie")

# ----- PAGE 4 : Questions psychologiques -----
def page_psychologie():
    st.title("Questions psychologiques")
    st.write("Quelques questions pour mieux te connaître :")
    
    conflict_management = st.slider("Sur une échelle de 1 à 10, comment évalues-tu ta capacité à gérer les conflits ?", 1, 10, 5)
    openness = st.slider("Sur une échelle de 1 à 10, à quel point es-tu ouvert(e) aux changements ?", 1, 10, 5)
    emotion_expression = st.radio("Comment préfères-tu exprimer tes émotions ?",
                                  ["Verbalement", "Par des actions", "En écrivant", "Autre"])
    emotional_stability = st.radio("Comment te décrirais-tu en termes de stabilité émotionnelle ?",
                                   ["Très stable", "Stable", "Instable", "Très instable"])
    self_confidence = st.slider("Quel est ton niveau de confiance en toi ?", 1, 10, 5)
    
    if st.button("Suivant"):
        st.session_state.static_answers["conflict_management"] = conflict_management
        st.session_state.static_answers["openness"] = openness
        st.session_state.static_answers["emotion_expression"] = emotion_expression
        st.session_state.static_answers["emotional_stability"] = emotional_stability
        st.session_state.static_answers["self_confidence"] = self_confidence
        go_to_page("chatbot")

# ----- PAGE 5 : Chatbot interactif -----
def page_chatbot():
    st.title("Chatbot interactif – Questionnaire complémentaire")
    st.write("Ici, le chatbot va te poser des questions supplémentaires pour approfondir ton profil.")
    
    # Si la conversation est vide, initialiser avec un prompt système et un premier message
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "Tu es un chatbot expert en matchmaking et psychologie. À partir des réponses statiques déjà fournies, "
                "pose des questions complémentaires pour mieux cerner le profil de l'utilisateur. "
                "Continue la conversation jusqu'à ce que tu considères que le profil est complet et termine par 'FIN DE QUESTIONNAIRE'."
            )
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Merci pour tes réponses. Peux-tu me parler d'une expérience marquante en amour ou dans une relation ?"
        })
    
    # Affichage de la conversation
    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Si le chatbot a terminé le questionnaire, proposer d'aller aux résultats
    if st.session_state.chat_history[-1]["role"] == "assistant" and \
       "FIN DE QUESTIONNAIRE" in st.session_state.chat_history[-1]["content"].upper():
        st.success("Le questionnaire est terminé !")
        if st.button("Voir les résultats"):
            go_to_page("result")
        return
    
    with st.form(key="chat_input_form", clear_on_submit=True):
        user_message = st.text_input("Votre réponse :", "")
        submit = st.form_submit_button("Envoyer")
    
    if submit and user_message.strip():
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message.strip()
        })
        with st.spinner("Le chatbot réfléchit..."):
            assistant_response = get_chatbot_response(st.session_state.chat_history)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": assistant_response
        })

# ----- PAGE 6 : Analyse et résultats -----
def page_result():
    st.title("Analyse du questionnaire – Résultats et feedback")
    st.write("Nous analysons tes réponses pour générer un profil détaillé.")
    
    # Préparer une synthèse des réponses statiques
    static_str = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    # Préparer la conversation interactive
    chat_str = "\n\n".join([f"{msg['role'].upper()} : {msg['content']}" 
                             for msg in st.session_state.chat_history if msg["role"] != "system"])
    full_data = "Réponses statiques:\n" + static_str + "\n\nConversation interactive:\n" + chat_str
    
    analysis_prompt = (
        "Analyse les informations suivantes pour dresser un profil de l'utilisateur et attribuer un score de compatibilité sur 100, "
        "ainsi qu'un feedback personnalisé. Réponds sous forme de JSON, par exemple : {\"score\": 85, \"feedback\": \"...\"}.\n\n"
        f"{full_data}"
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking et psychologie. Analyse ce profil."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = response.choices[0].message["content"].strip()
            st.code(analysis_text, language="json")
            result_json = json.loads(analysis_text)
            st.session_state.score = result_json.get("score", None)
            st.session_state.feedback = result_json.get("feedback", "")
        except Exception as e:
            st.error(f"Erreur lors de l'analyse : {str(e)}")
            st.session_state.score = None
            st.session_state.feedback = "Impossible d'obtenir un feedback détaillé."
    
    if st.session_state.score is not None:
        st.subheader(f"Votre score de compatibilité : {st.session_state.score}/100")
    st.write("**Feedback personnalisé :**")
    st.write(st.session_state.feedback)
    
    # Stocker le profil dans Google Sheets
    store_conversation_to_sheet(
        st.session_state.user_id,
        {"static_answers": st.session_state.static_answers, "chat_history": st.session_state.chat_history},
        st.session_state.score if st.session_state.score is not None else "N/A",
        st.session_state.feedback
    )
    
    if st.button("Voir les profils compatibles"):
        go_to_page("matching")

# ----- PAGE 7 : Matching avancé -----
def page_matching():
    st.title("Profils compatibles – Matching avancé")
    st.write("Voici les profils dont le score est proche du tien. Indique si tu les aimes ou non.")
    
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucune donnée n'a encore été enregistrée.")
        return
    
    try:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    except Exception:
        st.error("Erreur lors de la conversion des scores.")
        return
    
    user_score = st.session_state.score if st.session_state.score is not None else 0
    filtered_df = df[(df["score"] >= user_score - 10) & (df["score"] <= user_score + 10)]
    filtered_df = filtered_df[filtered_df["user_id"] != st.session_state.user_id]
    
    if filtered_df.empty:
        st.info("Aucun profil compatible trouvé pour le moment.")
    else:
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
                        st.success(f"Tu as liké {row['user_id']}.")
                with col2:
                    if st.button(f"👎 Je n’aime pas - {row['user_id']}", key=f"dislike_{idx}"):
                        st.session_state.likes[row['user_id']] = "dislike"
                        st.warning(f"Tu n'as pas aimé {row['user_id']}.")
                st.markdown("---")
    
    if st.button("Refaire le questionnaire"):
        st.session_state.page = "login"
        st.session_state.user_id = None
        st.session_state.static_answers = {}
        st.session_state.chat_history = []
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
elif st.session_state.page == "valeurs":
    page_valeurs()
elif st.session_state.page == "psychologie":
    page_psychologie()
elif st.session_state.page == "chatbot":
    page_chatbot()
elif st.session_state.page == "result":
    page_result()
elif st.session_state.page == "matching":
    page_matching()
