
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client


# -----------------------------------
# 1. 기본 설정
# -----------------------------------
st.set_page_config(
    page_title="모두의 점심",
    page_icon="🍱"
)

st.title("🍱 모두의 점심")
st.write("오늘 점심으로 먹고 싶은 메뉴에 투표해 보세요!")

MENUS = [
    "제육볶음", "스시", "수제버거",
    "파스타", "타코", "샐러드"
]

KST = ZoneInfo("Asia/Seoul")
PAGE_SIZE = 500


# -----------------------------------
# 2. Supabase 연결
# -----------------------------------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
    return create_client(url, key)


try:
    supabase = get_supabase()
except Exception:
    st.error("Supabase 연결 설정을 확인해 주세요.")
    st.stop()


# -----------------------------------
# 3. 한국 날짜 계산
# -----------------------------------
def korea_now():
    return datetime.now(KST)


def utc_text(dt):
    return dt.astimezone(
        timezone.utc
    ).isoformat()


def date_range(start_date, end_date):
    """한국 날짜 범위를 UTC 시각으로 변환"""
    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=KST
    )

    end = datetime.combine(
        end_date,
        datetime.min.time(),
        tzinfo=KST
    )

    return utc_text(start), utc_text(end)


# -----------------------------------
# 4. 데이터 저장
# -----------------------------------
def save_record(name, menu, kind):
    result = (
        supabase.table("votes")
        .insert({
            "name": name,
            "menu": menu,
            "kind": kind
        })
        .execute()
    )

    # 데이터베이스가 반환한 저장 기록 확인
    if not result.data or len(result.data) != 1:
        raise ValueError(
            "저장된 기록을 확인하지 못했습니다."
        )

    saved = result.data[0]

    if (
        saved.get("name") != name
        or saved.get("menu") != menu
        or saved.get("kind") != kind
        or saved.get("id") is None
        or saved.get("created_at") is None
    ):
        raise ValueError(
            "저장 응답의 내용이 올바르지 않습니다."
        )

    return saved


