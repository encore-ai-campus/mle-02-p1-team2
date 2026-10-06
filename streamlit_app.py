"""Unified Streamlit entry point for the safety assistant and retrieval inspector."""

from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
# The chat page keeps its existing local service imports (`services.*`).
PROJECT_1_ROOT = PROJECT_ROOT / "src" / "Project_1"
for import_root in (str(PROJECT_ROOT), str(PROJECT_1_ROOT)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)

chat_page = st.Page(
    "src/Project_1/app.py",
    title="작업 안전 상담",
    icon="🦺",
    default=True,
)
search_page = st.Page(
    "streamlit_search_page.py",
    title="사례 직접 검색",
    icon="🔎",
)

navigation = st.navigation(
    {
        "산업안전 지원": [chat_page],
        "검색 확인": [search_page],
    },
    position="sidebar",
)
navigation.run()
