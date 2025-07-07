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

# Add a new section for 빈자리 확인
st.header("빈자리 확인")
language = st.radio("언어를 선택하세요:", ["영어", "중국어", "일본어"], horizontal=True)

# Row mapping for each date, role, and language
row_map = {
    # 7/10–7/12
    "7/10(목)": {
        "심사위원": {"영어": [13], "중국어": [15,16], "일본어": [18]},
        "참가자": {"영어": [20,21], "중국어": [23,24], "일본어": [26]},
    },
    "7/11(금)": {
        "심사위원": {"영어": [13], "중국어": [15,16], "일본어": [18]},
        "참가자": {"영어": [20,21], "중국어": [23,24], "일본어": [26]},
    },
    "7/12(토)": {
        "심사위원": {"영어": [13], "중국어": [15,16], "일본어": [18]},
        "참가자": {"영어": [20,21], "중국어": [23,24], "일본어": [26]},
    },
    # 7/13–7/19
    "7/13(일)": {
        "심사위원": {"영어": list(range(37,42)), "중국어": list(range(43,49)), "일본어": list(range(50,53))},
        "참가자": {"영어": [54,55], "중국어": [57,58], "일본어": [60]},
    },
    "7/14(화)": {
        "심사위원": {"영어": list(range(37,42)), "중국어": list(range(43,49)), "일본어": list(range(50,53))},
        "참가자": {"영어": [54,55], "중국어": [57,58], "일본어": [60]},
    },
    "7/15(화)": {
        "심사위원": {"영어": list(range(37,42)), "중국어": list(range(43,49)), "일본어": list(range(50,53))},
        "참가자": {"영어": [54,55], "중국어": [57,58], "일본어": [60]},
    },
    "7/16(수)": {
        "심사위원": {"영어": list(range(37,42)), "중국어": list(range(43,49)), "일본어": list(range(50,53))},
        "참가자": {"영어": [54,55], "중국어": [57,58], "일본어": [60]},
    },
    "7/17(목)": {
        "심사위원": {"영어": list(range(37,42)), "중국어": list(range(43,49)), "일본어": list(range(50,53))},
        "참가자": {"영어": [54,55], "중국어": [57,58], "일본어": [60]},
    },
    "7/18(금)": {
        "심사위원": {"영어": [71,72,73], "중국어": [75], "일본어": [77]},
        "참가자": {"영어": [79,80], "중국어": [82,83], "일본어": []},
    },
    "7/19(토)": {
        "심사위원": {"영어": [71,72,73], "중국어": [75], "일본어": [77]},
        "참가자": {"영어": [79,80], "중국어": [82,83], "일본어": []},
    },
    "7/20(일)": {
        "심사위원": {"영어": [71,72,73], "중국어": [75], "일본어": [77]},
        "참가자": {"영어": [79,80], "중국어": [82,83], "일본어": []},
    },
    "7/21(월)": {
        "심사위원": {"영어": [71,72,73], "중국어": [75], "일본어": [77]},
        "참가자": {"영어": [79,80], "중국어": [82,83], "일본어": []},
    },
    "7/22(화)": {
        "심사위원": {"영어": [71,72,73], "중국어": [75], "일본어": [77]},
        "참가자": {"영어": [79,80], "중국어": [82,83], "일본어": []},
    },
}

def get_header_row(alloc_rows):
    if not alloc_rows:
        return None
    return min(alloc_rows) - 1

def parse_header(cell):
    m = re.match(r"\[(심사위원|참가자)\]\s*(영어|중국어|일본어)\s*(\d+)", cell or "")
    if m:
        return int(m.group(3))
    return None

def count_filled_slots(data, col_idx, alloc_rows, role):
    filled = 0
    for r in alloc_rows:
        if r-1 < len(data) and col_idx < len(data[r-1]):
            val = data[r-1][col_idx]
            if role == "심사위원":
                if re.match(r"\[[^\]]+\]\s*.+", val):
                    filled += 1
            elif role == "참가자":
                if val.strip():
                    filled += 1
    return filled

def get_empty_slots(ws, col, alloc_rows, role):
    data = ws.get_all_values()
    col_idx = ord(col) - ord('A')
    header_row = get_header_row(alloc_rows)
    if header_row is None or header_row >= len(data):
        return "N/A"
    header = data[header_row][col_idx] if col_idx < len(data[header_row]) else ""
    total = parse_header(header)
    if not total:
        return "N/A"
    filled = count_filled_slots(data, col_idx, alloc_rows, role)
    return total - filled

def get_table_data(dates, ws, language):
    rows = []
    for date in dates:
        row = [date]
        for role in ["심사위원", "참가자"]:
            alloc_rows = row_map.get(date, {}).get(role, {}).get(language, [])
            if not alloc_rows:
                row.append("N/A")
                continue
            # Guess column: for A조 use 'B', for B조 use 'C' (adjust if needed)
            col = 'B' if ws.title.endswith('A조') else 'C'
            empty = get_empty_slots(ws, col, alloc_rows, role)
            row.append(empty)
        rows.append(row)
    return rows

if language:
    a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
    b_ws_t = get_worksheet("본선 기간(통역팀-B조)")

    normal_dates = ["7/10(목)", "7/11(금)", "7/12(토)", "7/13(일)", "7/14(화)", "7/15(화)", "7/16(수)", "7/17(목)", "7/21(월)", "7/22(화)"]
    special_dates = ["7/18(금)", "7/19(토)", "7/20(일)"]

    st.subheader("7/10–7/17, 7/21–7/22")
    a_data = get_table_data(normal_dates, a_ws_t, language)
    b_data = get_table_data(normal_dates, b_ws_t, language)
    st.table({
        "날짜": normal_dates,
        "A조 - 심사위원": [row[1] for row in a_data],
        "A조 - 참가자": [row[2] for row in a_data],
        "B조 - 심사위원": [row[1] for row in b_data],
        "B조 - 참가자": [row[2] for row in b_data],
    })

    st.subheader("7/18–7/20")
    a_data = get_table_data(special_dates, a_ws_t, language)
    b_data = get_table_data(special_dates, b_ws_t, language)
    st.table({
        "날짜": special_dates,
        "A조 - 심사위원": [row[1] for row in a_data],
        "A조 - 참가자": [row[2] for row in a_data],
        "B조 - 심사위원": [row[1] for row in b_data],
        "B조 - 참가자": [row[2] for row in b_data],
    })
