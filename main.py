import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 화면 설정
# ==================================================

st.set_page_config(
    page_title="영화 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 영화 박스오피스")
st.caption("영화관입장권통합전산망(KOBIS) 일일 박스오피스")


# ==================================================
# 2. 한국 시간 설정
# ==================================================

KST = ZoneInfo("Asia/Seoul")

today = datetime.now(KST).date()

# 오늘은 아직 집계 전이므로 어제까지만 선택 가능
yesterday = today - timedelta(days=1)


# ==================================================
# 3. 날짜 선택
# ==================================================

st.subheader("📅 조회할 날짜")

selected_date = st.date_input(
    "박스오피스를 보고 싶은 날짜를 선택하세요.",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

target_date = selected_date.strftime("%Y%m%d")

display_date = selected_date.strftime("%Y년 %m월 %d일")


# ==================================================
# 4. KOBIS API
# ==================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Secrets에서 API 키 가져오기
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "empty": False,
            "error": f"API 요청에 실패했습니다.\n{e}"
        }

    except ValueError:

        return {
            "success": False,
            "empty": False,
            "error": "API가 올바른 데이터를 보내지 않았습니다."
        }


    # KOBIS API 오류 확인
    if "faultInfo" in data:

        fault = data["faultInfo"]

        return {
            "success": False,
            "empty": False,
            "error": (
                f"KOBIS API 오류\n"
                f"오류 코드: {fault.get('faultCode', '알 수 없음')}\n"
                f"오류 내용: {fault.get('message', '알 수 없음')}"
            )
        }


    # 박스오피스 결과 확인
    if "boxOfficeResult" not in data:

        return {
            "success": False,
            "empty": False,
            "error": "박스오피스 결과가 없습니다."
        }


    movie_list = data["boxOfficeResult"].get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 없는 경우
    if not movie_list:

        return {
            "success": False,
            "empty": True,
            "error": ""
        }


    return {
        "success": True,
        "empty": False,
        "movies": movie_list
    }


# ==================================================
# 5. API 실행
# ==================================================

result = get_boxoffice(target_date)


# ==================================================
# 6. 데이터가 없는 경우
# ==================================================

if result["empty"]:

    st.warning("📭 그날은 아직 집계 전입니다.")
    st.info("다른 날짜를 선택해 주세요.")

    st.stop()


# ==================================================
# 7. API 오류
# ==================================================

if not result["success"]:

    st.error("😥 박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(
        """
다음 내용을 확인해 주세요.

• Streamlit Secrets에 KOBIS_KEY가 등록되어 있는지 확인
• KOBIS API 인증키가 올바른지 확인
• 인터넷 연결 확인
• KOBIS API 서버 상태 확인
"""
    )

    st.code(result["error"])

    st.stop()


# ==================================================
# 8. DataFrame 만들기
# ==================================================

df = pd.DataFrame(result["movies"])


# ==================================================
# 9. 숫자 데이터 변환
# ==================================================

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0)


# 순위순으로 정렬
df = df.sort_values(
    "rank",
    ascending=True
).reset_index(drop=True)


# ==================================================
# 10. 선택한 날짜
# ==================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)


# ==================================================
# 11. 1위 영화
# ==================================================

first_movie = df.iloc[0]

first_movie_name = first_movie["movieNm"]

first_audience = int(
    first_movie["audiCnt"]
)

first_acc_audience = int(
    first_movie["audiAcc"]
)


# ==================================================
# 12. 1위 영화 카드
# ==================================================

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "🎬 영화",
        first_movie_name
    )


with col2:

    st.metric(
        "👥 해당 날짜 관객수",
        f"{first_audience:,}명"
    )


with col3:

    st.metric(
        "📊 누적 관객수",
        f"{first_acc_audience:,}명"
    )


# ==================================================
# 13. 관객수 상위 5편
# ==================================================

st.subheader("💗 관객수 상위 5편")

st.caption(
    "관객수가 많을수록 하트가 크게 표시됩니다."
)


top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 가장 많은 관객수
max_audience = int(
    top5["audiCnt"].max()
)

# 가장 적은 관객수
min_audience = int(
    top5["audiCnt"].min()
)


# ==================================================
# 14. 하트 표시
# ==================================================

for _, movie in top5.iterrows():

    movie_name = movie["movieNm"]

    audience = int(
        movie["audiCnt"]
    )


    # ----------------------------------------------
    # 관객수에 따라서 하트 크기 계산
    # ----------------------------------------------

    if max_audience == min_audience:

        heart_size = 70

    else:

        ratio = (
            (audience - min_audience)
            / (max_audience - min_audience)
        )

        heart_size = int(
            40 + ratio * 70
        )


    # ----------------------------------------------
    # 영화 이름
    # ----------------------------------------------

    st.write(f"🎬 **{movie_name}**")


    # ----------------------------------------------
    # 하트
    # ----------------------------------------------

    st.markdown(
        f"""
<span style="
font-size:{heart_size}px;
color:#FFC0CB;
">
♥
</span>
""",
        unsafe_allow_html=True
    )


    # ----------------------------------------------
    # 관객수
    # ----------------------------------------------

    st.caption(
        f"👥 {audience:,}명"
    )

    st.divider()


# ==================================================
# 15. 전체 박스오피스 표
# ==================================================

st.subheader("🎞️ 전체 박스오피스")


table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "rankInten",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# ==================================================
# 16. 누적관객 100만 명 초과 → 트로피
# ==================================================

def add_trophy(row):

    movie_name = str(
        row["movieNm"]
    )

    accumulated = int(
        row["audiAcc"]
    )

    if accumulated > 1_000_000:

        return f"🏆 {movie_name}"

    return movie_name


table_df["movieNm"] = table_df.apply(
    add_trophy,
    axis=1
)


# ==================================================
# 17. 순위 증감
# ==================================================

def make_rank_change(value):

    value = int(value)

    # 양수 → 순위 상승
    if value > 0:

        return f"🔴 ▲ {value}"

    # 음수 → 순위 하락
    elif value < 0:

        return f"🔵 ▼ {abs(value)}"

    # 변화 없음
    else:

        return "━"


table_df["rankInten"] = (
    table_df["rankInten"]
    .apply(make_rank_change)
)


# ==================================================
# 18. 표 이름 변경
# ==================================================

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "순위 증감",
    "관객수",
    "누적관객",
    "스크린수"
]


# ==================================================
# 19. 숫자에 쉼표
# ==================================================

table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{int(x):,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{int(x):,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{int(x):,}"
)


# ==================================================
# 20. 표 출력
# ==================================================

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 21. 출처
# ==================================================

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일일 박스오피스 API"
)
