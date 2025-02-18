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

# Remplacez par l'ID de votre Google Sheet (Assurez-vous que la première ligne contient : user_id, timestamp, data, score, feedback)
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
    Stocke dans Google Sheets les données du profil de l'utilisateur.
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
    On utilise ici un algorithme simple qui :
      - Ajoute 40 points si l'orientation est identique.
      - Ajoute 20 points si le genre est identique.
      - Ajoute jusqu'à 40 points selon la proximité de la valeur "engagement" (écart max = 9).
    Le score total est ensuite arrondi et sur 100.
    """
    score = 0
    if user_static.get("orientation") == other_static.get("orientation"):
        score += 40
    if user_static.get("gender") == other_static.get("gender"):
        score += 20
    try:
        engagement_user = float(user_static.get("engagement", 5))
        engagement_other = float(other_static.get("engagement", 5))
    except:
        engagement_user = 5
        engagement_other = 5
    diff = abs(engagement_user - engagement_other)
    engagement_score = (1 - diff / 9) * 40
    score += engagement_score
    return round(score)

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
    st.session_state.question_count = 0  # Limiter le chatbot à 3 questions
if "score" not in st.session_state:
    st.session_state.score = None
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "chat_input" not in st.session_state:
    st.session_state["chat_input"] = ""
# Pour stocker l'interaction choisie par l'utilisateur (résultat)
if "interaction_choice" not in st.session_state:
    st.session_state.interaction_choice = None

def go_to_page(page_name):
    st.session_state.page = page_name

# =============================================================================
# 5. PAGES DE L'APPLICATION
# =============================================================================

# ----- PAGE 1 : Login -----
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA (Version Test)")
    user_input = st.text_input("Entrez votre prénom (ou email) :")
    if st.button("Commencer"):
        if not user_input.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("basics")

# ----- PAGE 2 : Questions de base (version très courte) -----
def page_basics():
    st.title("Questions de base")
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
    st.title("Chatbot – Questions complémentaires")
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
    
    # Affichage de la conversation (sauf le message system)
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
    
    # Saisie de la réponse utilisateur (pas de formulaire pour éviter le double-clic)
    user_msg = st.text_input("Votre réponse :", key="chat_input")
    
    if st.button("Envoyer"):
        if st.session_state["chat_input"].strip():
            st.session_state.chat_history.append({
                "role": "user",
                "content": st.session_state["chat_input"].strip()
            })
            # Incrémenter le compteur si la dernière question posée par l'assistant contient un "?"
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
                st.stop()
                return
            # Sinon, obtenir la prochaine question via OpenAI
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
            st.session_state["chat_input"] = ""
            st.stop()
    
    if st.button("Terminer maintenant"):
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "FIN DE QUESTIONNAIRE"
        })
        st.stop()

# ----- PAGE 4 : Analyse et résultats -----
def page_result():
    st.title("Résultats du questionnaire")
    st.write("Analyse de vos réponses pour générer un profil et calculer votre compatibilité.")
    
    # Ajouter le choix de l'interaction (discuter, s'appeler, se rencontrer)
    interaction_choice = st.radio("Choisissez comment vous souhaitez interagir avec votre match :", 
                                  ["discuter", "s'appeler", "se rencontrer"])
    st.session_state.static_answers["interaction_choice"] = interaction_choice
    
    # Préparer un résumé des réponses
    static_info = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_info = "\n".join([f"{msg['role'].upper()} : {msg['content']}" 
                           for msg in st.session_state.chat_history if msg["role"] != "system"])
    full_text = f"Réponses statiques :\n{static_info}\n\nConversation :\n{chat_info}"
    
    analysis_prompt = (
        "Analyse les informations suivantes pour dresser un profil rapide de l'utilisateur et attribuer un pourcentage de compatibilité sur 100, ainsi qu'un court feedback. "
        "Réponds sous forme JSON : {\"score\": XX, \"feedback\": \"...\"}.\n\n" +
        full_text
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking. Donne un score de compatibilité et un feedback court."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = resp.choices[0].message["content"].strip()
            result_json = json.loads(analysis_text)
            st.session_state.score = result_json.get("score", 0)
            st.session_state.feedback = result_json.get("feedback", "")
        except Exception as e:
            st.error(f"Erreur lors de l'analyse : {e}")
            st.session_state.score = 0
            st.session_state.feedback = "Impossible de générer un feedback."
    
    st.subheader(f"Pourcentage de compatibilité : {st.session_state.score}%")
    st.write(f"**Feedback :** {st.session_state.feedback}")
    
    # Enregistrer le profil complet dans Google Sheets
    store_data_to_sheet(
        st.session_state.user_id,
        {"static_answers": st.session_state.static_answers, "chat_history": st.session_state.chat_history},
        st.session_state.score,
        st.session_state.feedback
    )
    
    if st.button("Voir mes matchs"):
        go_to_page("matching")

# ----- PAGE 5 : Matching (affichage du match sans profil complet) -----
def page_matching():
    st.title("Mes matchs")
    st.write("Voici votre match (juste un prénom et le pourcentage de compatibilité).")
    
    # Charger tous les profils enregistrés
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucun profil enregistré pour le moment.")
        return
    
    # Récupérer le profil de l'utilisateur courant
    try:
        current_data = json.loads(df[df["user_id"] == st.session_state.user_id]["data"].iloc[0])
        current_static = current_data.get("static_answers", {})
    except Exception:
        current_static = st.session_state.static_answers
    
    # On parcourt tous les autres profils et on calcule leur compatibilité
    matches = []
    for idx, row in df.iterrows():
        if row["user_id"] == st.session_state.user_id:
            continue  # Ne pas comparer avec soi-même
        try:
            other_data = json.loads(row["data"])
            other_static = other_data.get("static_answers", {})
        except Exception:
            continue
        comp = compute_compatibility(current_static, other_static)
        matches.append({
            "user_id": row["user_id"],
            "compatibility": comp,
            "interaction_choice": other_static.get("interaction_choice", "non défini")
        })
    
    if not matches:
        st.info("Aucun autre profil n'a encore répondu.")
        return
    
    # Pour le test, on ne présente qu'un seul match (celui avec le meilleur score)
    match = max(matches, key=lambda x: x["compatibility"])
    
    st.write(f"**Match trouvé : {match['user_id']}**")
    st.write(f"**Compatibilité : {match['compatibility']}%**")
    st.write(f"**Votre choix d'interaction :** {st.session_state.static_answers.get('interaction_choice', 'non défini')}")
    st.write(f"**Le choix de {match['user_id']} :** {match['interaction_choice']}")
    
    if st.session_state.static_answers.get("interaction_choice") == match["interaction_choice"]:
        st.success(f"Vous êtes appariés pour {match['interaction_choice']} !")
        st.write("Une interaction (chat, appel ou rencontre) va s'ouvrir.")
    else:
        st.info("Votre mode d'interaction n'est pas encore apparié avec votre match. Réessayez plus tard.")

# =============================================================================
# 6. ROUTAGE PRINCIPAL DE L'APPLICATION
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
