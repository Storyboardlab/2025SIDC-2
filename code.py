import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import json
import pandas as pd

# Google Sheets setup
@st.cache_resource(ttl=60)
def get_gspread_client():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_dict), scope)
    client = gspread.authorize(creds)
    return client

@st.cache_resource(ttl=60)
def get_worksheet(tab_name):
    SPREADSHEET_NAME = '1fN2MkfDK2F_mnYv-7S_YjEHaPlMBdGVL_X_EtNHSItg'
    client = get_gspread_client()
    sheet = client.open_by_key(SPREADSHEET_NAME)
    return sheet.worksheet(tab_name)

# Date and range mapping for 통역팀 tabs
interpreter_date_range_map = [
    ("7/10(목)", "F7:F27"),
    ("7/11(금)", "G10:G27"),
    ("7/12(토)", "H10:H27"),
    ("7/13(일)", "B34:B61"),
    ("7/14(화)", "C34:C61"),
    ("7/15(화)", "D34:D61"),
    ("7/16(수)", "E34:E61"),
    ("7/17(목)", "F34:F61"),
    ("7/18(금)", "G34:G61"),
    ("7/19(토)", "H34:H61"),
    ("7/20(일)", "B68:B84"),
    ("7/21(월)", "C68:C84"),
    ("7/22(화)", "D68:D84"),
]

def find_assignments_by_range(worksheet, name, date_range_map):
    data = worksheet.get_all_values()
    assignments = []
    for date_label, cell_range in date_range_map:
        # Parse the range, e.g., "E34:E61"
        match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range)
        if not match:
            continue
        col_start, row_start, col_end, row_end = match.groups()
        col_start_idx = ord(col_start) - ord('A')
        col_end_idx = ord(col_end) - ord('A')
        row_start_idx = int(row_start) - 1
        row_end_idx = int(row_end) - 1

        for col in range(col_start_idx, col_end_idx + 1):
            for row in range(row_start_idx, row_end_idx + 1):
                if row < len(data) and col < len(data[row]):
                    cell_value = data[row][col]
                    if cell_value and name in cell_value:
                        # Look upward in the same column for context
                        role, language = None, None
                        for lookup_row in range(row-1, max(row_start_idx-1, -1), -1):
                            above = data[lookup_row][col]
                            # Role/language
                            rl_match = re.match(r"\[(심사위원|참가자)\]\s*(영어|중국어|일본어)", above)
                            if rl_match and not (role and language):
                                role = rl_match.group(1)
                                language = rl_match.group(2)
                            if role and language:
                                break
                        # Judge: extract from the interpreter cell itself
                        judge = None
                        judge_match = re.match(r"\[([^\]]+)\]", cell_value)
                        if judge_match:
                            judge = judge_match.group(1)
                        # Optionally, fallback: look upward for judge if not found in cell
                        if not judge:
                            for lookup_row in range(row-1, max(row_start_idx-1, -1), -1):
                                above = data[lookup_row][col]
                                judge_match = re.match(r"\[([^\]]+)\]", above)
                                if judge_match:
                                    judge = judge_match.group(1)
                                    break
                        assignments.append({
                            "date": date_label,
                            "role": role,
                            "language": language,
                            "judge": judge
                        })
    # Deduplicate
    unique = []
    seen = set()
    for a in assignments:
        key = tuple(sorted(a.items()))
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique

st.title("2025 서울국제무용콩쿠르 서포터즈")
st.subheader("통역팀 배정 내역")

name = st.text_input("이름을 입력한 후 엔터를 눌러 주세요:")

if name:
    try:
        a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_assignments = find_assignments_by_range(a_ws_t, name, interpreter_date_range_map)
        b_assignments = find_assignments_by_range(b_ws_t, name, interpreter_date_range_map)

        special_dates = {"7/18(금)", "7/19(토)", "7/20(일)"}
        a_normal = [a for a in a_assignments if a["date"] not in special_dates]
        a_special = [a for a in a_assignments if a["date"] in special_dates]

        def display_assignments(assignments):
            if not assignments:
                st.write("없음")
                return
            for a in assignments:
                if a["role"] == "심사위원" and a.get("judge"):
                    line = f"{a['date']} - {a['language']} - 심사위원 통역: {a['judge']}"
                elif a["role"] == "참가자":
                    line = f"{a['date']} - {a['language']} - 참가자 통역"
                else:
                    line = f"{a['date']}"
                st.write(line)

        st.subheader("A조 출근일자")
        display_assignments(a_normal)

        st.subheader("B조 출근일자")
        display_assignments(b_assignments)

        st.subheader("7/18 ~ 7/20 출근일자")
        display_assignments(a_special)

    except Exception as e:
        st.error(f"스프레드시트 접근 중 오류 발생: {e}")
else:
    st.info("결과가 나오기 까지 15초 정도 걸릴 수 있습니다.")

# --- 빈자리 확인 기능 ---
def find_available_slots(worksheet, date_range_map):
    data = worksheet.get_all_values()
    available = []
    for date_label, cell_range in date_range_map:
        match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range)
        if not match:
            continue
        col_start, row_start, col_end, row_end = match.groups()
        col_start_idx = ord(col_start) - ord('A')
        col_end_idx = ord(col_end) - ord('A')
        row_start_idx = int(row_start) - 1
        row_end_idx = int(row_end) - 1

        for col in range(col_start_idx, col_end_idx + 1):
            row = row_start_idx
            while row <= row_end_idx:
                if row < len(data) and col < len(data[row]):
                    cell = data[row][col]
                    # Header: [역할] 언어 N
                    header_match = re.match(r"\[(심사위원|참가자)\]\s*(영어|중국어|일본어)\s*(\d+)", cell or "")
                    if header_match:
                        role, language, n_slots = header_match.groups()
                        n_slots = int(n_slots)
                        available_count = 0
                        slot_rows = []
                        for i in range(1, n_slots+1):
                            slot_row = row + i
                            if slot_row > row_end_idx or slot_row >= len(data):
                                continue
                            slot_cell = data[slot_row][col] if col < len(data[slot_row]) else ""
                            if role == "참가자":
                                # 참가자: blank = available
                                if not slot_cell.strip():
                                    available_count += 1
                            elif role == "심사위원":
                                # 심사위원: blank or only [이름] = available
                                if not slot_cell.strip():
                                    available_count += 1
                                else:
                                    judge_only = re.match(r"\[[^\]]+\]\s*$", slot_cell)
                                    if judge_only:
                                        available_count += 1
                        if available_count > 0:
                            available.append({
                                "date": date_label,
                                "language": language,
                                "role": role,
                                "available": available_count
                            })
                        row += n_slots  # skip slot rows
                row += 1
    return available

st.markdown("---")
st.subheader("빈자리 확인")
if st.button("빈자리 확인"):
    try:
        a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_available = find_available_slots(a_ws_t, interpreter_date_range_map)
        b_available = find_available_slots(b_ws_t, interpreter_date_range_map)
        st.write("#### A조 빈자리")
        if not a_available:
            st.write("없음")
        else:
            st.dataframe(pd.DataFrame(a_available))
        st.write("#### B조 빈자리")
        if not b_available:
            st.write("없음")
        else:
            st.dataframe(pd.DataFrame(b_available))
    except Exception as e:
        st.error(f"빈자리 확인 중 오류 발생: {e}")
