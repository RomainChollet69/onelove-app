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
    Stocke les réponses (data_dict), le score et le feedback dans Google Sheets, avec horodatage.
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
    st.session_state.question_count = 0  # Pour limiter à 3 questions
if "score" not in st.session_state:
    st.session_state.score = None
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "likes" not in st.session_state:
    st.session_state.likes = {}
if "chat_input" not in st.session_state:
    st.session_state["chat_input"] = ""  # Initialisation de la saisie

def go_to_page(page_name):
    st.session_state.page = page_name

# =============================================================================
# 5. PAGES DE L'APPLICATION
# =============================================================================

# ----- PAGE 1 : Login -----
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA (Version Courte)")
    user_input = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if not user_input.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("basics")

# ----- PAGE 2 : Questions de base (très courtes) -----
def page_basics():
    st.title("Questions de base (Version Courte)")
    
    orientation = st.radio("Quelle est ton orientation sexuelle ?",
                           ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Autre"])
    
    gender = st.radio("Quel est ton genre ?",
                      ["Homme", "Femme", "Autre"])
    
    engagement = st.slider("À quel point cherches-tu une relation sérieuse ? (1 à 10)",
                           1, 10, 5)
    
    if st.button("Suivant"):
        st.session_state.static_answers["orientation"] = orientation
        st.session_state.static_answers["gender"] = gender
        st.session_state.static_answers["engagement"] = engagement
        go_to_page("chatbot")

# ----- PAGE 3 : Chatbot (max 3 questions) -----
def page_chatbot():
    st.title("Chatbot – Questions complémentaires (max 3)")
    
    # Initialiser la conversation si vide
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "Tu es un chatbot de matchmaking. Pose jusqu'à 3 questions complémentaires maximum, "
                "puis termine par 'FIN DE QUESTIONNAIRE'."
            )
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Salut ! Peux-tu décrire en quelques mots ce que tu recherches en amour ?"
        })
    
    # Affichage de la conversation (on saute le message system)
    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Vérifier si le chatbot a terminé
    if (st.session_state.chat_history[-1]["role"] == "assistant" and
        "FIN DE QUESTIONNAIRE" in st.session_state.chat_history[-1]["content"].upper()):
        st.success("Le questionnaire est terminé !")
        if st.button("Voir les résultats"):
            go_to_page("result")
        return
    
    # Saisie de la réponse utilisateur
    user_msg = st.text_input("Votre réponse :", key="chat_input")
    
    if st.button("Envoyer"):
        if st.session_state["chat_input"].strip():
            # Ajouter la réponse de l'utilisateur
            st.session_state.chat_history.append({
                "role": "user",
                "content": st.session_state["chat_input"].strip()
            })
            
            # Incrémenter le compteur de questions si la dernière question de l'assistant contenait un "?"
            last_assistant_msg = st.session_state.chat_history[-2]["content"] if len(st.session_state.chat_history) > 1 else ""
            if "?" in last_assistant_msg:
                st.session_state.question_count += 1
            
            # Si 3 questions ont été posées, forcer la fin
            if st.session_state.question_count >= 3:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "FIN DE QUESTIONNAIRE"
                })
                st.session_state["chat_input"] = ""
                st.stop()  # Arrête pour recharger la page
                return
            
            # Appeler l'API pour obtenir la prochaine question
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
            
            # Vider le champ de saisie
            st.session_state["chat_input"] = ""
            st.stop()  # Forcer le rechargement de la page
    
    # Bouton pour forcer la fin du questionnaire
    if st.button("Terminer maintenant"):
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "FIN DE QUESTIONNAIRE"
        })
        st.stop()

# ----- PAGE 4 : Analyse et résultats -----
def page_result():
    st.title("Analyse du questionnaire – Résultats")
    st.write("Nous analysons vos réponses pour générer un feedback.")
    
    # Préparer un résumé des réponses
    static_info = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_info = "\n".join([
        f"{msg['role'].upper()} : {msg['content']}" 
        for msg in st.session_state.chat_history if msg["role"] != "system"
    ])
    full_text = f"Réponses statiques :\n{static_info}\n\nConversation :\n{chat_info}"
    
    analysis_prompt = (
        "Analyse les informations suivantes pour dresser un profil rapide de l'utilisateur et attribuer un score "
        "de compatibilité sur 100, plus un court feedback. Réponds sous forme JSON : {\"score\": XX, \"feedback\": \"...\"}.\n\n"
        f"{full_text}"
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking, donne un score et un feedback."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = resp.choices[0].message["content"].strip()
            # Parser le JSON retourné
            result_json = json.loads(analysis_text)
            st.session_state.score = result_json.get("score", 0)
            st.session_state.feedback = result_json.get("feedback", "")
        except Exception as e:
            st.error(f"Erreur lors de l'analyse : {e}")
            st.session_state.score = 0
            st.session_state.feedback = "Impossible de générer un feedback."
    
    st.subheader(f"Score : {st.session_state.score}/100")
    st.write(f"**Feedback :** {st.session_state.feedback}")
    
    # Enregistrer dans Google Sheets
    store_data_to_sheet(
        st.session_state.user_id,
        {
            "static_answers": st.session_state.static_answers,
            "chat_history": st.session_state.chat_history
        },
        st.session_state.score,
        st.session_state.feedback
    )
    
    if st.button("Voir les profils compatibles"):
        go_to_page("matching")

# ----- PAGE 5 : Matching -----
def page_matching():
    st.title("Matching – Profils Compatibles")
    
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucune donnée enregistrée.")
        return
    
    try:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    except Exception:
        st.error("Erreur de conversion des scores.")
        return
    
    user_score = st.session_state.score if st.session_state.score else 0
    filtered_df = df[
        (df["score"] >= user_score - 10) & 
        (df["score"] <= user_score + 10) &
        (df["user_id"] != st.session_state.user_id)
    ]
    
    if filtered_df.empty:
        st.info("Aucun profil compatible trouvé.")
    else:
        for idx, row in filtered_df.iterrows():
            with st.container():
                st.subheader(f"Profil : {row['user_id']}")
                st.write(f"Score : {row['score']}/100")
                st.write("Feedback :", row['feedback'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👍 Like - {row['user_id']}", key=f"like_{idx}"):
                        st.session_state.likes[row['user_id']] = "like"
                        st.success(f"Vous avez liké {row['user_id']}.")
                with col2:
                    if st.button(f"👎 Dislike - {row['user_id']}", key=f"dislike_{idx}"):
                        st.session_state.likes[row['user_id']] = "dislike"
                        st.warning(f"Vous n'aimez pas {row['user_id']}.")
                st.markdown("---")
    
    if st.button("Refaire le questionnaire"):
        # Réinitialisation de la session
        st.session_state.page = "login"
        st.session_state.user_id = None
        st.session_state.static_answers = {}
        st.session_state.chat_history = []
        st.session_state.question_count = 0
        st.session_state.score = None
        st.session_state.feedback = ""
        st.session_state.likes = {}
        st.session_state["chat_input"] = ""

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
