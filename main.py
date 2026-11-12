
import streamlit as st

st.set_page_config(page_title="모두의 점심", page_icon="🍱")

st.title("🍱 모두의 점심")
st.write("오늘 점심으로 먹고 싶은 메뉴에 투표해 보세요!")

# 투표 목록을 저장할 세션 상태 만들기
if "votes" not in st.session_state:
    st.session_state.votes = []

# 투표 입력 화면
with st.form("lunch_vote"):
    nickname = st.text_input("닉네임을 입력하세요.")

    menu = st.selectbox(
        "먹고 싶은 메뉴를 선택하세요.",
        ["제육볶음", "스시", "수제버거", "파스타", "타코", "샐러드"]
    )

    submitted = st.form_submit_button("투표하기")

# 투표 버튼을 누르면 목록에 추가
if submitted:
    if nickname.strip():
        st.session_state.votes.append({
            "nickname": nickname.strip(),
            "menu": menu
        })
        st.success("투표가 완료되었습니다!")
    else:
        st.warning("닉네임을 입력해 주세요.")

# 투표 목록 보여 주기
st.subheader("📋 투표 목록")

if st.session_state.votes:
    for i, vote in enumerate(st.session_state.votes, start=1):
        st.write(
            f"{i}. {vote['nickname']}님 — {vote['menu']}"
        )
else:
    st.info("아직 투표한 사람이 없습니다.")
