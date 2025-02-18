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
st.set_page_config(page_title="OneLove – Matchmaking IA", layout="centered")

if "openai" in st.secrets and "api_key" in st.secrets["openai"]:
    st.success("✅ Clé API OpenAI chargée avec succès !")
else:
    st.error("❌ Erreur : Impossible de charger la clé API OpenAI.")

if "GCP_SERVICE_ACCOUNT" not in st.secrets:
    st.error("❌ Erreur : Impossible de charger la configuration GCP.")

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
# La première ligne de la sheet doit contenir au moins : user_id, timestamp, data, score, feedback
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
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_str = json.dumps(data_dict, ensure_ascii=False)
        row = [user_id, timestamp, data_str, score, feedback]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Erreur lors de l'enregistrement des données : {e}")

def get_all_data_as_df():
    """
    Récupère toutes les données de la Google Sheet sous forme de DataFrame.
    """
    try:
        records = sheet.get_all_values()
        if not records or len(records) < 2:
            return pd.DataFrame()
        return pd.DataFrame(records[1:], columns=records[0])
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données : {e}")
        return pd.DataFrame()

def compute_compatibility(user_static, other_static):
    """
    Calcule un pourcentage de compatibilité entre deux utilisateurs
    à partir de critères pondérés.
    Critères (exemple de pondération) :
        - Orientation (1.5)
        - Genre (1.0)
        - Fumeur (2.0)
        - Enfants (2.5)
        - Rythme de vie (2.0)
        - Valeurs en couple (3.0)
        - Journée idéale (2.5)
        - Engagement (3.0)
    Le score total maximum est 17.5 points, qu'on ramène à un pourcentage sur 100.
    """
    total_weight = 17.5
    user_score = 0.0

    # 1) Orientation (1.5)
    if user_static.get("orientation") == other_static.get("orientation"):
        user_score += 1.5

    # 2) Genre (1.0)
    if user_static.get("gender") == other_static.get("gender"):
        user_score += 1.0

    # 3) Fumeur (2.0)
    if user_static.get("is_smoker") == other_static.get("is_smoker"):
        user_score += 2.0

    # 4) Enfants (2.5)
    if user_static.get("wants_children") == other_static.get("wants_children"):
        user_score += 2.5

    # 5) Rythme de vie (2.0)
    if user_static.get("lifestyle") == other_static.get("lifestyle"):
        user_score += 2.0

    # 6) Valeurs en couple (3.0)
    user_values = set(user_static.get("couple_values", []))
    other_values = set(other_static.get("couple_values", []))
    intersection_size = len(user_values.intersection(other_values))
    all_values = len(user_values.union(other_values))
    if all_values > 0:
        ratio = intersection_size / all_values
        user_score += 3.0 * ratio

    # 7) Journée idéale (2.5)
    # (Ici, on fait un matching très simple : identique = +2.5, sinon 0)
    # On pourrait faire une analyse sémantique via OpenAI, mais c'est plus avancé.
    if user_static.get("ideal_day") == other_static.get("ideal_day"):
        user_score += 2.5

    # 8) Niveau d’engagement (3.0)
    try:
        eng_user = float(user_static.get("engagement", 5))
        eng_other = float(other_static.get("engagement", 5))
    except:
        eng_user = 5
        eng_other = 5
    diff = abs(eng_user - eng_other)
    user_score += max(0, 3.0 * (1 - diff/9))

    # Score final en pourcentage
    return round((user_score / total_weight) * 100)

def go_to_page(page_name):
    st.session_state.page = page_name

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
    st.session_state.question_count = 0  # Pour limiter le chatbot à 3 questions
if "score" not in st.session_state:
    st.session_state.score = None
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "chat_input" not in st.session_state:
    st.session_state.chat_input = ""
if "interaction_choice" not in st.session_state:
    st.session_state.interaction_choice = None

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