# -----------------------------------
# 5. 데이터 조회
# -----------------------------------
def fetch_all(kind, start_date=None, end_date=None):
    """조건에 맞는 기록을 빠짐없이 나누어 읽기"""
    all_rows = []
    offset = 0

    while True:
        query = (
            supabase.table("votes")
            .select("id, created_at, name, menu, kind")
            .eq("kind", kind)
        )

        if start_date is not None and end_date is not None:
            start_utc, end_utc = date_range(
                start_date, end_date
            )

            query = (
                query
                .gte("created_at", start_utc)
                .lt("created_at", end_utc)
            )

        result = (
            query
            .order("created_at")
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        rows = result.data

        if rows is None:
            raise ValueError(
                "데이터 조회 응답이 올바르지 않습니다."
            )

        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return all_rows


def load_today_votes():
    today = korea_now().date()

    return fetch_all(
        "희망 메뉴",
        today,
        today + timedelta(days=1)
    )


def load_recent_meals():
    today = korea_now().date()

    # 오늘 제외, 이전 7일
    return fetch_all(
        "식사 완료",
        today - timedelta(days=7),
        today
    )


# -----------------------------------
# 6. 투표 집계
# -----------------------------------
def calculate_votes(rows):
    # 닉네임별 마지막 투표만 남기기
    latest = {}

    for row in rows:
        name = row["name"]

        if name not in latest:
            latest[name] = row
        else:
            old = latest[name]

            # created_at이 같으면 id가 큰 기록 선택
            if (
                row["created_at"], row["id"]
            ) > (
                old["created_at"], old["id"]
            ):
                latest[name] = row

    counts = {menu: 0 for menu in MENUS}

    for row in latest.values():
        if row["menu"] in counts:
            counts[row["menu"]] += 1

    return latest, counts


# -----------------------------------
# 7. 식사 기록 집계
# -----------------------------------
def calculate_meals(rows):
    # 한국 날짜와 메뉴가 같으면 한 번만 계산
    unique_meals = {}

    for row in rows:
        dt = datetime.fromisoformat(
            row["created_at"].replace("Z", "+00:00")
        ).astimezone(KST)

        day = dt.date()
        key = (day, row["menu"])

        if key not in unique_meals:
            unique_meals[key] = {
                "날짜": day,
                "메뉴": row["menu"]
            }

    return sorted(
        unique_meals.values(),
        key=lambda x: (x["날짜"], x["메뉴"]),
        reverse=True
    )


def error_message(error):
    """오류 내용에서 API 키나 연결 주소를 제외"""
    message = getattr(error, "message", None)

    if message:
        return str(message)

    if isinstance(error, ValueError):
        return str(error)

    return "데이터베이스 요청 중 오류가 발생했습니다."


def is_duplicate_error(error):
    # PostgreSQL 고유 제약 위반 코드
    return str(getattr(error, "code", "")) == "23505"


# -----------------------------------
# 8. 투표 입력 화면
# -----------------------------------
if st.session_state.pop("saved_message", None):
    st.success("저장이 완료되었습니다!")

with st.form("lunch_vote"):
    nickname = st.text_input(
        "닉네임을 입력하세요.",
        key="nickname"
    )

    menu = st.selectbox(
        "먹고 싶은 메뉴를 선택하세요.",
        MENUS,
        key="selected_menu"
    )

    submitted = st.form_submit_button("투표하기")


if submitted:
    if not nickname.strip():
        st.warning("닉네임을 입력해 주세요.")
    else:
        try:
            save_record(
                nickname.strip(),
                menu,
                "희망 메뉴"
            )

            st.session_state["saved_message"] = True
            st.rerun()

        except Exception as error:
            st.error(
                "투표 저장 실패: "
                + error_message(error)
            )


# -----------------------------------
# 9. 식사 완료 기록
# -----------------------------------
st.divider()
st.subheader("🍽️ 식사 완료 기록")

st.write(
    "실제로 먹은 메뉴를 선택하고 "
    "식사 완료 버튼을 눌러 주세요."
)

meal_menu = st.selectbox(
    "먹은 메뉴",
    MENUS,
    key="meal_menu"
)

if st.button("식사 완료"):
    try:
        save_record(
            "전체",
            meal_menu,
            "식사 완료"
        )

        st.session_state["saved_message"] = True
        st.rerun()

    except Exception as error:
        if is_duplicate_error(error):
            st.warning("이미 기록한 식사입니다")
        else:
            st.error(
                "식사 기록 저장 실패: "
                + error_message(error)
            )


# -----------------------------------
# 10. 결과 영역
# -----------------------------------
@st.fragment(run_every="10s")
def show_results():
    st.divider()
    st.subheader("📊 오늘의 투표 결과")

    if st.button("🔄 결과 새로 읽기"):
        pass

    try:
        # 매번 Supabase에서 최신 기록 조회
        vote_rows = load_today_votes()
        meal_rows = load_recent_meals()

        latest, counts = calculate_votes(vote_rows)
        meals = calculate_meals(meal_rows)

        read_time = korea_now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        st.caption(
            f"마지막으로 읽은 시각: {read_time} (한국 시간)"
        )

    except Exception as error:
        st.error(
            "결과를 불러오지 못했습니다: "
            + error_message(error)
        )
        return

    # 오늘의 투표 결과
    if not latest:
        st.info("아직 투표가 없습니다")
    else:
        st.metric(
            "투표한 사람 수",
            f"{len(latest)}명"
        )

    result_df = pd.DataFrame({
        "메뉴": MENUS,
        "득표 수": [counts[m] for m in MENUS]
    })

    st.subheader("메뉴별 득표 수")
    st.dataframe(
        result_df,
        hide_index=True,
        use_container_width=True
    )

    fig = px.bar(
        result_df,
        x="메뉴",
        y="득표 수",
        text="득표 수",
        title="오늘의 메뉴별 투표 결과"
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        yaxis=dict(
            range=[0, max(counts.values()) + 1],
            dtick=1
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    if latest:
        max_votes = max(counts.values())

        winners = [
            menu for menu, count in counts.items()
            if count == max_votes
        ]

        st.subheader("🏆 오늘의 1위 메뉴")
        st.success(
            f"{', '.join(winners)} "
            f"({max_votes}표)"
        )

    # 지난 7일의 식사 기록
    st.divider()
    st.subheader("📅 지난 7일 식사 기록")
    st.caption("오늘을 제외한 최근 7일의 기록입니다.")

    if meals:
        meal_df = pd.DataFrame(meals)
        meal_df["날짜"] = meal_df["날짜"].astype(str)

        st.dataframe(
            meal_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("지난 7일간 식사 기록이 없습니다.")

    # 선택한 메뉴의 마지막 식사 날짜
    st.subheader("🔎 최근에 먹은 메뉴 확인")

    selected = st.selectbox(
        "확인할 메뉴를 선택하세요.",
        MENUS,
        key="check_menu"
    )

    matched = [
        meal["날짜"]
        for meal in meals
        if meal["메뉴"] == selected
    ]

    if matched:
        last_day = max(matched)

        st.info(
            f"{selected}의 마지막 식사 날짜는 "
            f"{last_day:%Y년 %m월 %d일}입니다."
        )
    else:
        st.write(
            f"지난 7일 동안 {selected}을(를) "
            "먹은 기록이 없습니다."
        )


show_results()
