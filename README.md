# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

# 브라우저 탭의 제목과 화면 아이콘을 설정합니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# KOBIS 일별 박스오피스 API 주소입니다.
KOBIS_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 한국 시간대를 사용합니다.
# 배포 서버가 한국 시간이 아니어도 정확하게 '어제'를 계산할 수 있습니다.
KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------
# 날짜 계산
# ---------------------------------------------------------

def get_yesterday():
    """한국 시간 기준으로 어제 날짜를 yyyymmdd 형식으로 반환합니다."""

    # 현재 시각을 한국 시간으로 가져옵니다.
    now_kst = datetime.now(KST)

    # 하루를 빼서 어제를 구합니다.
    yesterday = now_kst - timedelta(days=1)

    # KOBIS가 요구하는 8자리 날짜 형식으로 바꿉니다.
    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# 숫자 변환
# ---------------------------------------------------------

def to_int(value):
    """API에서 문자열로 온 숫자를 정수로 변환합니다."""

    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        # 숫자로 바꿀 수 없는 값이 들어오면 0으로 처리합니다.
        return 0


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_dt):
    """
    특정 날짜의 박스오피스를 가져옵니다.

    cache_data의 ttl=3600은 약 1시간입니다.
    같은 날짜를 다시 조회하면 1시간 동안 API를 다시 호출하지 않습니다.
    """

    # 인증키는 Streamlit Cloud의 Secrets에서 가져옵니다.
    # 코드에 실제 인증키를 적지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        raise RuntimeError(
            "KOBIS_KEY가 없습니다. "
            "Streamlit Cloud의 앱 설정에서 Secrets에 "
            "KOBIS_KEY를 등록했는지 확인하세요."
        )

    # KOBIS API에 보낼 요청값입니다.
    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        response = requests.get(
            KOBIS_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류(예: 500 등)가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

    except requests.RequestException as e:
        raise RuntimeError(
            "KOBIS API에 접속하지 못했습니다. "
            f"인터넷 연결이나 KOBIS API 상태를 확인하세요.\n\n{e}"
        )

    # JSON으로 변환합니다.
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다. "
            "잠시 후 다시 시도해 보세요."
        )

    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 따로 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # 오류 내용을 최대한 알기 쉽게 가져옵니다.
        fault_text = str(fault_info)

        raise RuntimeError(
            "KOBIS API에서 오류(faultInfo)를 반환했습니다.\n\n"
            f"{fault_text}\n\n"
            "특히 Streamlit Secrets의 KOBIS_KEY가 정확한지 확인하세요."
        )

    # 정상 응답이라면 boxOfficeResult가 있어야 합니다.
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        raise RuntimeError(
            "KOBIS 응답에 boxOfficeResult가 없습니다. "
            "KOBIS API 응답 형식이나 서비스 상태를 확인하세요."
        )

    # 영화 목록을 가져옵니다.
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 목록이 비어 있으면 사용자에게 확인할 내용을 안내합니다.
    if not movie_list:
        raise RuntimeError(
            "해당 날짜의 영화 목록이 비어 있습니다.\n\n"
            "KOBIS에서 해당 날짜의 박스오피스가 집계되었는지, "
            "조회 날짜가 올바른지, API 서비스 상태를 확인하세요."
        )

    # 화면에서 사용하기 편하도록 필요한 값만 정리합니다.
    result = []

    for movie in movie_list:
        result.append(
            {
                "순위": to_int(movie.get("rank")),
                "영화명": movie.get("movieNm", ""),
                "개봉일": movie.get("openDt", ""),
                "관객수": to_int(movie.get("audiCnt")),
                "누적관객": to_int(movie.get("audiAcc")),
                "스크린수": to_int(movie.get("scrnCnt")),
            }
        )

    return result


# ---------------------------------------------------------
# 화면 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")

# 한국 시간 기준으로 어제 날짜를 계산합니다.
yesterday = get_yesterday()

# 사용자에게 조회 기준 날짜를 보여 줍니다.
display_date = datetime.strptime(yesterday, "%Y%m%d").strftime("%Y년 %m월 %d일")

st.caption(f"한국 시간 기준 {display_date} 박스오피스")


# ---------------------------------------------------------
# 데이터 가져오기
# ---------------------------------------------------------

try:
    movies = get_box_office(yesterday)

except Exception as e:
    # API 요청 실패나 설정 오류가 발생하면 빈 화면 대신 안내합니다.
    st.error("박스오피스를 불러오지 못했습니다.")

    st.warning(str(e))

    st.info(
        "확인할 항목:\n"
        "1. Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "2. KOBIS 인증키가 정확하고 아직 유효한지\n"
        "3. KOBIS API가 정상적으로 서비스되고 있는지\n"
        "4. 해당 날짜의 일별 박스오피스가 집계되었는지"
    )

    st.stop()


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

# 순위가 가장 높은 영화를 가져옵니다.
# API 응답이 이미 순위순이지만, 숫자로 변환한 순위를 기준으로 한 번 더 정렬합니다.
movies = sorted(movies, key=lambda movie: movie["순위"])

first_movie = movies[0]


st.subheader("🏆 1위 영화")

# 1위 영화의 핵심 지표 3개를 크게 보여 줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘의 관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )

st.markdown(f"### 🎥 {first_movie['영화명']}")
st.caption(f"개봉일: {first_movie['개봉일'] or '정보 없음'}")


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬합니다.
top_5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart는 숫자 열을 그래프로 만들 수 있습니다.
# 영화명을 인덱스로 사용하기 위해 별도의 딕셔너리를 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top_5
}

st.bar_chart(chart_data, horizontal=True)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 표에 표시할 열 순서를 명시합니다.
table_data = [
    {
        "순위": movie["순위"],
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": movie["관객수"],
        "누적관객": movie["누적관객"],
        "스크린수": movie["스크린수"],
    }
    for movie in movies
]

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개",
    
