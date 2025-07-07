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

# --- Slot allocation configuration ---
# Each entry: (date, section, role, language, header_row, allocation_rows)
# Section: 'A' or 'B'
# Role: '심사위원' or '참가자'
# Language: '영어', '중국어', '일본어'
# header_row and allocation_rows are 1-based (spreadsheet style)
allocation_config = [
    ("7/10(목)", section, "심사위원", "영어", 12, [13])
    for section in ("A", "B")
] + [
    ("7/10(목)", section, "심사위원", "중국어", 14, [15,16])
    for section in ("A", "B")
] + [
    ("7/10(목)", section, "심사위원", "일본어", 17, [18])
    for section in ("A", "B")
] + [
    ("7/10(목)", section, "참가자", "영어", 19, [20,21])
    for section in ("A", "B")
] + [
    ("7/10(목)", section, "참가자", "중국어", 22, [23,24])
    for section in ("A", "B")
] + [
    ("7/10(목)", section, "참가자", "일본어", 25, [26])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "심사위원", "영어", 12, [13])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "심사위원", "중국어", 14, [15,16])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "심사위원", "일본어", 17, [18])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "참가자", "영어", 19, [20,21])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "참가자", "중국어", 22, [23,24])
    for section in ("A", "B")
] + [
    ("7/11(금)", section, "참가자", "일본어", 25, [26])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "심사위원", "영어", 12, [13])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "심사위원", "중국어", 14, [15,16])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "심사위원", "일본어", 17, [18])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "참가자", "영어", 19, [20,21])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "참가자", "중국어", 22, [23,24])
    for section in ("A", "B")
] + [
    ("7/12(토)", section, "참가자", "일본어", 25, [26])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "심사위원", "영어", 36, [37,38,39,40,41])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "심사위원", "중국어", 42, [43,44,45,46,47,48])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "심사위원", "일본어", 49, [50,51,52])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "참가자", "영어", 53, [54,55])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "참가자", "중국어", 56, [57,58])
    for section in ("A", "B")
] + [
    ("7/13(일)", section, "참가자", "일본어", 59, [60])
    for section in ("A", "B")
]

def extract_slot_counts(worksheet, language):
    data = worksheet.get_all_values()
    results = {}
    for entry in allocation_config:
        date, section, role, lang, header_row, alloc_rows = entry
        if lang != language:
            continue
        # Adjust for 0-based index
        header_row_idx = header_row - 1
        alloc_row_indices = [r-1 for r in alloc_rows]
        # Find header cell in the correct column (first non-empty in row)
        header_cell = None
        for col in range(len(data[header_row_idx])):
            cell = data[header_row_idx][col]
            if cell:
                header_cell = cell
                break
        if not header_cell:
            total_slots = "N/A"
        else:
            m = re.match(r"\[(심사위원|참가자)\]\s*([가-힣]+)\s*(\d+)", header_cell)
            if m:
                total_slots = int(m.group(3))
            else:
                total_slots = "N/A"
        filled = 0
        empty = 0
        if total_slots != "N/A":
            for r in alloc_row_indices:
                for col in range(len(data[r])):
                    cell = data[r][col]
                    if role == "심사위원":
                        # [심사위원이름] interpreter or [심사위원이름] blank
                        if cell:
                            judge_match = re.match(r"\[([^\]]+)\](.*)", cell)
                            if judge_match:
                                interpreter = judge_match.group(2).strip()
                                if interpreter:
                                    filled += 1
                                else:
                                    empty += 1
                    elif role == "참가자":
                        if cell:
                            filled += 1
                        else:
                            empty += 1
        results[(date, section, role)] = {
            "total": total_slots,
            "filled": filled,
            "empty": empty if total_slots != "N/A" else "N/A"
        }
    return results

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

if language:
    # Dates for each table type
    normal_dates = ["7/10(목)", "7/11(금)", "7/12(토)", "7/13(일)", "7/14(화)", "7/15(화)", "7/16(수)", "7/17(목)", "7/21(월)", "7/22(화)"]
    special_dates = ["7/18(금)", "7/19(토)", "7/20(일)"]

    # Get worksheets for A조 and B조
    a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
    b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
    a_slots = extract_slot_counts(a_ws_t, language)
    b_slots = extract_slot_counts(b_ws_t, language)

    # Table for normal dates (7/10–7/17, 7/21–7/22)
    st.markdown("#### 7/10–7/17, 7/21–7/22")
    table_normal = {
        "날짜": normal_dates,
        "A조 - 심사위원": [],
        "A조 - 참가자": [],
        "B조 - 심사위원": [],
        "B조 - 참가자": [],
    }
    for date in normal_dates:
        # 심사위원
        a_judge = a_slots.get((date, "A", "심사위원"), {}).get("empty", "N/A")
        a_part = a_slots.get((date, "A", "참가자"), {}).get("empty", "N/A")
        b_judge = b_slots.get((date, "B", "심사위원"), {}).get("empty", "N/A")
        b_part = b_slots.get((date, "B", "참가자"), {}).get("empty", "N/A")
        table_normal["A조 - 심사위원"].append(a_judge)
        table_normal["A조 - 참가자"].append(a_part)
        table_normal["B조 - 심사위원"].append(b_judge)
        table_normal["B조 - 참가자"].append(b_part)
    st.table(table_normal)

    # Table for special dates (7/18–7/20)
    st.markdown("#### 7/18–7/20")
    table_special = {
        "날짜": special_dates,
        "심사위원": [],
        "참가자": [],
    }
    for date in special_dates:
        # For special dates, sum A+B for each role
        judge_empty = 0
        judge_na = True
        part_empty = 0
        part_na = True
        for section, slots in [("A", a_slots), ("B", b_slots)]:
            judge_val = slots.get((date, section, "심사위원"), {}).get("empty", "N/A")
            part_val = slots.get((date, section, "참가자"), {}).get("empty", "N/A")
            if judge_val != "N/A":
                judge_empty += judge_val
                judge_na = False
            if part_val != "N/A":
                part_empty += part_val
                part_na = False
        table_special["심사위원"].append("N/A" if judge_na else judge_empty)
        table_special["참가자"].append("N/A" if part_na else part_empty)
    st.table(table_special)
