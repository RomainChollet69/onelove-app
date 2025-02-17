import streamlit as st
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import openai

# -------------------------------------------------------------------
# 1. CONFIGURATION DES SECRETS & API
# -------------------------------------------------------------------
# Vérifier que la clé API OpenAI est chargée
if "openai" in st.secrets and "api_key" in st.secrets["openai"]:
    st.success("✅ Clé API OpenAI chargée avec succès !")
else:
    st.error("❌ Erreur : Impossible de charger la clé API OpenAI.")

# Chargement de la clé API OpenAI
api_key = st.secrets["openai"]["api_key"]

# Fonction pour générer un feedback via OpenAI
ddef generate_feedback(user_id, total_score, orientation, gender, is_smoker, wants_kids, 
                      dealbreakers_smoking, dealbreakers_kids, q1, q2, q3, q4):
    prompt = f"""
Un utilisateur vient de compléter le test de compatibilité IA sur OneLove.
Voici son profil détaillé :

- **ID** : {user_id}
- **Score de compatibilité** : {total_score}/15
- **Orientation sexuelle** : {orientation}
- **Genre** : {gender}
- **Fumeur** : {"Oui" if is_smoker else "Non"}
- **Souhaite avoir des enfants** : {"Oui" if wants_kids else "Non"}
- **Critère rédhibitoire (refuse un(e) partenaire fumeur)** : {"Oui" if dealbreakers_smoking else "Non"}
- **Critère rédhibitoire (refuse un(e) partenaire ne voulant pas d'enfants)** : {"Oui" if dealbreakers_kids else "Non"}
- **Rythme de vie** : {q1}
- **Valeurs en couple** : {q2}
- **Journée idéale** : {q3}
- **Niveau d'engagement recherché** : {q4}/10

🔹 **Analyse et conseils** :
- Dresse un portrait de cet utilisateur en fonction de ses réponses.
- Souligne ses points forts en relation amoureuse.
- Donne-lui des conseils pour trouver un partenaire compatible.
- Termine par une phrase inspirante sur l’amour et les rencontres.
    """
    print("🔍 Prompt envoyé à OpenAI :")
    print(prompt)

    try:
        # Définir la clé API dans le module OpenAI
        openai.api_key = api_key

        # Utilisation de l'API Chat de OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Ou "gpt-3.5-turbo" selon tes besoins
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        return f"❌ Erreur avec OpenAI : {str(e)}"


# -------------------------------------------------------------------
# 2. CONFIGURATION GOOGLE SHEETS
# -------------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
client = gspread.authorize(creds)

# Remplacez par l'ID de votre Google Sheet
SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"
sheet = client.open_by_key(SHEET_KEY).sheet1

# -------------------------------------------------------------------
# 3. FONCTIONS UTILES
# -------------------------------------------------------------------
def append_to_sheet(data_list):
    """
    Envoie une ligne de données à la Google Sheet.
    L'ordre doit correspondre à l'en-tête : 
    user_id, orientation, gender, is_smoker, wants_kids, dealbreakers_smoking, dealbreakers_kids, q1, q2, q3, q4, total_score
    """
    sheet.append_row(data_list)

def get_all_data_as_df():
    records = sheet.get_all_values()
    if not records or len(records) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(records[1:], columns=records[0])
    return df

# -------------------------------------------------------------------
# 4. GESTION DE LA SESSION & NAVIGATION
# -------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "answers" not in st.session_state:
    st.session_state.answers = {}

def go_to_page(page_name):
    st.session_state.page = page_name

# -------------------------------------------------------------------
# 5. PAGES DE L'APPLICATION
# -------------------------------------------------------------------
def page_login():
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    st.write("Veuillez vous identifier pour continuer.")
    user_input = st.text_input("Entrez votre pseudo ou email :")
    if st.button("Commencer"):
        if user_input.strip() == "":
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("profile_info")

def page_profile_info():
    st.title("Profil – Informations personnelles")
    orientation = st.radio(
        "Quelle est ton orientation sexuelle ?",
        ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Pansexuel(le)", "Autre"]
    )
    st.session_state.answers["orientation"] = orientation
    if orientation == "Autre":
        st.session_state.answers["orientation_detail"] = st.text_input("Précise si besoin :")
    else:
        st.session_state.answers["orientation_detail"] = ""
    gender = st.radio("Quel est ton genre ?", ["Homme", "Femme", "Autre"])
    st.session_state.answers["gender"] = gender
    is_smoker = st.radio("Es-tu fumeur/fumeuse ?", ["Oui", "Non"])
    st.session_state.answers["is_smoker"] = (is_smoker == "Oui")
    wants_kids = st.radio("Souhaites-tu avoir des enfants ?", ["Oui", "Non"])
    st.session_state.answers["wants_kids"] = (wants_kids == "Oui")
    if st.button("Suivant"):
        go_to_page("dealbreakers")

def page_dealbreakers():
    st.title("Critères rédhibitoires")
    dealbreakers_smoking = st.checkbox("Je refuse absolument un(e) partenaire fumeur/fumeuse")
    st.session_state.answers["dealbreakers_smoking"] = dealbreakers_smoking
    dealbreakers_kids = st.checkbox("Je refuse un(e) partenaire qui ne veut pas d'enfant (ou inverse)")
    st.session_state.answers["dealbreakers_kids"] = dealbreakers_kids
    if st.button("Suivant"):
        go_to_page("questions_part1")

