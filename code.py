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

def find_dates_by_range(worksheet, name, date_range_map):
    found = []
    for date_label, cell_range in date_range_map:
        cell_list = worksheet.range(cell_range)
        for cell in cell_list:
            if cell.value and name in cell.value:
                found.append(date_label)
                break  # Only need to find once per date
    return found

st.title("2025 서울국제무용콩쿠르 서포터즈")
st.subheader("통역팀 배정 내역")

name = st.text_input("이름을 입력한 후 엔터를 눌러 주세요:")

if name:
    try:
        a_ws_t = get_worksheet("본선 기간(통역팀-A조)")
        b_ws_t = get_worksheet("본선 기간(통역팀-B조)")
        a_dates = find_dates_by_range(a_ws_t, name, interpreter_date_range_map)
        b_dates = find_dates_by_range(b_ws_t, name, interpreter_date_range_map)

        special_dates = {"7/18(금)", "7/19(토)", "7/20(일)"}
        a_normal = [d for d in a_dates if d not in special_dates]
        a_special = [d for d in a_dates if d in special_dates]

        st.subheader("A조 출근일자 (통역팀)")
        st.write(", ".join(a_normal) if a_normal else "없음")

        st.subheader("B조 출근일자 (통역팀)")
        st.write(", ".join(b_dates) if b_dates else "없음")

        st.subheader("7/18 ~ 7/20 출근일자 (통역팀)")
        st.write(", ".join(a_special) if a_special else "없음")

    except Exception as e:
        st.error(f"스프레드시트 접근 중 오류 발생: {e}")
else:
    st.info("결과가 나오기 까지 15초 정도 걸릴 수 있습니다.")
