import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 화면 기본 설정
# ==================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 영화 박스오피스 조회")
st.caption("영화관입장권통합전산망(KOBIS) 일일 박스오피스")


# ==================================================
# 2. 한국 시간 설정
# ==================================================

# Streamlit Cloud 서버 시간이 한국 시간이 아닐 수 있으므로
# 서울 시간을 기준으로 날짜를 계산합니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

today = now_kst.date()

# 오늘은 아직 집계가 끝나지 않았으므로
# 선택할 수 있는 가장 최근 날짜는 어제입니다.

yesterday = today - timedelta(days=1)


# ==================================================
# 3. 날짜 선택
# ==================================================

st.subheader("📅 조회할 날짜를 선택하세요")

selected_date = st.date_input(
    "날짜",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)


# KOBIS API가 사용하는 날짜 형식
target_date = selected_date.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# ==================================================
# 4. KOBIS API에서 데이터 가져오기
# ==================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Secrets에 저장된 KOBIS API 키
    api_key = st.secrets["KOBIS_KEY"]

    # KOBIS 일일 박스오피스 API 주소
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
            "error": f"API 요청에 실패했습니다.\n{e}"
        }

    except ValueError:

        return {
            "success": False,
            "error": "API가 올바른 JSON 데이터를 보내지 않았습니다."
        }


    # ==================================================
    # 5. KOBIS API 오류 확인
    # ==================================================

    if "faultInfo" in data:

        fault = data["faultInfo"]

        fault_code = fault.get(
            "faultCode",
            "알 수 없음"
        )

        fault_message = fault.get(
            "message",
            "알 수 없는 오류"
        )

        return {
            "success": False,
            "error": (
                "KOBIS API 오류가 발생했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}"
            )
        }


    # ==================================================
    # 6. 박스오피스 결과 확인
    # ==================================================

    if "boxOfficeResult" not in data:

        return {
            "success": False,
            "error": "API 응답에 boxOfficeResult가 없습니다."
        }


    movie_list = data["boxOfficeResult"].get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있으면
    # 아직 해당 날짜의 데이터가 집계되지 않은 것으로 안내합니다.

    if not movie_list:

        return {
            "success": False,
            "empty": True
        }


    return {
        "success": True,
        "movies": movie_list
    }


# ==================================================
# 7. API 실행
# ==================================================

result = get_boxoffice(target_date)


# ==================================================
# 8. 데이터가 없는 경우
# ==================================================

if result.get("empty", False):

    st.warning(
        "📭 그날은 아직 집계 전입니다."
    )

    st.info(
        "다른 날짜를 선택해 주세요."
    )

    st.stop()


# ==================================================
# 9. API 오류가 발생한 경우
# ==================================================

if not result["success"]:

    st.error(
        "😥 박스오피스 데이터를 가져오지 못했습니다."
    )

    st.warning(
        """
다음 내용을 확인해 주세요.

1. Streamlit Secrets에 `KOBIS_KEY`가 등록되어 있는지 확인
2. KOBIS 인증키가 올바른지 확인
3. KOBIS API 서버가 정상적으로 작동하는지 확인
4. API 요청 제한이나 인터넷 연결에 문제가 없는지 확인
"""
    )

    st.code(result["error"])

    st.stop()


# ==================================================
# 10. DataFrame 만들기
# ==================================================

movies = result["movies"]

df = pd.DataFrame(movies)


# ==================================================
# 11. 숫자 데이터 변환
# ==================================================

# KOBIS API에서는 숫자도 문자열 형태로 보내기 때문에
# 실제 숫자로 변환합니다.

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


# ==================================================
# 12. 순위 기준 정렬
# ==================================================

df = df.sort_values(
    "rank",
    ascending=True
).reset_index(drop=True)


# ==================================================
# 13. 선택한 날짜 표시
# ==================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.info(
    f"{display_date}의 일일 박스오피스 데이터입니다."
)


# ==================================================
# 14. 1위 영화 정보
# ==================================================

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]

audience = int(
    first_movie["audiCnt"]
)

acc_audience = int(
    first_movie["audiAcc"]
)


# ==================================================
# 15. 1위 영화 지표 카드
# ==================================================

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "🎬 영화",
        movie_name
    )


with col2:

    st.metric(
        "👥 해당 날짜 관객수",
        f"{audience:,}명"
    )


with col3:

    st.metric(
        "📊 누적 관객수",
        f"{acc_audience:,}명"
    )


# ==================================================
# 16. 관객수 상위 5편 하트 그래프
# ==================================================

st.subheader("💗 관객수 상위 5편")

st.caption(
    "관객수가 많을수록 하트가 크게 표시됩니다."
)


# 관객수가 많은 순서대로 5편 선택

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 하트 크기 설정

MIN_SIZE = 35
MAX_SIZE = 110

max_audience = top5["audiCnt"].max()
min_audience = top5["audiCnt"].min()


# 상위 5편을 하나씩 표시

for _, movie in top5.iterrows():

    movie_name_chart = movie["movieNm"]

    movie_audience = int(
        movie["audiCnt"]
    )


    # --------------------------------------------------
    # 관객수에 따라 하트 크기 계산
    # --------------------------------------------------

    if max_audience == min_audience:

        heart_size = 70

    else:

        heart_size = (
            MIN_SIZE
            + (
                (movie_audience - min_audience)
                / (max_audience - min_audience)
            )
            * (MAX_SIZE - MIN_SIZE)
        )


    # --------------------------------------------------
    # 하트 표시
    # --------------------------------------------------

    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 20px;
            margin: 15px 0;
            padding: 12px;
            border-radius: 15px;
            background-color: #FFF7FA;
        ">

            <div style="
                width: 220px;
                font-size: 18px;
                font-weight: bold;
            ">
                🎬 {movie_name_chart}
            </div>

            <div style="
                font-size: {heart_size}px;
                line-height: 1;
                color: #FFC0CB;
                text-shadow: 1px 1px 2px #F5A9B8;
            ">
                ♥
            </div>

            <div style="
                font-size: 16px;
                color: #555555;
            ">
                {movie_audience:,}명
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


# ==================================================
# 17. 전체 박스오피스 표
# ==================================================

st.subheader("🎞️ 전체 박스오피스")


# 표에 사용할 데이터 복사

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
# 18. 영화명에 트로피 붙이기
# ==================================================

# 누적관객이 100만 명을 넘은 영화는
# 영화명 옆에 트로피를 붙입니다.

def make_movie_name(row):

    name = row["movieNm"]

    accumulated = int(
        row["audiAcc"]
    )

    if accumulated > 1_000_000:

        return f"🏆 {name}"

    return name


table_df["movieNm"] = table_df.apply(
    make_movie_name,
    axis=1
)


# ==================================================
# 19. 순위 증감 표시
# ==================================================

def make_rank_change(value):

    value = int(value)

    # 양수 = 순위 상승
    if value > 0:

        return f"🔴 ▲ {value}"

    # 음수 = 순위 하락
    elif value < 0:

        return f"🔵 ▼ {abs(value)}"

    # 0 = 순위 변화 없음
    else:

        return "━"


table_df["rankInten"] = table_df["rankInten"].apply(
    make_rank_change
)


# ==================================================
# 20. 표 컬럼 이름 변경
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
# 21. 숫자에 천 단위 쉼표 넣기
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
# 22. 표 출력
# ==================================================

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 23. 데이터 출처
# ==================================================

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일일 박스오피스 API"
)
