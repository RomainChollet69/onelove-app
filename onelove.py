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

# La première ligne de la Google Sheet doit contenir : user_id | timestamp | data | score | feedback
SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"
sheet = client.open_by_key(SHEET_KEY).sheet1

# =============================================================================
# 3. FONCTIONS UTILES
# =============================================================================
def get_chatbot_response(conversation):
    """Envoie l'historique de conversation à OpenAI pour obtenir la réponse du chatbot."""
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
    """Enregistre dans Google Sheets le profil de l'utilisateur."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_str = json.dumps(data_dict, ensure_ascii=False)
        row = [user_id, timestamp, data_str, score, feedback]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Erreur lors de l'enregistrement des données : {e}")

def get_all_data_as_df():
    """Récupère toutes les données de la Google Sheet sous forme de DataFrame."""
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
    Calcule un pourcentage de compatibilité entre deux utilisateurs à partir de critères pondérés.
    Pondérations (total max = 17.5 points) :
      - Orientation : 1.5
      - Genre : 1.0
      - Fumeur : 2.0
      - Enfants : 2.5
      - Rythme de vie : 2.0
      - Valeurs en couple : 3.0
      - Journée idéale : 2.5
      - Engagement : 3.0
    """
    total_weight = 17.5
    user_score = 0.0
    if user_static.get("orientation") == other_static.get("orientation"):
        user_score += 1.5
    if user_static.get("gender") == other_static.get("gender"):
        user_score += 1.0
    if user_static.get("is_smoker") == other_static.get("is_smoker"):
        user_score += 2.0
    if user_static.get("wants_children") == other_static.get("wants_children"):
        user_score += 2.5
    if user_static.get("lifestyle") == other_static.get("lifestyle"):
        user_score += 2.0
    user_values = set(user_static.get("couple_values", []))
    other_values = set(other_static.get("couple_values", []))
    if user_values or other_values:
        ratio = len(user_values.intersection(other_values)) / len(user_values.union(other_values))
        user_score += 3.0 * ratio
    if user_static.get("ideal_day") == other_static.get("ideal_day"):
        user_score += 2.5
    try:
        eng_user = float(user_static.get("engagement", 5))
        eng_other = float(other_static.get("engagement", 5))
    except:
        eng_user = 5
        eng_other = 5
    diff = abs(eng_user - eng_other)
    user_score += 3.0 * (1 - diff/9)
    return round((user_score / total_weight) * 100)

def go_to_page(page_name):
    st.session_state.page = page_name
    st.rerun()  # Force Streamlit à recharger immédiatement après le changement de page


# =============================================================================
# 4. INITIALISATION DE LA SESSION
# =============================================================================
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "personal_info" not in st.session_state:
    st.session_state.personal_info = {}
if "static_answers" not in st.session_state:
    st.session_state.static_answers = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0  # Pour limiter le chatbot à 3 questions
if "profile_summary" not in st.session_state:
    st.session_state.profile_summary = ""
if "interaction_choice" not in st.session_state:
    st.session_state.interaction_choice = None

# =============================================================================
# 5. PAGES DE L'APPLICATION
# =============================================================================

# PAGE 1 : Login
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    pseudo = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if not pseudo.strip():
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = pseudo.strip()
            go_to_page("personal")

# PAGE 2 : Informations personnelles
def page_personal():
    st.title("Informations personnelles")
    gender = st.radio("Quel est votre genre ?", ["Homme", "Femme", "Autre"])
    age = st.number_input("Quel est votre âge ?", min_value=18, max_value=120, value=25)
    location = st.text_input("Quel est votre emplacement (ville ou région) ?", value="Paris")
    if st.button("Suivant"):
        st.session_state.personal_info.update({
            "gender": gender,
            "age": age,
            "location": location
        })
        # Intégrer ces infos dans static_answers pour la suite
        st.session_state.static_answers.update({
            "gender": gender,
            "age": age,
            "location": location
        })
        go_to_page("psych")

