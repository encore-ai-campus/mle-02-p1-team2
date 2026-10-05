import unittest

from src.sif_rag.retrieval_tool import search_sif_cases, tool_schema


def case(case_id, *, url="https://www.data.go.kr/data/15161362/openapi.do", industry="Construction", text="forklift pedestrian collision"):
    return {
        "case_id": case_id,
        "source_url": url,
        "page_content": text,
        "fields": {
            "sifLclsfNm": industry,
            "disasterOverview": text,
            "orgtNm": "forklift",
            "situation": "vehicle movement",
            "disasterFactor": "pedestrian in route",
            "dcrsCntrplnCn": "separate pedestrian route",
        },
    }


class SearchSifCasesTests(unittest.TestCase):
    def test_returns_ranked_evidence_with_valid_citation(self):
        result = search_sif_cases("forklift pedestrian collision", [case("SIF-1")])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"][0]["case_id"], "SIF-1")
        self.assertTrue(result["results"][0]["citation"]["validated"])
        self.assertEqual(result["results"][0]["evidence"]["risk_factor"], "pedestrian in route")
        self.assertFalse(result["retrieval"]["score_is_probability"])

    def test_excludes_candidate_without_http_source_and_warns(self):
        result = search_sif_cases("forklift pedestrian collision", [case("SIF-1", url="javascript:alert(1)")])
        self.assertEqual(result["status"], "no_citable_results")
        self.assertEqual(result["results"], [])
        self.assertTrue(result["warnings"])

    def test_rejects_non_official_source_domain(self):
        result = search_sif_cases(
            "forklift pedestrian collision",
            [case("SIF-1", url="https://data.go.kr.attacker.test/case")],
        )
        self.assertEqual(result["status"], "no_citable_results")
        self.assertTrue(result["warnings"])

    def test_applies_explicit_industry_filter(self):
        result = search_sif_cases(
            "forklift pedestrian collision",
            [case("SIF-C", industry="Construction"), case("SIF-M", industry="Manufacturing")],
            industry="construction",
        )
        self.assertEqual([item["case_id"] for item in result["results"]], ["SIF-C"])
        self.assertEqual(result["filters"]["industry"], "construction")

    def test_deduplicates_case_ids(self):
        result = search_sif_cases(
            "forklift pedestrian collision",
            [case("SIF-1"), case("SIF-1", url="https://www.data.go.kr/data/15161362/openapi.do?duplicate=1")],
            top_k=2,
        )
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(any("duplicate" in warning for warning in result["warnings"]))

    def test_validates_tool_inputs(self):
        for kwargs in ({"query": " "}, {"query": "forklift", "top_k": 0}, {"query": "forklift", "top_k": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_sif_cases(corpus=[], **kwargs)

    def test_exposes_closed_tool_schema(self):
        schema = tool_schema()
        self.assertEqual(schema["name"], "search_sif_cases")
        self.assertEqual(schema["input_schema"]["required"], ["query"])
        self.assertFalse(schema["input_schema"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
