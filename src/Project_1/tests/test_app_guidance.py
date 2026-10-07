"""Regression checks for safety guidance kept visible in the active Streamlit app."""

import unittest
from pathlib import Path


APP_SOURCE = Path(__file__).resolve().parents[1] / "app.py"


class AppGuidanceTests(unittest.TestCase):
    def test_active_safety_tab_shows_worksite_caution(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            'st.info("답변은 검색된 사고사례와 안전자료를 바탕으로 한 참고용입니다.',
            source,
        )

    def test_active_app_surfaces_statistics_source_warning(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        self.assertIn('if data.attrs.get("source_warning"):', source)
        self.assertIn('st.warning(data.attrs["source_warning"])', source)


if __name__ == "__main__":
    unittest.main()
