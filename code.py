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
    # Hardcoded slot row ranges for each date/role/language
    allocation_ranges = {
        # 7/10~7/12
        "7/10(목)": {
            ("심사위원", "영어"): [13, 13],
            ("심사위원", "중국어"): [15, 16],
            ("심사위원", "일본어"): [18, 18],
            ("참가자", "영어"): [20, 21],
            ("참가자", "중국어"): [23, 24],
            ("참가자", "일본어"): [26, 26],
        },
        "7/11(금)": {
            ("심사위원", "영어"): [13, 13],
            ("심사위원", "중국어"): [15, 16],
            ("심사위원", "일본어"): [18, 18],
            ("참가자", "영어"): [20, 21],
            ("참가자", "중국어"): [23, 24],
            ("참가자", "일본어"): [26, 26],
        },
        "7/12(토)": {
            ("심사위원", "영어"): [13, 13],
            ("심사위원", "중국어"): [15, 16],
            ("심사위원", "일본어"): [18, 18],
            ("참가자", "영어"): [20, 21],
            ("참가자", "중국어"): [23, 24],
            ("참가자", "일본어"): [26, 26],
        },
        # 7/13~7/19
        "7/13(일)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/14(화)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/15(화)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/16(수)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/17(목)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/18(금)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        "7/19(토)": {
            ("심사위원", "영어"): [37, 41],
            ("심사위원", "중국어"): [43, 48],
            ("심사위원", "일본어"): [50, 52],
            ("참가자", "영어"): [54, 55],
            ("참가자", "중국어"): [57, 58],
            ("참가자", "일본어"): [60, 60],
        },
        # 7/20~7/22
        "7/20(일)": {
            ("심사위원", "영어"): [71, 73],
            ("심사위원", "중국어"): [75, 75],
            ("심사위원", "일본어"): [77, 77],
            ("참가자", "영어"): [79, 80],
            ("참가자", "중국어"): [82, 83],
        },
        "7/21(월)": {
            ("심사위원", "영어"): [71, 73],
            ("심사위원", "중국어"): [75, 75],
            ("심사위원", "일본어"): [77, 77],
            ("참가자", "영어"): [79, 80],
            ("참가자", "중국어"): [82, 83],
        },
        "7/22(화)": {
            ("심사위원", "영어"): [71, 73],
            ("심사위원", "중국어"): [75, 75],
            ("심사위원", "일본어"): [77, 77],
            ("참가자", "영어"): [79, 80],
            ("참가자", "중국어"): [82, 83],
        },
    }
    assignments = []
    for date_label, cell_range in date_range_map:
        if date_label not in allocation_ranges:
            continue
        match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range)
        if not match:
            continue
        col_start, row_start, col_end, row_end = match.groups()
        col_idx = ord(col_start) - ord('A')
        for (role, language), (row_start_idx, row_end_idx) in allocation_ranges[date_label].items():
            # Header is one row above the start
            header_row = row_start_idx - 1
            header_cell = data[header_row][col_idx] if header_row < len(data) and col_idx < len(data[header_row]) else ""
            if not header_cell or header_cell.strip() == "":
                available_count = "N/A"
            else:
                available_count = 0
                for row in range(row_start_idx, row_end_idx + 1):
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
            # Default values
            table[date] = {"A조-심사위원": 0, "A조-참가자": 0, "B조-심사위원": 0, "B조-참가자": 0}
            # 7/10(목) and 7/14(월) have no 참가자 통역
            if date in ["7/10(목)", "7/14(월)"]:
                table[date]["A조-참가자"] = "N/A"
                table[date]["B조-참가자"] = "N/A"
            # 7/18~7/22 have no 참가자 일본어 통역
            if date in ["7/18(금)", "7/19(토)", "7/20(일)", "7/21(월)", "7/22(화)"]:
                # This only affects the special section for 7/18~20, but for 7/21~22, set B조/A조-참가자 to N/A if language is 일본어
                if date not in special_dates:
                    # For main table, set 참가자 일본어 to N/A (if language is 일본어, handled below)
                    pass  # handled in special section
        for slot in a_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                continue
            # Only update if not N/A
            if role == "심사위원":
                table[date]["A조-심사위원"] += count
            elif role == "참가자" and table[date]["A조-참가자"] != "N/A":
                table[date]["A조-참가자"] += count
        for slot in b_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                continue
            if role == "심사위원":
                table[date]["B조-심사위원"] += count
            elif role == "참가자" and table[date]["B조-참가자"] != "N/A":
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
        # Build a dict for each date: {date: {role: count or 'N/A'}}
        special_dict = {d: {"심사위원": "N/A", "참가자": "N/A"} for d in ["7/18(금)", "7/19(토)", "7/20(일)"]}
        for slot in a_available:
            if slot["date"] in special_dict:
                role = slot["role"]
                # Only for the selected language
                if slot["language"] == language_selected:
                    special_dict[slot["date"]][role] = slot["available"]
        # For 참가자-일본어, ensure N/A if language_selected is 일본어
        if language_selected == "일본어":
            for d in special_dict:
                special_dict[d]["참가자"] = "N/A"
        # Build rows for table
        special_rows = []
        for d in ["7/18(금)", "7/19(토)", "7/20(일)"]:
            special_rows.append({
                "날짜": d,
                "심사위원": special_dict[d]["심사위원"],
                "참가자": special_dict[d]["참가자"]
            })
        # Special table
        special_html = """
        <style>
        .nowrap-table2 td, .nowrap-table2 th { white-space:nowrap; font-size:16px; }
        </style>
        <table class='nowrap-table2' border='1' style='border-collapse:collapse;width:auto;'>
            <thead>
                <tr>
                    <th>날짜</th>
                    <th>심사위원</th>
                    <th>참가자</th>
                </tr>
            </thead>
            <tbody>
        """
        for row in special_rows:
            special_html += f"<tr><td>{row['날짜']}</td><td>{row['심사위원']}</td><td>{row['참가자']}</td></tr>"
        special_html += "</tbody></table>"
        st.markdown(special_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"빈자리 확인 중 오류 발생: {e}")
