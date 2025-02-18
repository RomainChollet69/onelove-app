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
    à partir de critères pondérés (exemple).
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
if "profile_summary" not in st.session_state:
    st.session_state.profile_summary = ""  # Le résumé "test psychologique"
if "interaction_choice" not in st.session_state:
    st.session_state.interaction_choice = None

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
    st.title("Chatbot – Questions complémentaires (3 max)")
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
                "Ne termine pas par 'FIN DE QUESTIONNAIRE' ; c'est le code qui gère la fin."
            )
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Salut ! Peux-tu décrire en quelques mots ce que tu recherches en amour ?"
        })
    
    # Affichage de la conversation (en ignorant le message system)
    for msg in st.session_state.chat_history:
        if msg["role"] == "system":
            continue
        elif msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")

    # Vérifier si on a déjà posé 3 questions
    if st.session_state.question_count >= 3:
        st.success("Vous avez déjà répondu à 3 questions. Le questionnaire est terminé.")
        if st.button("Voir le résumé de votre profil"):
            go_to_page("result")
        return

    # Saisie de la réponse utilisateur
    user_msg = st.text_input("Votre réponse :")
    if st.button("Envoyer"):
        if user_msg.strip():
            # Ajouter la réponse utilisateur
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_msg.strip()
            })
            # Incrémenter le compteur si la dernière intervention du chatbot contenait un "?"
            last_assistant_msg = st.session_state.chat_history[-2]["content"]
            if "?" in last_assistant_msg:
                st.session_state.question_count += 1
            
            # Si on vient d'atteindre 3 questions, on arrête (pas de nouvelle question)
            if st.session_state.question_count >= 3:
                st.success("Vous avez répondu à 3 questions. Le questionnaire est terminé.")
                return
            else:
                # Sinon, on demande la question suivante
                with st.spinner("Le chatbot réfléchit..."):
                    assistant_text = get_chatbot_response(st.session_state.chat_history)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": assistant_text
                })

    if st.button("Terminer maintenant"):
        st.session_state.question_count = 3
        st.success("Vous avez décidé de terminer. Le questionnaire est fini.")
        return

# ----- PAGE 4 : Résumé du profil (style test psychologique) -----
def page_result():
    st.title("Résumé de votre profil")
    st.write("Voici un résumé de votre profil, comme dans un test psychologique.")

    # Préparer un prompt qui demande à ChatGPT de résumer le profil
    # en vouvoyant l'utilisateur et en parlant de sa personnalité, etc.
    static_str = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_str = "\n".join([
        f"{msg['role'].upper()} : {msg['content']}"
        for msg in st.session_state.chat_history
        if msg["role"] != "system"
    ])
    prompt_summary = (
        "Voici les informations d'un utilisateur (ses réponses statiques et un bref échange chatbot). "
        "Rédige un résumé de son profil comme un test psychologique, en le vouvoyant (style 'vous êtes...'). "
        "Ne donne pas de score de compatibilité, mais décris sa personnalité, ses attentes, "
        "et ce qui pourrait le définir en amour.\n\n"
        f"---\nRéponses statiques:\n{static_str}\n---\n"
        f"Conversation:\n{chat_str}\n"
        "Réponds en quelques phrases, en français, sans JSON."
    )

    if "profile_summary" not in st.session_state or not st.session_state.profile_summary:
        # On génère le résumé via OpenAI
        with st.spinner("Génération du résumé..."):
            try:
                resp = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Tu es un expert en psychologie et en matchmaking."},
                        {"role": "user", "content": prompt_summary}
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                st.session_state.profile_summary = resp.choices[0].message["content"].strip()
            except Exception as e:
                st.error(f"Erreur lors de la génération du résumé : {e}")
                st.session_state.profile_summary = "Impossible de générer un résumé pour le moment."

    st.write(st.session_state.profile_summary)

    # Bouton pour aller voir si un match existe
    if st.button("Découvrez si nous avons quelqu’un de compatible avec vous"):
        go_to_page("matching")

# ----- PAGE 5 : Matching -----
def page_matching():
    st.title("Recherche de match")
    st.write("Nous allons vérifier s’il existe un match vous correspondant à 60 % ou plus.")

    # On enregistre les infos dans Google Sheets (score = 0, feedback = "")
    # (Si vous voulez enregistrer plus tôt, c'est possible, mais ici on fait un enregistrement final.)
    store_data_to_sheet(
        st.session_state.user_id,
        {"static_answers": st.session_state.static_answers,
         "chat_history": st.session_state.chat_history,
         "profile_summary": st.session_state.profile_summary},
        0,
        ""
    )

    df = get_all_data_as_df()
    if df.empty:
        st.info("Aucun profil n’est encore enregistré.")
        return
    
    # Récupérer le profil actuel
    try:
        current_data_row = df[df["user_id"] == st.session_state.user_id]
        if current_data_row.empty:
            st.info("Votre profil n'a pas été trouvé dans la base.")
            return
        current_data = json.loads(current_data_row["data"].iloc[0])
        current_static = current_data.get("static_answers", {})
    except Exception:
        current_static = st.session_state.static_answers
    
    # Calcul de compatibilité
    best_match = None
    best_score = 0

    for idx, row in df.iterrows():
        if row["user_id"] == st.session_state.user_id:
            continue
        try:
            other_data = json.loads(row["data"])
            other_static = other_data.get("static_answers", {})
        except Exception:
            continue
        
        comp = compute_compatibility(current_static, other_static)
        if comp > best_score:
            best_score = comp
            best_match = row["user_id"]
    
    if not best_match:
        st.info("Aucun autre profil n’a été trouvé.")
        return

    if best_score >= 60:
        st.success(f"Bravo ! Vous êtes compatible avec **{best_match}** à hauteur de **{best_score}%**.")
    else:
        st.info(f"Aucun profil n’a une compatibilité >= 60%. Le meilleur trouvé est {best_match} à {best_score}%.")

# =============================================================================
# 6. ROUTAGE PRINCIPAL
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
