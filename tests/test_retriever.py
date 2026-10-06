import unittest

import numpy as np

from src.retriever import PersonalRetriever


class _FakeMatrix:
    def __init__(self, rows):
        self.rows = rows

    def toarray(self):
        return np.asarray(self.rows, dtype=np.float32)


class _FakeVectorizer:
    def transform(self, texts):
        rows = []
        for index, text in enumerate(texts):
            if index == 0 or "named source" in text:
                rows.append([1.0, 0.0])
            else:
                rows.append([0.1, 0.9])
        return _FakeMatrix(rows)


def _metadata(doc_id: str) -> dict:
    return {
        "doc_id": doc_id,
        "source_type": "sif",
        "industry_major": "제조업",
        "equipment": "",
        "title": doc_id,
        "source_url": "https://example.org/source",
        "page": None,
    }


class ExactDocumentIdRetrievalTests(unittest.TestCase):
    def make_retriever(self) -> PersonalRetriever:
        retriever = object.__new__(PersonalRetriever)
        retriever.mode = "lexical"
        retriever.vectorizer = _FakeVectorizer()
        retriever.indexes = {
            "lexical": (
                np.array(["chunk-other", "chunk-target"]),
                np.array([[1.0, 0.0], [0.1, 0.9]], dtype=np.float32),
                [_metadata("SIF-M-0999"), _metadata("SIF-M-0150")],
                ["similar but wrong case", "the named source case"],
            )
        }
        return retriever

    def test_explicit_document_id_overrides_similar_rank(self) -> None:
        retriever = self.make_retriever()
        hits = retriever.retrieve("SIF-M-0150 사고 원인은?")
        self.assertEqual([hit["doc_id"] for hit in hits], ["SIF-M-0150"])
        self.assertTrue(hits[0]["exact_doc_id_match"])

    def test_unknown_explicit_document_id_returns_no_substitute(self) -> None:
        retriever = self.make_retriever()
        hits = retriever.retrieve("SIF-M-1234 사고 원인은?")
        self.assertEqual(hits, [])

    def test_semantic_mode_uses_local_exact_match_without_embedding_call(self) -> None:
        retriever = self.make_retriever()
        retriever.mode = "semantic"
        retriever.indexes = {"semantic": retriever.indexes["lexical"]}
        retriever._semantic_vector = lambda _question: (_ for _ in ()).throw(
            AssertionError("exact ID retrieval must not request an embedding")
        )
        hits = retriever.retrieve("SIF-M-0150 사고 원인은?")
        self.assertEqual([hit["doc_id"] for hit in hits], ["SIF-M-0150"])


if __name__ == "__main__":
    unittest.main()
