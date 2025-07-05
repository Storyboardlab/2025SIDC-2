import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import json

# Google Sheets setup
def get_worksheet(tab_name):
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_dict), scope)
    client = gspread.authorize(creds)
    SPREADSHEET_NAME = '1fN2MkfDK2F_mnYv-7S_YjEHaPlMBdGVL_X_EtNHSItg'
    sheet = client.open_by_key(SPREADSHEET_NAME)
    return sheet.worksheet(tab_name)

# Helper to parse interpreter assignments in complex tabs
def parse_interpreter_assignments(worksheet, name):
    """
    Parse the worksheet for interpreter assignments matching the given name.
    Returns a list of dicts: {date, role, language, judge (optional)}
    """
    data = worksheet.get_all_values()
    assignments = []
    current_date = None
    current_role = None
    current_language = None

    for row in data:
        for cell in row:
            # Detect date (e.g., "7/18(금)")
            date_match = re.match(r"\d{1,2}/\d{1,2}\([가-힣]\)", cell)
            if date_match:
                current_date = cell.strip()
                current_role = None
                current_language = None
                continue

            # Detect role/language (e.g., "[심사위원] 영어 3" or "[참가자] 중국어 2")
            role_lang_match = re.match(r"\[(심사위원|참가자)\]\s*(영어|중국어|일본어)", cell)
            if role_lang_match:
                current_role = role_lang_match.group(1)
                current_language = role_lang_match.group(2)
                continue

            # Detect interpreter assignment (e.g., "[월록] 임어진" or just "임어진")
            if name in cell:
                judge = None
                judge_match = re.match(r"\[([^\]]+)\]\s*(.+)", cell)
                if judge_match:
                    judge = judge_match.group(1)
                    interpreter_name = judge_match.group(2)
                else:
                    interpreter_name = cell.strip()

                # Only add if the interpreter name matches exactly (to avoid partial matches)
                if interpreter_name == name:
                    assignment = {
                        "date": current_date,
                        "role": current_role,
                        "language": current_language,
                    }
                    if current_role == "심사위원" and judge:
                        assignment["judge"] = judge
                    assignments.append(assignment)
    return assignments

st.title("2025 서울국제무용콩쿠르 서포터즈")
st.subheader("통역팀 배정 내역")

name = st.text_input("이름을 입력한 후 엔터를 눌러 주세요:")

if name:
    try:
        a_ws_t = get_worksheet("본선 시간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_assignments = parse_interpreter_assignments(a_ws_t, name)
        b_assignments = parse_interpreter_assignments(b_ws_t, name)

        special_dates = {"7/18(금)", "7/19(토)", "7/20(일)"}
        a_normal_t = [a for a in a_assignments if a["date"] not in special_dates]
        a_special_t = [a for a in a_assignments if a["date"] in special_dates]

        def display_assignments(assignments):
            if not assignments:
                st.write("없음")
                return
            for a in assignments:
                if a["role"] == "심사위원" and a.get("judge"):
                    line = f"{a['date']} - {a['language']} - 심사위원: {a['judge']}"
                else:
                    line = f"{a['date']} - {a['language']} - {a['role']}"
                st.write(line)

        st.subheader("A조 출근일자 (통역팀)")
        display_assignments(a_normal_t)

        st.subheader("B조 출근일자 (통역팀)")
        display_assignments(b_assignments)

        st.subheader("7/18 ~ 7/20 출근일자 (통역팀)")
        display_assignments(a_special_t)

    except Exception as e:
        st.error(f"스프레드시트 접근 중 오류 발생: {e}")
else:
    st.info("결과가 나오기 까지 15초 정도 걸릴 수 있습니다.")
