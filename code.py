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
    # Hardcoded row offsets for each date and role/language
    offset_map = {
        # 7/11 and 7/12
        "7/11(금)": {
            "심사위원": {"영어": [3], "중국어": [5, 6], "일본어": [8]},
            "참가자": {"영어": [10, 11], "중국어": [13, 14], "일본어": [16]},
        },
        "7/12(토)": {
            "심사위원": {"영어": [3], "중국어": [5, 6], "일본어": [8]},
            "참가자": {"영어": [10, 11], "중국어": [13, 14], "일본어": [16]},
        },
        # 7/13 to 7/19
        "7/13(일)": None, "7/14(화)": None, "7/15(화)": None, "7/16(수)": None, "7/17(목)": None, "7/18(금)": None, "7/19(토)": None,
        # 7/20 to 7/22
        "7/20(일)": None, "7/21(월)": None, "7/22(화)": None,
    }
    # Fill in 7/13~7/19
    for d in ["7/13(일)", "7/14(화)", "7/15(화)", "7/16(수)", "7/17(목)", "7/18(금)", "7/19(토)"]:
        offset_map[d] = {
            "심사위원": {"영어": [3,4,5,6,7], "중국어": [9,10,11,12,13,14], "일본어": [16,17,18]},
            "참가자": {"영어": [20,21], "중국어": [23,24], "일본어": [26]},
        }
    # Fill in 7/20~7/22
    for d in ["7/20(일)", "7/21(월)", "7/22(화)"]:
        offset_map[d] = {
            "심사위원": {"영어": [3,4,5], "중국어": [7], "일본어": [9]},
            "참가자": {"영어": [11,12], "중국어": [14,15]},
        }
    assignments = []
    for date_label, cell_range in date_range_map:
        if date_label not in offset_map:
            continue
        match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range)
        if not match:
            continue
        col_start, row_start, col_end, row_end = match.groups()
        col_idx = ord(col_start) - ord('A')  # always single column
        row_start_idx = int(row_start) - 1
        # For each role/language, check the specified offsets
        for role in offset_map[date_label]:
            for language in offset_map[date_label][role]:
                offsets = offset_map[date_label][role][language]
                available_count = 0
                for offset in offsets:
                    row = row_start_idx + offset
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
                if available_count > 0:
                    assignments.append({
                        "date": date_label,
                        "role": role,
                        "language": language,
                        "available": available_count
                    })
    return assignments

st.markdown("---")
st.subheader("빈자리 확인")

# Custom HTML/CSS for language selection buttons
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "영어"

lang_labels = ["영어", "중국어", "일본어"]
lang_keys = ["영어", "중국어", "일본어"]
lang_html = "<div style='display:flex;gap:8px;align-items:center;'>"
for label, key in zip(lang_labels, lang_keys):
    selected = (st.session_state.selected_language == key)
    style = (
        "background:#2563eb;color:white;border:none;padding:8px 20px;border-radius:6px;font-size:18px;cursor:pointer;white-space:nowrap;"
        if selected else
        "background:#f1f1f1;color:#222;border:none;padding:8px 20px;border-radius:6px;font-size:18px;cursor:pointer;white-space:nowrap;"
    )
    lang_html += f"<form style='display:inline;' action='' method='post'><button name='langbtn' value='{key}' style='{style}'>{label}</button></form>"
lang_html += "</div>"
lang_event = st.markdown(lang_html, unsafe_allow_html=True)

# Button click handling (simulate POST)
import streamlit as st
from streamlit import runtime
if runtime.exists():
    import streamlit.web.server.websocket_headers as _wh
    from streamlit.web.server import Server
    from urllib.parse import parse_qs
    ctx = st.runtime.scriptrunner.get_script_run_ctx()
    if ctx and hasattr(ctx, 'request') and ctx.request:
        body = ctx.request.body.decode() if hasattr(ctx.request, 'body') else ''
        if 'langbtn=' in body:
            val = parse_qs(body).get('langbtn', [None])[0]
            if val in lang_keys:
                st.session_state.selected_language = val

language_selected = st.session_state.selected_language

if language_selected:
    try:
        a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_available = [slot for slot in find_available_slots(a_ws_t, interpreter_date_range_map) if slot["language"] == language_selected]
        b_available = [slot for slot in find_available_slots(b_ws_t, interpreter_date_range_map) if slot["language"] == language_selected]
        special_dates = {"7/18(금)", "7/19(토)", "7/20(일)"}
        all_dates = [d for d, _ in interpreter_date_range_map]
        table = {}
        for date in all_dates:
            if date in special_dates:
                table[date] = {"A조-심사위원": "N/A", "A조-참가자": "N/A", "B조-심사위원": "N/A", "B조-참가자": "N/A"}
            else:
                table[date] = {"A조-심사위원": 0, "A조-참가자": 0, "B조-심사위원": 0, "B조-참가자": 0}
        for slot in a_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                if role == "심사위원":
                    table[date]["A조-심사위원"] = count
                elif role == "참가자":
                    table[date]["A조-참가자"] = count
            else:
                if role == "심사위원":
                    table[date]["A조-심사위원"] += count
                elif role == "참가자":
                    table[date]["A조-참가자"] += count
        for slot in b_available:
            date = slot["date"]
            role = slot["role"]
            count = slot["available"]
            if date in special_dates:
                if role == "심사위원":
                    table[date]["B조-심사위원"] = count
                elif role == "참가자":
                    table[date]["B조-참가자"] = count
            else:
                if role == "심사위원":
                    table[date]["B조-심사위원"] += count
                elif role == "참가자":
                    table[date]["B조-참가자"] += count
        rows = []
        for date in all_dates:
            row = {"날짜": date}
            row.update(table[date])
            rows.append(row)
        # Custom HTML table with nowrap style
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
    except Exception as e:
        st.error(f"빈자리 확인 중 오류 발생: {e}")