def page_questions_part1():
    st.title("Questionnaire – Personnalité / Style de vie")
    q1 = st.radio(
        "Comment décrirais-tu ton rythme de vie ?",
        ["Très actif(ve)", "Assez actif(ve)", "Plutôt calme", "Très tranquille"]
    )
    st.session_state.answers["q1"] = q1
    q2 = st.radio(
        "Dans une relation, qu'est-ce qui est le plus important ?",
        ["A) La communication", "B) La complicité", "C) L'aventure", "D) La stabilité"]
    )
    st.session_state.answers["q2"] = q2
    q3 = st.text_input("Décris brièvement une journée idéale :")
    st.session_state.answers["q3"] = q3
    q4 = st.slider(
        "À quel point cherches-tu une relation sérieuse ? (0 = pas du tout, 10 = très sérieux)",
        0, 10, 5
    )
    st.session_state.answers["q4"] = q4
    if st.button("Valider et calculer mon score"):
        # Scoring simplifié
        score_q1_map = {"Très actif(ve)": 8, "Assez actif(ve)": 6, "Plutôt calme": 4, "Très tranquille": 2}
        s_q1 = score_q1_map.get(q1, 0)
        score_q2_map = {"A) La communication": 10, "B) La complicité": 8, "C) L'aventure": 7, "D) La stabilité": 6}
        s_q2 = score_q2_map.get(q2, 0)
        keywords = {"voyage": 5, "plage": 5, "océan": 5, "aventure": 5, "tranquillité": 3, "famille": 3, "sport": 3, "culture": 3}
        s_q3 = sum(val for w, val in keywords.items() if w in q3.lower())
        s_q4 = q4
        total_score = s_q1 + s_q2 + s_q3 + s_q4
        st.session_state.answers["total_score"] = total_score
        # Enregistrement dans la Google Sheet (12 colonnes)
        append_to_sheet([
            st.session_state.user_id,
            st.session_state.answers["orientation"],
            st.session_state.answers["gender"],
            str(st.session_state.answers["is_smoker"]),
            str(st.session_state.answers["wants_kids"]),
            str(st.session_state.answers["dealbreakers_smoking"]),
            str(st.session_state.answers["dealbreakers_kids"]),
            q1,
            q2,
            q3,
            q4,
            total_score
        ])
        go_to_page("result")

def page_result():
    st.title("Résultats, Feedback et Matching")
    total_score = st.session_state.answers.get("total_score", 0)
    st.write(f"**Votre score : {total_score}**")
    
    st.write("⏳ Génération du feedback en cours...")
    feedback = generate_feedback(
        st.session_state.user_id,
        total_score,
        st.session_state.answers.get("orientation", "Non précisé"),
        st.session_state.answers.get("gender", "Non précisé"),
        st.session_state.answers.get("is_smoker", False),
        st.session_state.answers.get("wants_kids", False),
        st.session_state.answers.get("dealbreakers_smoking", False),
        st.session_state.answers.get("dealbreakers_kids", False),
        st.session_state.answers.get("q1", "Non précisé"),
        st.session_state.answers.get("q2", "Non précisé"),
        st.session_state.answers.get("q3", "Non précisé"),
        st.session_state.answers.get("q4", 5),
    )
    st.write("✅ Réponse OpenAI reçue :")
    st.write(feedback)
    
    # Récupérer les profils enregistrés depuis la Google Sheet
    df = get_all_data_as_df()
    if df.empty:
        st.write("Aucune donnée enregistrée pour le moment.")
        return
    # Conversion des colonnes booléennes
    for col in ["is_smoker", "wants_kids", "dealbreakers_smoking", "dealbreakers_kids"]:
        df[col] = df[col].apply(lambda x: str(x).lower() == "true")
    df["total_score"] = pd.to_numeric(df["total_score"], errors="coerce")
    
    # Mes critères personnels
    my_orientation = st.session_state.answers["orientation"]
    my_gender = st.session_state.answers["gender"]
    my_smoker = st.session_state.answers["is_smoker"]
    my_kids = st.session_state.answers["wants_kids"]
    my_ds_smoking = st.session_state.answers["dealbreakers_smoking"]
    my_ds_kids = st.session_state.answers["dealbreakers_kids"]
    
    # Fonction d'exclusion basée sur les dealbreakers
    def is_excluded(row):
        if my_ds_smoking and row["is_smoker"]:
            return True
        if row["dealbreakers_smoking"] and my_smoker:
            return True
        if my_ds_kids and (row["wants_kids"] == False):
            return True
        if row["dealbreakers_kids"] and (my_kids == False):
            return True
        return False
    
    df["excluded"] = df.apply(is_excluded, axis=1)
    # Filtre par score (±2 points) et exclusion
    min_score = total_score - 2
    max_score = total_score + 2
    compatible_profiles = df[
        (df["excluded"] == False) &
        (df["total_score"] >= min_score) &
        (df["total_score"] <= max_score)
    ].copy()
    # Exclure mon propre profil
    compatible_profiles = compatible_profiles[compatible_profiles["user_id"] != st.session_state.user_id]
    
    if not compatible_profiles.empty:
        st.subheader("Profils compatibles :")
        for idx, row in compatible_profiles.iterrows():
            st.write(f"- **ID** : {row['user_id']} | **Score** : {row['total_score']} "
                     f"| **Orientation** : {row['orientation']} | **Fumeur** : {row['is_smoker']} | **Enfants** : {row['wants_kids']}")
    else:
        st.write("Aucun profil proche de votre score n’a été trouvé pour le moment.")
    
    if st.button("Refaire le questionnaire"):
        st.session_state.answers = {}
        st.session_state.user_id = None
        go_to_page("login")

# -------------------------------------------------------------------
# 6. ROUTAGE PRINCIPAL
# -------------------------------------------------------------------
if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "profile_info":
    page_profile_info()
elif st.session_state.page == "dealbreakers":
    page_dealbreakers()
elif st.session_state.page == "questions_part1":
    page_questions_part1()
elif st.session_state.page == "result":
    page_result()
