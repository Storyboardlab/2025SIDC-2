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

# Allocation mapping: date -> team -> role -> (col, header_row, alloc_rows)
allocation_map = {
    # 7/10–7/12
    "7/10(목)": {
        "A조": {
            "심사위원": {"영어": ("F", 12, [13]), "중국어": ("F", 14, [15,16]), "일본어": ("F", 17, [18])},
            "참가자": {"영어": ("F", 19, [20,21]), "중국어": ("F", 22, [23,24]), "일본어": ("F", 25, [26])},
        },
        "B조": None,
    },
    "7/11(금)": {
        "A조": {
            "심사위원": {"영어": ("G", 12, [13]), "중국어": ("G", 14, [15,16]), "일본어": ("G", 17, [18])},
            "참가자": {"영어": ("G", 19, [20,21]), "중국어": ("G", 22, [23,24]), "일본어": ("G", 25, [26])},
        },
        "B조": None,
    },
    "7/12(토)": {
        "A조": {
            "심사위원": {"영어": ("H", 12, [13]), "중국어": ("H", 14, [15,16]), "일본어": ("H", 17, [18])},
            "참가자": {"영어": ("H", 19, [20,21]), "중국어": ("H", 22, [23,24]), "일본어": ("H", 25, [26])},
        },
        "B조": None,
    },
    # 7/13–7/19
    "7/13(일)": {
        "A조": {
            "심사위원": {"영어": ("B", 36, list(range(37,42))), "중국어": ("B", 42, list(range(43,49))), "일본어": ("B", 49, list(range(50,53)))},
            "참가자": {"영어": ("B", 53, [54,55]), "중국어": ("B", 56, [57,58]), "일본어": ("B", 59, [60])},
        },
        "B조": None,
    },
    "7/14(화)": {
        "A조": {
            "심사위원": {"영어": ("C", 36, list(range(37,42))), "중국어": ("C", 42, list(range(43,49))), "일본어": ("C", 49, list(range(50,53)))},
            "참가자": {"영어": ("C", 53, [54,55]), "중국어": ("C", 56, [57,58]), "일본어": ("C", 59, [60])},
        },
        "B조": None,
    },
    "7/15(화)": {
        "A조": {
            "심사위원": {"영어": ("D", 36, list(range(37,42))), "중국어": ("D", 42, list(range(43,49))), "일본어": ("D", 49, list(range(50,53)))},
            "참가자": {"영어": ("D", 53, [54,55]), "중국어": ("D", 56, [57,58]), "일본어": ("D", 59, [60])},
        },
        "B조": None,
    },
    "7/16(수)": {
        "A조": {
            "심사위원": {"영어": ("E", 36, list(range(37,42))), "중국어": ("E", 42, list(range(43,49))), "일본어": ("E", 49, list(range(50,53)))},
            "참가자": {"영어": ("E", 53, [54,55]), "중국어": ("E", 56, [57,58]), "일본어": ("E", 59, [60])},
        },
        "B조": None,
    },
    "7/17(목)": {
        "A조": {
            "심사위원": {"영어": ("F", 36, list(range(37,42))), "중국어": ("F", 42, list(range(43,49))), "일본어": ("F", 49, list(range(50,53)))},
            "참가자": {"영어": ("F", 53, [54,55]), "중국어": ("F", 56, [57,58]), "일본어": ("F", 59, [60])},
        },
        "B조": None,
    },
    # 7/18–7/20 (special)
    "7/18(금)": {
        "A조": {
            "심사위원": {"영어": ("G", 70, [71,72,73]), "중국어": ("G", 74, [75]), "일본어": ("G", 76, [77])},
            "참가자": {"영어": ("G", 78, [79,80]), "중국어": ("G", 81, [82,83])},
        },
        "B조": None,
    },
    "7/19(토)": {
        "A조": {
            "심사위원": {"영어": ("H", 70, [71,72,73]), "중국어": ("H", 74, [75]), "일본어": ("H", 76, [77])},
            "참가자": {"영어": ("H", 78, [79,80]), "중국어": ("H", 81, [82,83])},
        },
        "B조": None,
    },
    "7/20(일)": {
        "A조": {
            "심사위원": {"영어": ("B", 70, [71,72,73]), "중국어": ("B", 74, [75]), "일본어": ("B", 76, [77])},
            "참가자": {"영어": ("B", 78, [79,80]), "중국어": ("B", 81, [82,83])},
        },
        "B조": None,
    },
    # 7/21–7/22
    "7/21(월)": {
        "A조": {
            "심사위원": {"영어": ("C", 70, [71,72,73]), "중국어": ("C", 74, [75]), "일본어": ("C", 76, [77])},
            "참가자": {"영어": ("C", 78, [79,80]), "중국어": ("C", 81, [82,83])},
        },
        "B조": None,
    },
    "7/22(화)": {
        "A조": {
            "심사위원": {"영어": ("D", 70, [71,72,73]), "중국어": ("D", 74, [75]), "일본어": ("D", 76, [77])},
            "참가자": {"영어": ("D", 78, [79,80]), "중국어": ("D", 81, [82,83])},
        },
        "B조": None,
    },
}

