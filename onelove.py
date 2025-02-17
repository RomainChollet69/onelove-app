import streamlit as st
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread

# -------------------------------------------------------------------
# 1. CONFIGURATION DE L'ACCES GOOGLE SHEETS
# -------------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
client = gspread.authorize(creds)

SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"  # Ton ID de Google Sheet
sheet = client.open_by_key(SHEET_KEY).sheet1

# -------------------------------------------------------------------
# 2. FONCTIONS UTILES
# -------------------------------------------------------------------
def append_to_sheet(data_list):
    """
    data_list : liste des champs à ajouter dans la feuille 
    Ex: [user_id, orientation, gender, is_smoker, wants_kids, 
         dealbreakers_smoking, dealbreakers_kids, Q1, Q2, Q3, Q4, total_score]
    """
    sheet.append_row(data_list)

def get_all_data_as_df():
    """
    Récupère toutes les données de la Google Sheet et les renvoie
    sous forme de DataFrame pandas.
    """
    records = sheet.get_all_values()
    if not records or len(records) < 2:
        # Soit la feuille est vide ou n'a que l'en-tête
        return pd.DataFrame()
    df = pd.DataFrame(records[1:], columns=records[0])
    return df

# -------------------------------------------------------------------
# 3. GESTION DE LA SESSION (NAVIGATION)
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
# 4. PAGES DE L'APPLICATION
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
    """
    Page où on pose des questions sur l'orientation, le genre, 
    si on est fumeur/fumeuse, si on veut des enfants, etc.
    """
    st.title("Profil – Informations personnelles")
    
    orientation = st.radio(
        "Quelle est ton orientation sexuelle ?",
        ["Hétérosexuel(le)", "Homosexuel(le)", "Bisexuel(le)", "Pansexuel(le)", "Autre"]
    )
    st.session_state.answers["orientation"] = orientation

    if orientation == "Autre":
        orientation_detail = st.text_input("Précise si besoin :")
        st.session_state.answers["orientation_detail"] = orientation_detail
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
    """
    Page QCM / sliders / questions pour le scoring
    """
    st.title("Questionnaire – Personnalité / Style de vie")

    # Q1
    q1 = st.radio(
        "Comment décrirais-tu ton rythme de vie ?",
        ["Très actif(ve)", "Assez actif(ve)", "Plutôt calme", "Très tranquille"]
    )
    st.session_state.answers["q1"] = q1

    # Q2
    q2 = st.radio(
        "Dans une relation, qu'est-ce qui est le plus important ?",
        ["A) La communication", "B) La complicité", "C) L'aventure", "D) La stabilité"]
    )
    st.session_state.answers["q2"] = q2

    # Q3 question libre
    q3 = st.text_input("Décris brièvement une journée idéale :")
    st.session_state.answers["q3"] = q3

    # Q4 slider
    q4 = st.slider(
        "À quel point cherches-tu une relation sérieuse ? (0 = pas du tout, 10 = très sérieux)",
        0, 10, 5
    )
    st.session_state.answers["q4"] = q4

    if st.button("Valider et calculer mon score"):
        # On calcule un score "style de vie", "valeurs", etc. (exemple simplifié)
        # Q1 scoring
        score_q1_map = {
            "Très actif(ve)": 8,
            "Assez actif(ve)": 6,
            "Plutôt calme": 4,
            "Très tranquille": 2
        }
        s_q1 = score_q1_map.get(q1, 0)

        # Q2 scoring
        score_q2_map = {
            "A) La communication": 10,
            "B) La complicité": 8,
            "C) L'aventure": 7,
            "D) La stabilité": 6
        }
        s_q2 = score_q2_map.get(q2, 0)

        # Q3 mots-clés
        keywords = {
            "voyage": 5, "plage": 5, "océan": 5, "aventure": 5,
            "tranquillité": 3, "famille": 3, "sport": 3, "culture": 3
        }
        s_q3 = sum(val for w, val in keywords.items() if w in q3.lower())

        # Q4 = direct usage
        s_q4 = q4

        total_score = s_q1 + s_q2 + s_q3 + s_q4
        st.session_state.answers["total_score"] = total_score

        # Enregistrer dans la Google Sheet
        # Prévois l'entête: user_id | orientation | gender | is_smoker | wants_kids
        # dealbreakers_smoking | dealbreakers_kids | q1 | q2 | q3 | q4 | total_score
        append_to_sheet([
            st.session_state.user_id,
            st.session_state.answers["orientation"],
            st.session_state.answers["gender"],
            str(st.session_state.answers["is_smoker"]),        # str() car bool
            str(st.session_state.answers["wants_kids"]),       # str() car bool
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
    st.title("Résultats et Matching")

    total_score = st.session_state.answers.get("total_score", 0)
    st.write(f"**Votre score : {total_score}**")

    df = get_all_data_as_df()
    if df.empty:
        st.write("Aucune donnée enregistrée pour le moment.")
        return

    # Convertir en types corrects
    # Nom des colonnes: (selon ton entête existante)
    # user_id, orientation, gender, is_smoker, wants_kids,
    # dealbreakers_smoking, dealbreakers_kids, q1, q2, q3, q4, total_score
    for col in ["is_smoker", "wants_kids", "dealbreakers_smoking", "dealbreakers_kids"]:
        df[col] = df[col].apply(lambda x: str(x).lower() == "true")

    df["total_score"] = pd.to_numeric(df["total_score"], errors="coerce")

    # Récupérer MES réponses
    my_orientation = st.session_state.answers["orientation"]
    my_gender = st.session_state.answers["gender"]
    my_smoker = st.session_state.answers["is_smoker"]
    my_kids = st.session_state.answers["wants_kids"]
    my_ds_smoking = st.session_state.answers["dealbreakers_smoking"]
    my_ds_kids = st.session_state.answers["dealbreakers_kids"]

    # On définit une fonction d'exclusion
    def is_excluded(row):
        # 1) Si je refuse un fumeur et row est fumeur => exclude
        if my_ds_smoking and (row["is_smoker"] == True):
            return True
        # 2) L'autre sens : si row refuse un fumeur et je suis fumeur
        if row["dealbreakers_smoking"] and my_smoker:
            return True

        # 3) Enfants
        #   si je refuse un partenaire qui ne veut pas d'enfants et row ne veut pas => exclude
        if my_ds_kids and (row["wants_kids"] == False):
            return True
        # 4) L'autre sens : si row refuse un partenaire kids, je n'en veux pas...
        if row["dealbreakers_kids"] and (my_kids == False):
            return True

        # TODO: On peut aussi ajouter orientation => s'il y a un mismatch
        # ex: hétéro => match seulement si gender opposé. (Tu peux coder la logique.)
        return False

    df["excluded"] = df.apply(is_excluded, axis=1)

    # Filtre par score et exclusion
    min_score = total_score - 2
    max_score = total_score + 2

    compatible_profiles = df[
        (df["excluded"] == False) &
        (df["total_score"] >= min_score) &
        (df["total_score"] <= max_score)
    ].copy()

    # Enlève moi-même (on ne veut pas s'auto-match)
    compatible_profiles = compatible_profiles[compatible_profiles["user_id"] != st.session_state.user_id]

    if not compatible_profiles.empty:
        st.subheader("Profils compatibles :")
        for idx, row in compatible_profiles.iterrows():
            st.write(
                f"- **ID** : {row['user_id']} | **Score** : {row['total_score']} "
                f"| **Orientation** : {row['orientation']} "
                f"| **Fumeur** : {row['is_smoker']} | **Enfants** : {row['wants_kids']}"
            )
    else:
        st.write("Aucun profil proche de votre score n’a été trouvé pour le moment.")

    if st.button("Refaire le questionnaire"):
        st.session_state.answers = {}
        st.session_state.user_id = None
        go_to_page("login")

# -------------------------------------------------------------------
# 5. ROUTAGE PRINCIPAL
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
