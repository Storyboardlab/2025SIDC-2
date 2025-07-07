import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import json

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

# --- 빈자리 확인 Section ---
st.subheader("빈자리 확인")
language = st.radio("언어를 선택하세요:", ["영어", "중국어", "일본어"], horizontal=True)

# Row mappings for each date range and category
row_mappings = {
    # 7/10–7/12
    "7/10(목)": {
        "A조": {
            "심사위원": {"영어": 13, "중국어": [15, 16], "일본어": 18},
            "참가자": {"영어": [20, 21], "중국어": [23, 24], "일본어": 26},
        },
        "B조": None  # Add if needed
    },
    "7/11(금)": {
        "A조": {
            "심사위원": {"영어": 13, "중국어": [15, 16], "일본어": 18},
            "참가자": {"영어": [20, 21], "중국어": [23, 24], "일본어": 26},
        },
        "B조": None
    },
    "7/12(토)": {
        "A조": {
            "심사위원": {"영어": 13, "중국어": [15, 16], "일본어": 18},
            "참가자": {"영어": [20, 21], "중국어": [23, 24], "일본어": 26},
        },
        "B조": None
    },
    # 7/13–7/19
    "7/13(일)": {
        "A조": {
            "심사위원": {"영어": [37, 41], "중국어": [43, 48], "일본어": [50, 52]},
            "참가자": {"영어": [54, 55], "중국어": [57, 58], "일본어": 60},
        },
        "B조": None
    },
    # ... (repeat for other dates)
}

# Helper to get worksheet data
@st.cache_data(ttl=60)
def get_sheet_data(tab_name):
    ws = get_worksheet(tab_name)
    return ws.get_all_values()

def get_slot_status(data, col, rows, header_row, role, lang):
    # rows: int or [start, end]
    if isinstance(rows, int):
        slot_rows = [rows-1]  # 0-based
    else:
        slot_rows = list(range(rows[0]-1, rows[-1]))
    # Header cell is row above first slot
    header = data[header_row-1][col] if header_row-1 < len(data) and col < len(data[0]) else ""
    if not header or not re.search(rf"\[{role}\]\s*{lang}", header):
        return "N/A"
    m = re.search(r"(\d+)$", header)
    total = int(m.group(1)) if m else len(slot_rows)
    filled = 0
    for r in slot_rows:
        if r < len(data) and col < len(data[r]):
            cell = data[r][col]
            if role == "심사위원":
                if cell and not ("(no interpreter)" in cell or cell.strip() == ""):
                    filled += 1
            else:  # 참가자
                if cell and cell.strip():
                    filled += 1
    return f"{filled}/{total}"

if language:
    # Dates for each table type
    normal_dates = ["7/10(목)", "7/11(금)", "7/12(토)", "7/13(일)", "7/14(화)", "7/15(화)", "7/16(수)", "7/17(목)", "7/21(월)", "7/22(화)"]
    special_dates = ["7/18(금)", "7/19(토)", "7/20(일)"]

    # Get data for A조 and B조
    try:
        a_data = get_sheet_data("본선 기간(통역팀-A조)")
        b_data = get_sheet_data("본선 기간(통역팀-B조)")
    except Exception as e:
        st.error(f"스프레드시트 접근 중 오류 발생: {e}")
        a_data, b_data = [], []

    # Table for normal dates (7/10–7/17, 7/21–7/22)
    st.markdown("#### 7/10–7/17, 7/21–7/22")
    table = {"날짜": [], "A조 - 심사위원": [], "A조 - 참가자": [], "B조 - 심사위원": [], "B조 - 참가자": []}
    for date in normal_dates:
        table["날짜"].append(date)
        # Example: only A조 for now, col=5 (F)
        # TODO: Map col and rows for each date/category
        if date in row_mappings:
            a_map = row_mappings[date]["A조"]
            # 심사위원
            table["A조 - 심사위원"].append(get_slot_status(a_data, 5, a_map["심사위원"][language], 12, "심사위원", language))
            # 참가자
            table["A조 - 참가자"].append(get_slot_status(a_data, 5, a_map["참가자"][language], 19, "참가자", language))
        else:
            table["A조 - 심사위원"].append("")
            table["A조 - 참가자"].append("")
        # B조: implement similarly if needed
        table["B조 - 심사위원"].append("")
        table["B조 - 참가자"].append("")
    st.table(table)

    # Table for special dates (7/18–7/20)
    st.markdown("#### 7/18–7/20")
    table2 = {"날짜": [], "심사위원": [], "참가자": []}
    for date in special_dates:
        table2["날짜"].append(date)
        table2["심사위원"].append("")  # TODO: implement
        table2["참가자"].append("")  # TODO: implement
    st.table(table2)
