"""Storage 인증·원격 로딩·기존 결측 연도 처리의 회귀 검사."""
from io import BytesIO
import math
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from services import statistics
from services import statistics_storage as storage
from services.visualization import plot_six_year_line

KEY = "sb_secret_unit_test_only"
CONFIG = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": KEY,
    "SUPABASE_STORAGE_BUCKET": "industrial-statistics",
}
CSV = ("대업종,구분," + ",".join(str(i) for i in range(10)) + "\n"
       + "제조업,테스트업종," + ",".join("1" for _ in range(10)) + "\n").encode("utf-8-sig")


class StorageStatisticsTests(unittest.TestCase):
    def test_remote_data_does_not_use_local_files_and_preserves_gap(self):
        payload = {key: CSV for key in statistics.storage_files()}
        with patch.object(statistics, "download_csvs", return_value=payload), \
             patch.object(statistics, "source_files", side_effect=AssertionError("local files used")):
            data = statistics.load_statistics()
        self.assertEqual(set(data["연도"]), set(range(2020, 2026)))
        trend = statistics.industry_trend(data, "테스트업종", "사망만인율")
        self.assertTrue(math.isnan(trend.loc[trend["연도"] == 2021, "값"].iloc[0]))
        self.assertEqual(trend.loc[trend["연도"] == 2020, "값"].iloc[0], 1)
        self.assertIsNone(statistics.kpi_value(data, 2021, "테스트업종", "5인 미만", "사망만인율"))
        fig = plot_six_year_line(trend, "테스트업종", "사망만인율", 2025, None)
        self.assertFalse(fig.data[0].connectgaps)

    def test_explicit_local_directory_keeps_existing_loader(self):
        with patch.object(statistics, "download_csvs") as remote, \
             patch.object(statistics, "source_files", return_value={("사고사망자수", 2025): BytesIO(CSV)}):
            data = statistics.load_statistics(statistics.DATA_DIR)
        remote.assert_not_called()
        self.assertEqual(statistics.kpi_value(data, 2025, "테스트업종", None, "사고사망자수"), 10)

    def test_cloud_secrets_take_precedence_over_environment(self):
        with patch.dict(os.environ, {"SUPABASE_SECRET_KEY": "local_value"}), \
             patch.object(storage.st, "secrets", {"SUPABASE_SECRET_KEY": KEY}):
            self.assertEqual(storage._setting("SUPABASE_SECRET_KEY"), KEY)

    def test_absent_storage_settings_allow_local_mode(self):
        with patch.object(storage, "_setting", return_value=None), \
             patch.object(storage, "build_opener") as opener:
            self.assertIsNone(storage.download_csvs(statistics.storage_files()))
        opener.assert_not_called()

    def test_download_failure_is_not_missing_data_or_local_fallback(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("https://example.supabase.co/file", 404, "missing", {}, None)
        with patch.object(storage, "_setting", side_effect=CONFIG.get), \
             patch.object(storage, "build_opener", return_value=opener), \
             patch.object(statistics, "source_files") as local:
            with self.assertRaises(storage.StatisticsStorageError) as caught:
                statistics.load_statistics()
        local.assert_not_called()
        self.assertNotIn(KEY, str(caught.exception))
        self.assertIn("HTTP 404", str(caught.exception))

    def test_external_host_rejected_before_sending_key(self):
        config = {**CONFIG, "SUPABASE_URL": "https://example.com"}
        with patch.object(storage, "_setting", side_effect=config.get), \
             patch.object(storage, "build_opener") as opener:
            with self.assertRaises(storage.StatisticsStorageError):
                storage.download_csvs(statistics.storage_files())
        opener.assert_not_called()

    def test_invalid_remote_csv_still_rejected_by_existing_validation(self):
        with patch.object(statistics, "download_csvs", return_value={("사고사망자수", 2025): b"wrong,columns\n1,2\n"}):
            with self.assertRaises(ValueError):
                statistics.load_statistics()


if __name__ == "__main__":
    unittest.main()
