import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 화면 기본 설정
# ==================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화관입장권통합전산망(KOBIS) 일일 박스오피스")


# ==================================================
# 2. 한국 시간 기준으로 '어제' 날짜 계산하기
# ==================================================

# Streamlit Cloud 서버가 한국 시간이 아닐 수도 있기 때문에
# 한국 시간(서울)을 기준으로 날짜를 계산합니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘에서 하루를 빼면 '어제'입니다.
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 원하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ==================================================
# 3. KOBIS API에서 박스오피스 가져오기
# ==================================================

# 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용합니다.
# 따라서 API를 계속 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # 인증키는 Streamlit Secrets에서 가져옵니다.
    # 실제 인증키를 코드에 직접 쓰지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 보낼 정보
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # ----------------------------------------------
    # API 요청
    # ----------------------------------------------

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인합니다.
        response.raise_for_status()

        # JSON으로 변환합니다.
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
    # 4. KOBIS의 faultInfo 오류 확인
    # ==================================================

    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 그래서 faultInfo가 있는지 따로 확인해야 합니다.

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
    # 5. 정상적인 응답인지 확인
    # ==================================================

    if "boxOfficeResult" not in data:

        return {
            "success": False,
            "error": "API 응답에 boxOfficeResult가 없습니다."
        }


    # 영화 목록 가져오기
    movie_list = data["boxOfficeResult"].get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있는 경우
    if not movie_list:

        return {
            "success": False,
            "error": "해당 날짜의 영화 목록이 비어 있습니다."
        }


    # 정상적으로 가져온 경우
    return {
        "success": True,
        "movies": movie_list
    }


# ==================================================
# 6. API 실행
# ==================================================

result = get_boxoffice(target_date)


# ==================================================
# 7. 오류가 발생했을 때 안내하기
# ==================================================

if not result["success"]:

    st.error("😥 박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(
        """
다음 내용을 확인해 주세요.

1. Streamlit Secrets에 `KOBIS_KEY`가 정확하게 등록되어 있는지 확인
2. KOBIS 인증키가 올바른지 확인
3. KOBIS API 서버가 정상적으로 작동하는지 확인
4. 조회 날짜에 박스오피스 데이터가 존재하는지 확인
5. API 요청 제한이나 인터넷 연결에 문제가 없는지 확인
"""
    )

    # 개발자가 오류 원인을 확인할 수 있도록 표시
    st.code(result["error"])

    # 아래 코드는 실행하지 않고 멈춥니다.
    st.stop()


# ==================================================
# 8. 데이터를 DataFrame으로 만들기
# ==================================================

movies = result["movies"]

df = pd.DataFrame(movies)


# ==================================================
# 9. 숫자 데이터를 실제 숫자로 변환하기
# ==================================================

# KOBIS에서는 숫자도 문자열로 보내기 때문에
# 그래프와 정렬에 사용할 수 있도록 숫자로 변환합니다.

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
# 10. 순위 순서대로 정렬
# ==================================================

df = df.sort_values(
    "rank",
    ascending=True
).reset_index(drop=True)


# ==================================================
# 11. 조회 날짜 표시
# ==================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.info(
    f"한국 시간 기준 어제인 {display_date}의 "
    "KOBIS 일일 박스오피스입니다."
)


# ==================================================
# 12. 1위 영화 찾기
# ==================================================

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]

audience = int(
    first_movie["audiCnt"]
)

acc_audience = int(
    first_movie["audiAcc"]
)

screen_count = int(
    first_movie["scrnCnt"]
)


# ==================================================
# 13. 1위 영화 지표 카드 3개
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
        "👥 어제 관객수",
        f"{audience:,}명"
    )


with col3:

    st.metric(
        "📊 누적 관객수",
        f"{acc_audience:,}명"
    )


# ==================================================
# 14. 관객수 상위 5편 그래프
# ==================================================

st.subheader("📊 관객수 상위 5편")


# 관객수가 많은 순서대로 정렬합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 그래프에서도 관객수가 많은 순서가
# 확실하게 보이도록 다시 정렬합니다.
top5 = top5.sort_values(
    "audiCnt",
    ascending=True
)


# 영화명을 세로축으로 사용하고
# 관객수를 가로축으로 사용합니다.
top5_chart = top5.set_index(
    "movieNm"
)["audiCnt"]


# 노란색 그래프!
# #FFD700 = 금색에 가까운 밝은 노란색
st.bar_chart(
    top5_chart,
    horizontal=True,
    color="#FFD700"
)


# ==================================================
# 15. 전체 박스오피스 표
# ==================================================

st.subheader("🎞️ 전체 박스오피스")


# 필요한 데이터만 골라냅니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 표의 제목을 한국어로 변경합니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자에 천 단위 쉼표를 넣습니다.
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{int(x):,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{int(x):,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{int(x):,}"
)


# 표 보여주기
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 16. 데이터 출처
# ==================================================

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일일 박스오피스 API"
)