# PAGE 3 : Questionnaire psychologique
def page_psych():
    st.title("Questionnaire psychologique")
    # Utilisez un formulaire pour regrouper toutes les questions.
    with st.form(key="psych_form", clear_on_submit=False):
        orientation = st.radio(
            "Quelle est votre orientation sexuelle ?",
            ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Pansexuel(le)", "Autre"]
        )
        engagement = st.slider(
            "À quel point cherchez-vous une relation sérieuse ? (1 à 10)",
            1, 10, 5
        )
        is_smoker = st.radio("Fumez-vous ?", ["Oui", "Non"])
        wants_children = st.radio("Souhaitez-vous avoir des enfants ?", ["Oui", "Non"])
        lifestyle = st.selectbox(
            "Comment décririez-vous votre rythme de vie ?",
            ["Casanier", "Actif", "Fêtard", "Équilibré"]
        )
        couple_values = st.multiselect(
            "Quelles sont vos valeurs en couple ?",
            ["Confiance", "Loyauté", "Indépendance", "Communication", "Humour", "Respect", "Spiritualité", "Liberté"]
        )
        ideal_day = st.text_input("Décrivez brièvement votre journée idéale")
        
        # Le formulaire ne se soumettra que lorsque l'utilisateur cliquera sur "Suivant"
        submitted = st.form_submit_button("Suivant")
    
    if submitted:
        st.session_state.static_answers.update({
            "orientation": orientation,
            "engagement": engagement,
            "is_smoker": is_smoker,
            "wants_children": wants_children,
            "lifestyle": lifestyle,
            "couple_values": couple_values,
            "ideal_day": ideal_day
        })
        go_to_page("chatbot")


# PAGE 4 : Chatbot interactif (3 questions maximum)
def page_chatbot():
    st.title("Questions complémentaires – Chatbot")
    # Initialiser la conversation si vide
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "Tu es un chatbot de matchmaking. Tu connais déjà les informations personnelles et psychologiques de l'utilisateur : "
                f"{st.session_state.static_answers}. Pose 3 questions complémentaires maximum sur sa personnalité et ses attentes, "
                "sans insérer de terminaison automatique."
            )
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Bonjour ! Peux-tu décrire en quelques mots ce que vous recherchez en amour ?"
        })
    
    # Affichage de la conversation (hors message système)
    for msg in st.session_state.chat_history:
        if msg["role"] == "system":
            continue
        elif msg["role"] == "assistant":
            st.markdown(f"**Chatbot :** {msg['content']}")
        else:
            st.markdown(f"**Vous :** {msg['content']}")
    
    # Si déjà 3 réponses ont été enregistrées, terminer le questionnaire
    if st.session_state.question_count >= 3:
        st.success("Vous avez répondu à 3 questions complémentaires. Le questionnaire est terminé.")
        if st.button("Voir le résumé de votre profil"):
            go_to_page("result")
        return
    
    # Saisie de la réponse utilisateur
    user_msg = st.text_input("Votre réponse :")
    if st.button("Envoyer"):
        if user_msg.strip():
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_msg.strip()
            })
            # Incrémenter le compteur si la dernière question du chatbot contenait un "?"
            if len(st.session_state.chat_history) >= 2:
                last_assistant_msg = st.session_state.chat_history[-2]["content"]
                if "?" in last_assistant_msg:
                    st.session_state.question_count += 1
            if st.session_state.question_count < 3:
                with st.spinner("Le chatbot réfléchit..."):
                    assistant_text = get_chatbot_response(st.session_state.chat_history)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": assistant_text
                })
            else:
                st.success("Vous avez répondu à 3 questions complémentaires. Le questionnaire est terminé.")
        return
    
    if st.button("Terminer maintenant"):
        st.session_state.question_count = 3
        st.success("Vous avez décidé de terminer le questionnaire.")
        return