# ----- PAGE 2 : Questions de base (version étendue) -----
def page_basics():
    st.title("Questions de base")

    orientation = st.radio("Quelle est ton orientation sexuelle ?",
                           ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Autre"])

    gender = st.radio("Quel est ton genre ?",
                      ["Homme", "Femme", "Autre"])

    engagement = st.slider("À quel point cherches-tu une relation sérieuse ? (1 à 10)",
                           1, 10, 5)

    is_smoker = st.radio("Fumes-tu ?", ["Oui", "Non"])
    wants_children = st.radio("Souhaites-tu avoir des enfants ?", ["Oui", "Non"])
    lifestyle = st.selectbox("Décris ton rythme de vie", ["Casanier", "Actif", "Fêtard", "Équilibré"])

    couple_values = st.multiselect(
        "Quelles sont tes valeurs en couple ?",
        ["Confiance", "Loyauté", "Indépendance", "Communication", "Humour", "Respect", "Spiritualité", "Liberté"]
    )

    ideal_day = st.text_input("Décris rapidement ta journée idéale")

    if st.button("Suivant"):
        st.session_state.static_answers.update({
            "orientation": orientation,
            "gender": gender,
            "engagement": engagement,
            "is_smoker": is_smoker,
            "wants_children": wants_children,
            "lifestyle": lifestyle,
            "couple_values": couple_values,
            "ideal_day": ideal_day
        })
        go_to_page("chatbot")

# ----- PAGE 3 : Chatbot (maximum 3 questions) -----
def page_chatbot():
    st.title("Chatbot – Questions complémentaires")
    # Initialiser la conversation si vide
    if not st.session_state.chat_history:
        # Ajout d’un message système qui rappelle le rôle du chatbot
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "Tu es un chatbot de matchmaking. "
                "Tu disposes des réponses de base suivantes: " 
                f"{st.session_state.static_answers}. "
                "Pose 3 questions complémentaires maximum, claires, "
                "axées sur la compatibilité amoureuse. "
                "Puis termine par 'FIN DE QUESTIONNAIRE'. "
                "Pas de questions hors-sujet, garde un ton bienveillant et concis."
            )
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Salut ! Peux-tu décrire en quelques mots ce que tu recherches en amour ?"
        })
    
    # Affichage de la conversation (en ignorant le message système)
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "system":
            continue
        elif msg["role"] == "assistant":
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
    
    # Saisie de la réponse utilisateur
    user_msg = st.text_input("Votre réponse :", key="chat_input")

    if st.button("Envoyer"):
        if st.session_state.chat_input.strip():
            st.session_state.chat_history.append({
                "role": "user",
                "content": st.session_state.chat_input.strip()
            })
            # Incrémenter le compteur de question si la dernière question de l'assistant contient un "?"
            last_assistant_msg = st.session_state.chat_history[-2]["content"] if len(st.session_state.chat_history) > 1 else ""
            if "?" in last_assistant_msg:
                st.session_state.question_count += 1

            # Si 3 questions ont été posées, forcer la fin du questionnaire
            if st.session_state.question_count >= 3:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "FIN DE QUESTIONNAIRE"
                })
                return
            
            # Sinon, obtenir la prochaine question via OpenAI
            with st.spinner("Le chatbot réfléchit..."):
                assistant_text = get_chatbot_response(st.session_state.chat_history)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": assistant_text
            })
            #st.session_state.chat_input = ""  # Réinitialiser le champ
            return

    if st.button("Terminer maintenant"):
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "FIN DE QUESTIONNAIRE"
        })
        return

# ----- PAGE 4 : Analyse et résultats -----
def page_result():
    st.title("Résultats du questionnaire")
    st.write("Analyse de vos réponses pour générer un profil et calculer votre compatibilité.")
    
    # Choix de l'interaction souhaitée
    interaction_choice = st.radio("Choisissez comment vous souhaitez interagir avec votre match :",
                                  ["discuter", "s'appeler", "se rencontrer"])
    st.session_state.static_answers["interaction_choice"] = interaction_choice
    
    # Préparer un résumé des réponses
    static_info = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_info = "\n".join([f"{msg['role'].upper()} : {msg['content']}" 
                           for msg in st.session_state.chat_history if msg["role"] != "system"])
    full_text = f"Réponses statiques :\n{static_info}\n\nConversation :\n{chat_info}"
    
    analysis_prompt = (
        "Analyse les informations suivantes pour dresser un profil rapide de l'utilisateur "
        "et attribuer un pourcentage de compatibilité sur 100, ainsi qu'un court feedback. "
        "Réponds sous forme JSON strict : {\"score\": XX, \"feedback\": \"...\"}.\n\n" +
        full_text
    )
    
    with st.spinner("Analyse en cours..."):
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en matchmaking. Donne un score et un feedback court sous forme JSON uniquement."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            analysis_text = resp.choices[0].message["content"].strip()
            # Tenter de parser le JSON
            try:
                result_json = json.loads(analysis_text)
                st.session_state.score = result_json.get("score", 0)
                st.session_state.feedback = result_json.get("feedback", "")
            except json.JSONDecodeError:
                # En cas de JSON invalide, on met des valeurs par défaut
                st.session_state.score = 0
                st.session_state.feedback = "Impossible de générer un feedback (JSON invalide)."
        except Exception as e:
            st.error(f"Erreur lors de l'analyse : {e}")
            st.session_state.score = 0
            st.session_state.feedback = "Impossible de générer un feedback."
    
    st.subheader(f"Pourcentage de compatibilité (IA) : {st.session_state.score}%")
    st.write(f"**Feedback (IA) :** {st.session_state.feedback}")
    
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
    
    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucun profil enregistré pour le moment.")
        return
    
    # Récupérer le profil de l'utilisateur courant
    try:
        current_data_row = df[df["user_id"] == st.session_state.user_id]
        if current_data_row.empty:
            st.info("Votre profil n'a pas encore été enregistré correctement.")
            return
        current_data = json.loads(current_data_row["data"].iloc[0])
        current_static = current_data.get("static_answers", {})
    except Exception:
        current_static = st.session_state.static_answers
    
    # Calculer la compatibilité avec les autres profils
    matches = []
    for idx, row in df.iterrows():
        if row["user_id"] == st.session_state.user_id:
            continue
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
    
    # Pour la phase test, on affiche le match avec la meilleure compatibilité
    match = max(matches, key=lambda x: x["compatibility"])
    
    st.write(f"**Match trouvé : {match['user_id']}**")
    st.write(f"**Compatibilité : {match['compatibility']}%**")
    st.write(f"**Votre choix d'interaction :** {st.session_state.static_answers.get('interaction_choice', 'non défini')}")
    st.write(f"**Le choix de {match['user_id']} :** {match['interaction_choice']}")
    
    if st.session_state.static_answers.get("interaction_choice") == match["interaction_choice"]:
        st.success(f"Vous êtes appariés pour {match['interaction_choice']} !")
        st.write("Une interaction (chat, appel ou rencontre) va s'ouvrir (simulation).")
    else:
        st.info("Votre mode d'interaction n'est pas encore apparié avec votre match. Réessayez plus tard.")

# =============================================================================
# 6. ROUTAGE PRINCIPAL DE L'APPLICATION
# =============================================================================
def main():
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

if __name__ == "__main__":
    main()
