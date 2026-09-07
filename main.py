```python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화관입장권통합전산망(KOBIS) 일일 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 구하기
# --------------------------------------------------
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 기준으로 계산합니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 원하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API에서 데이터 가져오기
# --------------------------------------------------
# cache_data를 사용하면 같은 날짜에 API를 계속 호출하지 않습니다.
# 3600초 = 약 1시간 동안 결과를 기억합니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 절대 적지 않습니다.
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

        # HTTP 오류가 있으면 예외 발생
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

    # --------------------------------------------------
    # 4. KOBIS가 faultInfo를 보내는 경우
    # --------------------------------------------------
    # 인증키가 틀려도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 직접 확인해야 합니다.

    if "faultInfo" in data:
        fault = data["faultInfo"]

        fault_code = fault.get("faultCode", "알 수 없음")
        fault_message = fault.get("message", "알 수 없는 오류")

        return {
            "success": False,
            "error": (
                f"KOBIS API 오류가 발생했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}"
            )
        }

    # 정상적인 응답인지 확인
    if "boxOfficeResult" not in data:
        return {
            "success": False,
            "error": "API 응답에 boxOfficeResult가 없습니다."
        }

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

    return {
        "success": True,
        "movies": movie_list
    }


# --------------------------------------------------
# 5. API 호출
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 6. 오류가 발생했을 때 안내
# --------------------------------------------------

if not result["success"]:

    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(
        "다음 내용을 확인해 주세요.\n\n"
        "1. Streamlit Secrets에 `KOBIS_KEY`가 정확히 등록되어 있는지 확인\n"
        "2. KOBIS 인증키가 유효한지 확인\n"
        "3. KOBIS API 서버가 정상적으로 응답하는지 확인\n"
        "4. 조회 날짜에 실제 박스오피스 데이터가 존재하는지 확인\n"
        "5. 인터넷 연결 또는 API 요청 제한에 문제가 없는지 확인"
    )

    st.code(result["error"])

    st.stop()


movies = result["movies"]


# --------------------------------------------------
# 7. 데이터를 표에 사용하기 좋게 변환
# --------------------------------------------------

df = pd.DataFrame(movies)


# KOBIS에서 숫자가 문자열로 오기 때문에
# 숫자 컬럼을 실제 숫자 자료형으로 변환합니다.

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


# --------------------------------------------------
# 8. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.info(
    f"한국 시간 기준 어제({display_date})의 "
    "KOBIS 일일 박스오피스 데이터입니다."
)


# --------------------------------------------------
# 9. 1위 영화 정보
# --------------------------------------------------

# 순위가 가장 낮은 영화가 1위이므로 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]
audience = int(first_movie["audiCnt"])
acc_audience = int(first_movie["audiAcc"])
screen_count = int(first_movie["scrnCnt"])


st.subheader("🏆 1위 영화")


# 지표 카드 3개
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


# --------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 인덱스로 사용하면 Streamlit이
# 영화별 막대그래프로 보여줍니다.
top5_chart = top5.set_index("movieNm")["audiCnt"]

st.bar_chart(top5_chart)


# --------------------------------------------------
# 11. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 화면에 표시할 컬럼만 선택합니다.
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


# 컬럼 이름을 한국어로 바꿉니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자를 보기 편하게 천 단위 쉼표로 표시합니다.
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{int(x):,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{int(x):,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{int(x):,}"
)


# 표 출력
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 12. 마지막 안내
# --------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일일 박스오피스 API"
)
```
