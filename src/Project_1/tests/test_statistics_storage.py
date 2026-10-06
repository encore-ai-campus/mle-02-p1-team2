"""Storage 인증·원격 로딩·기존 결측 연도 처리의 회귀 검사."""
from io import BytesIO
import math
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pandas as pd

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
       + "\n".join(
           f"제조업,테스트업종{index or ''}," + ",".join("1" for _ in range(10))
           for index in range(30)
       ) + "\n").encode("utf-8-sig")


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

    def test_cp949_source_csv_loads_and_preserves_explicit_missing_cells(self):
        text = CSV.decode("utf-8-sig").replace(
            "제조업,테스트업종,1,1,", "제조업,테스트업종,자료 없음,1,", 1
        )
        source = BytesIO(text.encode("cp949"))
        data = statistics.load_stat_csv("사고재해자수", 2025, source)
        self.assertEqual(len(data), 300)
        self.assertEqual(data["산업중분류"].nunique(), 30)
        self.assertTrue(pd.isna(data.loc[data["산업중분류"] == "테스트업종", "값"].iloc[0]))

    def test_unexpected_text_in_statistic_cell_is_rejected(self):
        text = CSV.decode("utf-8-sig").replace(
            "제조업,테스트업종,1,1,", "제조업,테스트업종,값오류,1,", 1
        )
        with self.assertRaises(ValueError):
            statistics.load_stat_csv("사고재해자수", 2025, BytesIO(text.encode("utf-8-sig")))

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
             patch.object(statistics, "source_files") as local, \
             patch.object(statistics, "_load_statistics_from_postgres", return_value=None):
            with self.assertRaises(storage.StatisticsStorageError) as caught:
                statistics.load_statistics()
        local.assert_not_called()
        self.assertNotIn(KEY, str(caught.exception))
        self.assertIn("HTTP 404", str(caught.exception))

    def test_database_fallback_parses_2025_metrics_and_explicit_missing_values(self):
        documents = []
        labels = (
            "5인 미만", "5인 - 9인", "10인 - 19인", "20인 - 29인",
            "30인 - 49인", "50인 - 99인", "100인 - 299인",
            "300인 - 499인", "500인 - 999인", "1000인 이상",
        )
        for metric in statistics.METRICS:
            for index in range(30):
                if metric == "사망만인율":
                    value_labels = labels
                else:
                    suffix = "사업장수" if metric == "사업장수" else "근로자수"
                    value_labels = [f"{label} {suffix}" for label in labels]
                values = ["자료 없음" if metric == "사망만인율" and index == 0 and rank == 0
                          else str(index + rank) for rank in range(10)]
                content = "\n".join(
                    [f"지표: {metric}", f"대업종: 대분류{index % 3}", f"구분: 중분류{index}"]
                    + [f"{label}: {value}" for label, value in zip(value_labels, values)]
                )
                metadata = {
                    "metric": metric,
                    "industry": f"중분류{index}",
                    "sector": f"대분류{index % 3}",
                    "reference_date": statistics.POSTGRES_STAT_REFERENCE_DATE,
                }
                documents.append((f"stat:{metric}:{index}", content, metadata))

        data = statistics._statistics_from_documents(documents)
        self.assertEqual(len(data), 4 * 30 * 10)
        self.assertEqual(set(data["연도"]), {2025})
        self.assertEqual(data["산업중분류"].nunique(), 30)
        missing = data.loc[(data["지표"] == "사망만인율") & (data["산업중분류"] == "중분류0")
                           & (data["규모"] == "5인 미만"), "값"]
        self.assertTrue(missing.isna().all())

    def test_storage_failure_uses_database_fallback_when_available(self):
        fallback = pd.DataFrame({"연도": [2025], "대업종": ["대분류"],
                                 "산업중분류": ["중분류"], "규모": ["5인 미만"],
                                 "지표": ["사고사망자수"], "값": [1]})
        fallback.attrs["source_warning"] = "2025년 DB 자료"
        with patch.object(statistics, "download_csvs", side_effect=storage.StatisticsStorageError("HTTP 400")), \
             patch.object(statistics, "_load_statistics_from_postgres", return_value=fallback):
            data = statistics.load_statistics()
        self.assertEqual(set(data["연도"]), {2025})
        self.assertIn("DB 자료", data.attrs["source_warning"])

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
