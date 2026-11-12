
import streamlit as st
import requests

st.set_page_config(page_title="모두의 점심", page_icon="🍱")

st.title("🍱 모두의 점심")
st.write("오늘 점심으로 먹고 싶은 메뉴에 투표해 보세요!")

# 구글 시트 연결 주소 가져오기
try:
    SHEET_URL = st.secrets["SHEET_URL"]
except (KeyError, FileNotFoundError):
    st.error("구글 시트 연결 설정을 확인해 주세요.")
    st.stop()


# 구글 시트에 투표 저장하기
def save_vote(nickname, menu):
    response = requests.post(
        SHEET_URL,
        json={
            "data": {
                "member": nickname,
                "menu": menu,
                "type": "희망메뉴"
            }
        },
        timeout=15
    )
    response.raise_for_status()
    result = response.json()

    return result.get("ok") is True


# 구글 시트에서 투표 목록 읽기
def load_votes():
    response = requests.get(
        SHEET_URL,
        timeout=15
    )
    response.raise_for_status()

    rows = response.json()

    # 응답 형식 확인
    if not isinstance(rows, list):
        raise ValueError("투표 목록의 응답 형식이 올바르지 않습니다.")

    if not rows:
        raise ValueError("시트의 머리글을 찾을 수 없습니다.")

    # 첫 번째 행은 머리글이므로 제외
    votes = []

    for row in rows[1:]:
        if not isinstance(row, list) or len(row) < 4:
            raise ValueError("투표 기록의 형식이 올바르지 않습니다.")

        votes.append({
            "time": row[0],
            "nickname": row[1],
            "menu": row[2],
            "type": row[3]
        })

    return votes


# 투표 입력 화면
with st.form("lunch_vote"):
    nickname = st.text_input("닉네임을 입력하세요.")

    menu = st.selectbox(
        "먹고 싶은 메뉴를 선택하세요.",
        ["제육볶음", "스시", "수제버거", "파스타", "타코", "샐러드"]
    )

    submitted = st.form_submit_button("투표하기")

# 투표 버튼을 누르면 구글 시트에 저장
if submitted:
    if nickname.strip():
        try:
            saved = save_vote(nickname.strip(), menu)

            if saved:
                st.success("투표가 완료되었습니다!")
            else:
                st.error(
                    "투표를 저장하지 못했습니다. "
                    "잠시 후 다시 시도해 주세요."
                )

        except (requests.RequestException, ValueError):
            st.error(
                "투표 저장 중 문제가 발생했습니다. "
                "연결 상태를 확인한 뒤 다시 시도해 주세요."
            )
    else:
        st.warning("닉네임을 입력해 주세요.")


# 투표 목록 보여 주기
st.subheader("📋 투표 목록")

if st.button("🔄 결과 새로 읽기"):
    st.rerun()

try:
    votes = load_votes()

    if votes:
        for i, vote in enumerate(votes, start=1):
            st.write(
                f"{i}. {vote['nickname']}님 — {vote['menu']}"
            )
    else:
        st.info("아직 투표한 사람이 없습니다.")

except (requests.RequestException, ValueError):
    st.error(
        "투표 목록을 불러오지 못했습니다. "
        "잠시 후 '결과 새로 읽기' 버튼을 눌러 주세요."
    )
