import streamlit as st
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# DEBUG: Inspecter le contenu de st.secrets
st.write("DEBUG - st.secrets keys:", list(st.secrets.keys()))

service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
st.write("DEBUG - Lecture JSON effectuée avec succès.")
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    service_account_info,
    SCOPES
)
client = gspread.authorize(creds)


# Feuille Google Sheets
SHEET_KEY = "1kJ9EfPW_LlChPp5eeuy4t-csLDrmjRyI-mIMUnmixfw"
sheet = client.open_by_key(SHEET_KEY).sheet1

st.title("Mon appli IA Dating")
# 

# -------------------------------------------------------------------
# 2. FONCTIONS UTILES
# -------------------------------------------------------------------

def append_to_sheet(data_list):
    """
    data_list : liste des champs à ajouter dans la feuille (dans l'ordre des colonnes)
    exemple: [user_id, Q1, Q2, Q3, Q4, total_score]
    """
    sheet.append_row(data_list)

def get_all_data_as_df():
    """
    Récupère toutes les données de la Google Sheet et les renvoie
    sous forme de DataFrame pandas.
    """
    records = sheet.get_all_values()
    # Si la feuille est vide ou juste l'en-tête, vérifie la structure
    if not records:
        return pd.DataFrame()

    # records[0] devrait contenir la ligne d'entêtes
    # records[1:] = toutes les lignes de données
    df = pd.DataFrame(records[1:], columns=records[0])
    return df

# -------------------------------------------------------------------
# 3. GESTION DE LA SESSION
# -------------------------------------------------------------------
# On utilise st.session_state pour stocker l'état de la navigation (quelle page),
# ainsi que l'id utilisateur et ses réponses.

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
    """
    Page de login / identification
    L'utilisateur saisit son pseudo ou email
    """
    st.title("Bienvenue sur OneLove – Matchmaking IA")
    st.write("Veuillez vous identifier pour continuer.")

    user_input = st.text_input("Entrez votre pseudo ou email :")

    if st.button("Commencer"):
        if user_input.strip() == "":
            st.warning("Merci de renseigner un identifiant.")
        else:
            st.session_state.user_id = user_input.strip()
            go_to_page("questions_part1")

def page_questions_part1():
    """
    Page 1 du questionnaire : QCM
    """
    st.title("Questionnaire (1/2)")
    st.write("Partie 1 : Questions QCM")

    # Q1
    question1 = st.radio(
        "Dans une relation, qu'est-ce qui est le plus important pour toi ?",
        [
            "A) La confiance",
            "B) L’aventure et la spontanéité",
            "C) La communication",
            "D) L’intimité et la complicité"
        ]
    )
    st.session_state.answers["question1"] = question1

    # Q2
    question2 = st.radio(
        "Quel est ton niveau de sociabilité ?",
        ["Très sociable", "Assez sociable", "Introverti(e)", "Plutôt solitaire"]
    )
    st.session_state.answers["question2"] = question2

    if st.button("Suivant"):
        go_to_page("questions_part2")

def page_questions_part2():
    """
    Page 2 du questionnaire : réponses libres, sliders, etc.
    """
    st.title("Questionnaire (2/2)")
    st.write("Partie 2 : Questions ouvertes et échelle d'importance")

    # Q3 - question libre
    question3 = st.text_input("Décris ta journée idéale en quelques mots :")
    st.session_state.answers["question3"] = question3

    # Q4 - slider
    question4 = st.slider(
        "A quel point cherches-tu une relation sérieuse ? (0 = pas du tout, 10 = très)",
        0, 10, 5
    )
    st.session_state.answers["question4"] = question4

    if st.button("Valider et calculer mon score"):
        # On calcule un score basique basé sur les réponses
        
        # Scoring Q1
        scores_q1 = {
            "A) La confiance": 10,
            "B) L’aventure et la spontanéité": 8,
            "C) La communication": 7,
            "D) L’intimité et la complicité": 6
        }
        score_q1 = scores_q1.get(st.session_state.answers["question1"], 0)

        # Scoring Q2
        scores_q2 = {
            "Très sociable": 8,
            "Assez sociable": 6,
            "Introverti(e)": 4,
            "Plutôt solitaire": 2
        }
        score_q2 = scores_q2.get(st.session_state.answers["question2"], 0)

        # Scoring Q3 (mots-clés simples)
        keywords = {
            "voyage": 5, "plage": 5, "océan": 5, "aventure": 5,
            "tranquillité": 3, "famille": 3, "sport": 3, "culture": 3
        }
        text = st.session_state.answers["question3"].lower()
        score_text = sum(value for word, value in keywords.items() if word in text)

        # Q4 = on utilise la valeur directement comme points
        score_q4 = question4

        total_score = score_q1 + score_q2 + score_text + score_q4
        st.session_state.answers["total_score"] = total_score

        # Enregistrement dans la Google Sheet
        # On suppose que ta feuille a un header : user_id, Q1, Q2, Q3, Q4, Score
        append_to_sheet([
            st.session_state.user_id,
            st.session_state.answers["question1"],
            st.session_state.answers["question2"],
            st.session_state.answers["question3"],
            st.session_state.answers["question4"],
            total_score
        ])

        go_to_page("result")

def page_result():
    """
    Page finale : affiche le score et propose des profils compatibles.
    """
    st.title("Résultats et Matching")

    total_score = st.session_state.answers.get("total_score", 0)
    st.write(f"**Votre score : {total_score}**")

    df = get_all_data_as_df()

    if "Score" in df.columns:
        # Convertir la colonne Score en nombre
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

        # Filtre de compatibilité : +/- 2 autour du score de l'utilisateur
        min_score = total_score - 2
        max_score = total_score + 2

        compatible_profiles = df[
            (df["Score"] >= min_score) & (df["Score"] <= max_score)
        ]

        st.subheader("Profils compatibles :")
        if not compatible_profiles.empty:
            for idx, row in compatible_profiles.iterrows():
                st.write(
                    f"- **ID** : {row['user_id']} "
                    f"| **Score** : {row['Score']} "
                    f"| **Journée idéale** : {row.get('Q3', '')}"
                )
        else:
            st.write("Aucun profil proche de votre score n’a été trouvé pour le moment.")
    else:
        st.write("Pas de données dans la feuille ou pas de colonne Score détectée.")

    if st.button("Refaire le questionnaire"):
        # Réinitialiser la session et revenir à la page de login
        st.session_state.answers = {}
        st.session_state.user_id = None
        go_to_page("login")

# -------------------------------------------------------------------
# 5. ROUTAGE PRINCIPAL
# -------------------------------------------------------------------
if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "questions_part1":
    page_questions_part1()
elif st.session_state.page == "questions_part2":
    page_questions_part2()
elif st.session_state.page == "result":
    page_result()