def get_empty_count(ws, col, header_row, alloc_rows, role, language):
    # Convert col letter to index
    col_idx = ord(col) - ord('A')
    data = ws.get_all_values()
    # Header cell
    if header_row >= len(data):
        return "N/A"
    header = data[header_row][col_idx] if col_idx < len(data[header_row]) else ""
    # Extract quota
    m = re.match(r"\[(심사위원|참가자)\]\s*" + language + r"\s*(\d+)", header)
    if not m:
        return "N/A"
    quota = int(m.group(2))
    filled = 0
    for r in alloc_rows:
        if r >= len(data):
            continue
        cell = data[r][col_idx] if col_idx < len(data[r]) else ""
        if role == "심사위원":
            # [심사위원이름] 통역사이름 → filled, [심사위원이름] → empty, blank → ignore
            if cell.strip() == "":
                continue
            if re.match(r"\[[^\]]+\]\s*.+", cell):
                filled += 1
        else:
            # 참가자: any non-empty cell = filled
            if cell.strip() != "":
                filled += 1
    return quota - filled

@st.cache_resource(ttl=60)
def get_interpreter_worksheets():
    a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
    b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
    return a_ws_t, b_ws_t

if language:
    # Prepare worksheet
    a_ws_t, b_ws_t = get_interpreter_worksheets()
    normal_dates = ["7/10(목)", "7/11(금)", "7/12(토)", "7/13(일)", "7/14(화)", "7/15(화)", "7/16(수)", "7/17(목)", "7/21(월)", "7/22(화)"]
    special_dates = ["7/18(금)", "7/19(토)", "7/20(일)"]

    # Table for normal dates (7/10–7/17, 7/21–7/22)
    table_normal = {"날짜": [], "A조 - 심사위원": [], "A조 - 참가자": [], "B조 - 심사위원": [], "B조 - 참가자": []}
    for d in normal_dates:
        table_normal["날짜"].append(d)
        for team, ws, col1, col2 in [("A조", a_ws_t, "A조 - 심사위원", "A조 - 참가자"), ("B조", b_ws_t, "B조 - 심사위원", "B조 - 참가자")]:
            v1 = v2 = "N/A"
            if allocation_map.get(d, {}).get(team):
                if allocation_map[d][team]["심사위원"].get(language):
                    col, header_row, alloc_rows = allocation_map[d][team]["심사위원"][language]
                    v1 = get_empty_count(ws, col, header_row, alloc_rows, "심사위원", language)
                if allocation_map[d][team]["참가자"].get(language):
                    col, header_row, alloc_rows = allocation_map[d][team]["참가자"][language]
                    v2 = get_empty_count(ws, col, header_row, alloc_rows, "참가자", language)
            table_normal[col1].append(v1)
            table_normal[col2].append(v2)
    st.markdown("#### 7/10–7/17, 7/21–7/22")
    st.table(table_normal)

    # Table for special dates (7/18–7/20)
    table_special = {"날짜": [], "심사위원": [], "참가자": []}
    for d in special_dates:
        table_special["날짜"].append(d)
        v1 = v2 = "N/A"
        if allocation_map.get(d, {}).get("A조"):
            if allocation_map[d]["A조"]["심사위원"].get(language):
                col, header_row, alloc_rows = allocation_map[d]["A조"]["심사위원"][language]
                v1 = get_empty_count(a_ws_t, col, header_row, alloc_rows, "심사위원", language)
            if allocation_map[d]["A조"]["참가자"].get(language):
                col, header_row, alloc_rows = allocation_map[d]["A조"]["참가자"][language]
                v2 = get_empty_count(a_ws_t, col, header_row, alloc_rows, "참가자", language)
        table_special["심사위원"].append(v1)
        table_special["참가자"].append(v2)
    st.markdown("#### 7/18–7/20")
    st.table(table_special)
