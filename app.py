"""시작점(라우터) — 실행: streamlit run app.py

파일명은 영문(Windows·Git 한글 깨짐 방지), 화면 메뉴 이름만 한글로 표시합니다.
"""
import streamlit as st

st.set_page_config(page_title="AI 말하기 코치", page_icon="🎙️", layout="wide")

pg = st.navigation([
    st.Page("pages/home.py", title="연습 홈", icon="🎙️", default=True),
    st.Page("pages/result.py", title="결과", icon="📝"),
    st.Page("pages/history.py", title="이력", icon="📈"),
    st.Page("pages/dashboard.py", title="대시보드", icon="📊"),
])
pg.run()