# PAGE 5 : Résumé du profil (style test psychologique)
def page_result():
    st.title("Votre profil amoureux")
    st.write("Notre Love Psy vous a analysé et voici le profil qu'il dresse de vous !")
    
    # Préparation des données à envoyer pour la génération du résumé
    static_str = "\n".join([f"{k}: {v}" for k, v in st.session_state.static_answers.items()])
    chat_str = "\n".join([
        f"{msg['role'].upper()} : {msg['content']}"
        for msg in st.session_state.chat_history if msg["role"] != "system"
    ])
    
    # Le prompt demande expressément de s'adresser à l'utilisateur avec "vous".
    prompt_summary = (
        "Voici les informations d'un utilisateur (ses réponses personnelles et psychologiques, ainsi qu'un échange avec un chatbot). "
        "Veuillez rédiger un résumé de son profil amoureux en vous adressant directement à l'utilisateur avec le pronom 'vous'. "
        "Utilisez un ton bienveillant et professionnel, sans formules introductives génériques. "
        "Commencez directement par décrire le profil. \n\n"
        f"--- Informations :\n{static_str}\n---\nConversation :\n{chat_str}\n"
    )
    
    with st.spinner("Génération du résumé..."):
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Vous êtes un expert en psychologie et en matchmaking."},
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
    
    if st.button("Découvrez si nous avons quelqu’un de compatible avec vous"):
        go_to_page("matching")



# PAGE 6 : Matching
def partner_allowed(user_static, other_static):
    """
    Détermine si le profil 'other_static' est admissible en fonction de l'orientation sexuelle et du genre de l'utilisateur.
    - Pour un(e) hétérosexuel(le): le partenaire doit être de genre opposé.
    - Pour un(e) homosexuel(le): le partenaire doit être du même genre.
    - Pour bisexuel(le), pansexuel(le) ou Autre: tous les genres sont acceptés.
    """
    orientation = user_static.get("orientation", "").lower()
    user_gender = user_static.get("gender", "").lower()
    partner_gender = other_static.get("gender", "").lower()
    
    if orientation == "hétérosexuel(le)":
        return user_gender != partner_gender
    elif orientation == "homosexuel(le)":
        return user_gender == partner_gender
    elif orientation in ["bisexuel(le)", "pansexuel(le)"]:
        return True
    else:
        return True

def page_matching():
    st.title("Recherche de match")
    st.write("Nous vérifions si nous avons un profil compatible à au moins 60% avec vous.")
    
    # Enregistrement final du profil dans Google Sheets (score et feedback non utilisés ici)
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
    
    try:
        current_data_row = df[df["user_id"] == st.session_state.user_id]
        if current_data_row.empty:
            st.info("Votre profil n'a pas été trouvé dans la base.")
            return
        current_data = json.loads(current_data_row["data"].iloc[0])
        current_static = current_data.get("static_answers", {})
    except Exception:
        current_static = st.session_state.static_answers
    
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
        # Filtrer par orientation/gender
        if not partner_allowed(current_static, other_static):
            continue
        comp = compute_compatibility(current_static, other_static)
        if comp > best_score:
            best_score = comp
            best_match = row["user_id"]
    
    if not best_match:
        st.info("Aucun autre profil n’a été trouvé.")
        return

    if best_score >= 60:
        # Affichage du message de match sans mode de communication
        st.header(f"Bravo, tu as matché avec {best_match} à hauteur de {best_score}% !")
        st.write("Maintenant à toi de choisir comment tu souhaites rentrer en contact avec ton match :")
        user_mode = st.radio(
            "",
            ["discuter par chat", "par téléphone", "se rencontrer directement"]
        )
        st.session_state.static_answers["interaction_choice"] = user_mode
        if user_mode:
            st.success(f"Votre mode de communication sélectionné est : {user_mode}.")
    else:
        st.info(f"Aucun profil n’a une compatibilité >= 60%. Le meilleur match est {best_match} à {best_score}%.")

# =============================================================================
# 7. ROUTAGE PRINCIPAL DE L'APPLICATION
# =============================================================================
def main():
    if st.session_state.page == "login":
        page_login()
    elif st.session_state.page == "personal":
        page_personal()
    elif st.session_state.page == "psych":
        page_psych()
    elif st.session_state.page == "chatbot":
        page_chatbot()
    elif st.session_state.page == "result":
        page_result()
    elif st.session_state.page == "matching":
        page_matching()

if __name__ == "__main__":
    main()
