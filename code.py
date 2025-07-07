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
    # Map each date to its week block and column index (0-based)
    week_blocks = [
        # (start_row, [date, col_idx])
        (6, [  # 7/10~7/12 block starts at row 6 (0-based)
            ("7/10(목)", 4),
            ("7/11(금)", 5),
            ("7/12(토)", 6),
        ]),
        (32, [  # 7/13~7/19 block starts at row 32
            ("7/13(일)", 1),
            ("7/14(화)", 2),
            ("7/15(화)", 3),
            ("7/16(수)", 4),
            ("7/17(목)", 5),
            ("7/18(금)", 6),
            ("7/19(토)", 7),
        ]),
        (68, [  # 7/20~7/22 block starts at row 68
            ("7/20(일)", 2),
            ("7/21(월)", 3),
            ("7/22(화)", 4),
        ]),
    ]
    # For each week block, define the row offsets for each role/language
    offsets_map = {
        # 7/10~7/12
        6: {
            "심사위원": {"영어": [10], "중국어": [12, 13], "일본어": [15]},
            "참가자": {"영어": [17, 18], "중국어": [20, 21], "일본어": [23]},
        },
        # 7/13~7/19
        32: {
            "심사위원": {"영어": [10,11,12,13,14], "중국어": [16,17,18,19,20,21], "일본어": [23,24,25]},
            "참가자": {"영어": [27,28], "중국어": [30,31], "일본어": [33]},
        },
        # 7/20~7/22
        68: {
            "심사위원": {"영어": [8,9,10], "중국어": [12], "일본어": [14]},
            "참가자": {"영어": [16,17], "중국어": [19,20]},
        },
    }
    assignments = []
    for block_start, date_cols in week_blocks:
        for date_label, col_idx in date_cols:
            offsets = offsets_map[block_start]
            for role in offsets:
                for language in offsets[role]:
                    available_count = 0
                    for row_offset in offsets[role][language]:
                        row = block_start + row_offset
                        if row < len(data) and col_idx < len(data[row]):
                            cell = data[row][col_idx]
                            if role == "참가자":
                                if not cell or cell.strip() == "":
                                    available_count += 1
                            elif role == "심사위원":
                                if not cell or cell.strip() == "":
                                    available_count += 1
                                else:
                                    judge_only = re.match(r"\[[^\]]+\]\s*$", cell)
                                    if judge_only:
                                        available_count += 1
                    assignments.append({
                        "date": date_label,
                        "role": role,
                        "language": language,
                        "available": available_count
                    })
    return assignments

st.markdown("---")
st.subheader("빈자리 확인")

# Language selection using st.radio (always one line, left-aligned)
lang_labels = ["영어", "중국어", "일본어"]
if "selected_language" not in st.session_state:
    st.session_state.selected_language = lang_labels[0]

selected = st.radio(
    "언어 선택",
    lang_labels,
    index=lang_labels.index(st.session_state.selected_language),
    horizontal=True,
    key="selected_language_radio"
)
st.session_state.selected_language = selected

language_selected = st.session_state.selected_language

if language_selected:
    try:
        a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_available = [slot for slot in find_available_slots(a_ws_t, interpreter_date_range_map) if slot["language"] == language_selected]
        b_available = [slot for slot in find_available_slots(b_ws_t, interpreter_date_range_map) if slot["language"] == language_selected]
        special_dates = {"7/18(금)", "7/19(토)", "7/20(일)"}
        all_dates = [d for d, _ in interpreter_date_range_map]
        # Main table: exclude special dates
        table = {}
        for date in all_dates:
            if date in special_dates:
                continue
            table[date] = {"A조-심사위원": 0, "A조-참가자": 0, "B조-심사위원": 0, "B조-참가자": 0}
        for slot in a_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                continue
            if role == "심사위원":
                table[date]["A조-심사위원"] += count
            elif role == "참가자":
                table[date]["A조-참가자"] += count
        for slot in b_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                continue
            if role == "심사위원":
                table[date]["B조-심사위원"] += count
            elif role == "참가자":
                table[date]["B조-참가자"] += count
        rows = []
        for date in all_dates:
            if date in special_dates:
                continue
            row = {"날짜": date}
            row.update(table[date])
            rows.append(row)
        # Main table
        table_html = """
        <style>
        .nowrap-table td, .nowrap-table th { white-space:nowrap; font-size:16px; }
        </style>
        <table class='nowrap-table' border='1' style='border-collapse:collapse;width:auto;'>
            <thead>
                <tr>
                    <th>날짜</th>
                    <th>A조-심사위원</th>
                    <th>A조-참가자</th>
                    <th>B조-심사위원</th>
                    <th>B조-참가자</th>
                </tr>
            </thead>
            <tbody>
        """
        for row in rows:
            table_html += f"<tr><td>{row['날짜']}</td><td>{row['A조-심사위원']}</td><td>{row['A조-참가자']}</td><td>{row['B조-심사위원']}</td><td>{row['B조-참가자']}</td></tr>"
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
        # Special section for 7/18~7/20 (A조 only)
        st.markdown("<br/><b>7/18~7/20 빈자리 (A조만 해당)</b>", unsafe_allow_html=True)
        special_rows = []
        for slot in a_available:
            if slot["date"] in special_dates:
                special_rows.append({
                    "날짜": slot["date"],
                    "역할": slot["role"],
                    "언어": slot["language"],
                    "남은 자리": slot["available"]
                })
        # Sort by date, role, language
        special_rows = sorted(special_rows, key=lambda x: (x["날짜"], x["역할"], x["언어"]))
        # Special table
        special_html = """
        <style>
        .nowrap-table2 td, .nowrap-table2 th { white-space:nowrap; font-size:16px; }
        </style>
        <table class='nowrap-table2' border='1' style='border-collapse:collapse;width:auto;'>
            <thead>
                <tr>
                    <th>날짜</th>
                    <th>역할</th>
                    <th>언어</th>
                    <th>남은 자리</th>
                </tr>
            </thead>
            <tbody>
        """
        for row in special_rows:
            special_html += f"<tr><td>{row['날짜']}</td><td>{row['역할']}</td><td>{row['언어']}</td><td>{row['남은 자리']}</td></tr>"
        special_html += "</tbody></table>"
        st.markdown(special_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"빈자리 확인 중 오류 발생: {e}")
