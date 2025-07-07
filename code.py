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

def find_available_slots(worksheet):
    """
    Detect available interpreter slots for 7/13(일) (B34:B61) only.
    Returns a list of dicts: {section, header, total_slots, available_slots, status, details}
    """
    # 0-based indices for B column (col_idx = 1)
    slot_sections = [
        {"section": "[심사위원] 영어", "header_row": 35, "slot_rows": list(range(36, 41+1))},
        {"section": "[심사위원] 중국어", "header_row": 42, "slot_rows": list(range(43, 48+1))},
        {"section": "[심사위원] 일본어", "header_row": 49, "slot_rows": list(range(50, 52+1))},
        {"section": "[참가자] 영어", "header_row": 53, "slot_rows": list(range(54, 55+1))},
        {"section": "[참가자] 중국어", "header_row": 56, "slot_rows": list(range(57, 58+1))},
        {"section": "[참가자] 일본어", "header_row": 59, "slot_rows": [60]},
    ]
    col_idx = 1  # B column
    data = worksheet.get_all_values()
    results = []
    for section in slot_sections:
        header = data[section["header_row"]][col_idx] if section["header_row"] < len(data) and col_idx < len(data[section["header_row"]]) else ""
        if not header.strip():
            results.append({"section": section["section"], "status": "N/A", "header": "", "total_slots": 0, "available_slots": 0, "details": []})
            continue
        # Parse slot count from header, e.g., [심사위원] 영어 2
        m = re.match(r"\[[^\]]+\]\s*([^\d]+)?(\d+)?", header)
        slot_count = None
        if m and m.group(2):
            slot_count = int(m.group(2))
        else:
            slot_count = len(section["slot_rows"])
        available = 0
        details = []
        for row in section["slot_rows"]:
            if row >= len(data):
                details.append("(out of range)")
                continue
            cell = data[row][col_idx] if col_idx < len(data[row]) else ""
            # Available if blank or only [judge]
            if not cell.strip():
                available += 1
                details.append("(blank)")
            elif re.match(r"^\[[^\]]+\]$", cell.strip()):
                available += 1
                details.append(cell.strip())
            else:
                details.append(cell.strip())
        results.append({
            "section": section["section"],
            "header": header,
            "total_slots": slot_count,
            "available_slots": available,
            "status": "OK" if available > 0 else "Full",
            "details": details
        })
    return results

st.title("2025 서울국제무용콩쿠르 서포터즈")
st.subheader("통역팀 배정 내역")

name = st.text_input("이름을 입력한 후 엔터를 눌러 주세요:")

a_ws_t = None
try:
    a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
except Exception as e:
    st.error(f"A조 시트 접근 중 오류 발생: {e}")

if name:
    try:
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_assignments = find_assignments_by_range(a_ws_t, name, interpreter_date_range_map) if a_ws_t else []
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

# Always show 7/13 slot availability if worksheet loaded
if a_ws_t:
    st.subheader("7/13(일) 빈 슬롯 현황 (A조)")
    a_slots = find_available_slots(a_ws_t)
    for slot in a_slots:
        st.write(f"{slot['section']} | 헤더: {slot['header']} | 총 슬롯: {slot['total_slots']} | 남은 슬롯: {slot['available_slots']} | 상태: {slot['status']}")
        st.write(f"  세부: {slot['details']}")
else:
    st.info("결과가 나오기 까지 15초 정도 걸릴 수 있습니다.")
