"""Exact document retrieval over personal Chroma lexical and semantic vectors."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import chromadb
import numpy as np
from dotenv import dotenv_values
from openai import OpenAI
from sklearn.feature_extraction.text import CountVectorizer, HashingVectorizer

from src.bm25_eval import _bm25_scores


class PersonalRetriever:
    def __init__(self, root: Path, *, mode: str = "semantic"):
        if mode not in {"lexical", "semantic", "hybrid_rrf", "bm25"}:
            raise ValueError(f"Unknown retrieval mode: {mode}")
        self.root = root
        self.mode = mode
        corpus = root / "data/personal/corpus"
        lexical = json.loads((corpus / "index_meta.json").read_text(encoding="utf-8"))
        semantic = json.loads((corpus / "index_meta_semantic.json").read_text(encoding="utf-8"))
        raw_sha = hashlib.sha256((corpus / "chunks.jsonl").read_bytes()).hexdigest()
        if (lexical["corpus_sha256"] != raw_sha or semantic["corpus_sha256"] != raw_sha
                or not semantic["complete"]):
            raise RuntimeError("Search index does not match the complete corpus")
        self.semantic_model = semantic["model"]
        self.vectorizer = HashingVectorizer(
            analyzer="char", ngram_range=(2, 4), n_features=1024,
            alternate_sign=False, norm="l2", dtype=np.float32,
        )
        self._openai = None
        db = chromadb.PersistentClient(path=str(root / "chroma_db/personal"))
        metas = {"lexical": lexical, "semantic": semantic}
        needed = {"semantic" if mode == "semantic" else "lexical"} if mode != "hybrid_rrf" else {"lexical", "semantic"}
        self.indexes = {}
        for name in needed:
            collection = db.get_collection(metas[name]["collection"], embedding_function=None)
            if collection.count() != metas[name]["chunks"]:
                raise RuntimeError(f"Incomplete {name} index")
            stored = collection.get(include=["embeddings", "metadatas", "documents"])
            ids = np.asarray(stored["ids"])
            order = np.argsort(ids, kind="stable")
            vectors = np.asarray(stored["embeddings"], dtype=np.float32)[order]
            vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
            self.indexes[name] = (
                ids[order], vectors,
                [stored["metadatas"][int(i)] for i in order],
                [stored["documents"][int(i)] for i in order],
            )
        if mode == "bm25":
            texts = self.indexes["lexical"][3]
            self.bm25_vectorizer = CountVectorizer(
                analyzer="char_wb", ngram_range=(2, 4),
                lowercase=False, dtype=np.float32,
            )
            self.bm25_matrix = self.bm25_vectorizer.fit_transform(texts).tocsr()
            document_frequency = np.asarray((self.bm25_matrix > 0).sum(axis=0)).ravel().astype(np.float32)
            count = self.bm25_matrix.shape[0]
            self.bm25_idf = np.log1p(
                (count - document_frequency + 0.5) / (document_frequency + 0.5)
            ).astype(np.float32)
            self.bm25_lengths = np.asarray(self.bm25_matrix.sum(axis=1)).ravel().astype(np.float32)
            self.bm25_average_length = float(self.bm25_lengths.mean())

    def _semantic_vector(self, query: str) -> np.ndarray:
        if self._openai is None:
            key = (dotenv_values(self.root / ".env").get("OPENAI_API_KEY") or "").strip()
            if not key:
                raise RuntimeError("OPENAI_API_KEY is missing")
            self._openai = OpenAI(api_key=key, timeout=60, max_retries=2)
        response = self._openai.embeddings.create(
            model=self.semantic_model, input=query, encoding_format="float"
        )
        return np.asarray(response.data[0].embedding, dtype=np.float32)

    def _rank(self, name: str, vector: np.ndarray, *, source_type: str | None,
              industry_major: str | None, equipment: str | None) -> list[dict]:
        ids, vectors, metadatas, documents = self.indexes[name]
        query = vector / max(float(np.linalg.norm(vector)), 1e-12)
        similarities = vectors @ query
        equipment_key = equipment.casefold() if equipment else ""
        filters = np.fromiter((
            (not source_type or meta["source_type"] == source_type)
            and (not industry_major or meta["source_type"] != "sif"
                 or meta["industry_major"] == industry_major)
            and (not equipment_key or equipment_key in meta["equipment"].casefold()
                 or (not meta["equipment"] and equipment_key in documents[i].casefold()))
            for i, meta in enumerate(metadatas)
        ), dtype=bool)
        similarities = np.where(filters, similarities, -np.inf)
        order = np.lexsort((ids, -similarities))
        hits = []
        doc_counts: dict[str, int] = {}
        for position in order:
            if not np.isfinite(similarities[position]):
                break
            meta = metadatas[int(position)]
            max_per_doc = 3 if meta["source_type"] == "kosha_guide" else 1
            if doc_counts.get(meta["doc_id"], 0) >= max_per_doc:
                continue
            doc_counts[meta["doc_id"]] = doc_counts.get(meta["doc_id"], 0) + 1
            hits.append({
                "doc_id": meta["doc_id"],
                "text": documents[int(position)],
                "metadata": meta,
                "similarity": float(similarities[position]),
            })
            if len(hits) >= 100:
                break
        return hits

    def _rank_bm25(self, question: str, *, source_type: str | None,
                   industry_major: str | None, equipment: str | None) -> list[dict]:
        ids, _, metadatas, documents = self.indexes["lexical"]
        scores = _bm25_scores(
            question, self.bm25_vectorizer, self.bm25_matrix, self.bm25_idf,
            self.bm25_lengths, self.bm25_average_length,
        )
        equipment_key = equipment.casefold() if equipment else ""
        valid = np.fromiter((
            (not source_type or meta["source_type"] == source_type)
            and (not industry_major or meta["source_type"] != "sif"
                 or meta["industry_major"] == industry_major)
            and (not equipment_key or equipment_key in meta["equipment"].casefold()
                 or (not meta["equipment"] and equipment_key in documents[i].casefold()))
            for i, meta in enumerate(metadatas)
        ), dtype=bool)
        scores = np.where(valid, scores, 0.0)
        order = np.lexsort((ids, -scores))
        hits = []
        doc_counts: dict[str, int] = {}
        for position in order:
            if scores[position] <= 0:
                break
            meta = metadatas[int(position)]
            max_per_doc = 3 if meta["source_type"] == "kosha_guide" else 1
            if doc_counts.get(meta["doc_id"], 0) >= max_per_doc:
                continue
            doc_counts[meta["doc_id"]] = doc_counts.get(meta["doc_id"], 0) + 1
            hits.append({
                "doc_id": meta["doc_id"], "text": documents[int(position)],
                "metadata": meta, "similarity": float(scores[position]),
            })
            if len(hits) >= 100:
                break
        return hits

    @staticmethod
    def _mentioned_document_ids(question: str, known_ids: set[str]) -> list[str] | None:
        """Return explicit corpus IDs in the question, or None if there are none.

        If a question names an ID that looks like a document identifier but is not
        in the corpus, the caller receives an empty match list and can abstain
        instead of substituting a merely similar incident.
        """
        candidates = re.findall(
            r"(?<![A-Z0-9])[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,5}(?![A-Z0-9])",
            question.upper(),
        )
        if not candidates:
            return None
        known = {doc_id.upper(): doc_id for doc_id in known_ids}
        return list(dict.fromkeys(known[item] for item in candidates if item in known))

    @staticmethod
    def _exact_document_hits(
        doc_id: str,
        index: tuple[np.ndarray, np.ndarray, list[dict], list[str]],
        question: str,
        vectorizer: HashingVectorizer,
        *,
        source_type: str | None,
        industry_major: str | None,
        equipment: str | None,
        limit: int,
    ) -> list[dict]:
        ids, _, metadatas, documents = index
        equipment_key = equipment.casefold() if equipment else ""
        positions = [
            i for i, meta in enumerate(metadatas)
            if meta["doc_id"] == doc_id
            and (not source_type or meta["source_type"] == source_type)
            and (not industry_major or meta["source_type"] != "sif"
                 or meta["industry_major"] == industry_major)
            and (not equipment_key or equipment_key in meta["equipment"].casefold()
                 or (not meta["equipment"] and equipment_key in documents[i].casefold()))
        ]
        if not positions:
            return []
        local_vectors = vectorizer.transform(
            [question, *(documents[i] for i in positions)]
        ).toarray().astype(np.float32)
        query = local_vectors[0]
        query /= max(float(np.linalg.norm(query)), 1e-12)
        scores = local_vectors[1:] @ query
        ranked_positions = sorted(
            zip(positions, scores), key=lambda item: (-item[1], ids[item[0]])
        )
        return [
            {
                "doc_id": doc_id,
                "text": documents[i],
                "metadata": metadatas[i],
                "similarity": float(score),
                "exact_doc_id_match": True,
            }
            for i, score in ranked_positions[:limit]
        ]

    def retrieve(self, question: str, *, k: int = 5, source_type: str | None = None,
                 industry_major: str | None = None, equipment: str | None = None) -> list[dict]:
        if not question.strip():
            raise ValueError("Empty retrieval query")
        if k < 1:
            raise ValueError("k must be positive")
        filters = {"source_type": source_type, "industry_major": industry_major,
                   "equipment": equipment}
        known_ids = {
            str(meta["doc_id"])
            for _, _, metadatas, _ in self.indexes.values()
            for meta in metadatas
        }
        mentioned_ids = self._mentioned_document_ids(question, known_ids)
        if mentioned_ids is not None:
            # Match IDs before semantic embedding so a cited case needs no API call.
            if not mentioned_ids:
                return []
            index_name = "semantic" if "semantic" in self.indexes else "lexical"
            exact_hits = []
            for doc_id in mentioned_ids:
                exact_hits.extend(self._exact_document_hits(
                    doc_id, self.indexes[index_name], question, self.vectorizer,
                    limit=k, **filters,
                ))
            return exact_hits[:k]

        ranked = {}
        query_vectors = {}
        if self.mode == "bm25":
            ranked["bm25"] = self._rank_bm25(question, **filters)
        if self.mode in {"lexical", "hybrid_rrf"}:
            vector = self.vectorizer.transform([question]).toarray()[0].astype(np.float32)
            query_vectors["lexical"] = vector
            ranked["lexical"] = self._rank("lexical", vector, **filters)
        if self.mode in {"semantic", "hybrid_rrf"}:
            vector = self._semantic_vector(question)
            query_vectors["semantic"] = vector
            ranked["semantic"] = self._rank("semantic", vector, **filters)

        if self.mode != "hybrid_rrf":
            selected = ranked[self.mode][:k]
        else:
            fused = {}
            references = {}
            for name, hits in ranked.items():
                seen_docs = set()
                document_rank = 0
                for hit in hits:
                    doc_id = hit["doc_id"]
                    if doc_id in seen_docs:
                        continue
                    seen_docs.add(doc_id)
                    document_rank += 1
                    fused[doc_id] = fused.get(doc_id, 0.0) + 1 / (60 + document_rank)
                    if doc_id not in references or name == "semantic":
                        references[doc_id] = hit
            ordered = sorted(fused, key=lambda doc_id: (-fused[doc_id], doc_id))[:k]
            selected = [references[doc_id] for doc_id in ordered]
        if source_type == "moel_report" and selected and any(
            term in question for term in ("원인", "대책", "예방", "방지")
        ):
            name = "semantic" if "semantic" in self.indexes else "lexical"
            return self._expand_report_sections(selected, query_vectors[name], name, k)
        return selected

    def retrieve_tbm(self, question: str, *, k: int = 5,
                     source_type: str | None = None,
                     industry_major: str | None = None,
                     equipment: str | None = None) -> list[dict]:
        """Search incident cases and official guidance together for a TBM draft."""
        if k < 2:
            raise ValueError("TBM retrieval needs at least two evidence slots")
        filters = {"industry_major": industry_major, "equipment": equipment}
        candidates = []
        anchors = []
        for source_type in ("sif", "kosha_guide"):
            hits = self.retrieve(question, k=max(3, k), source_type=source_type, **filters)
            if hits:
                anchors.append(hits[0])
                candidates.extend(hits)
        if not candidates:
            return []
        # Reserve one evidence slot per source type when available, then fill
        # the remaining slots with the highest-scoring distinct passages.
        selected = sorted(anchors, key=lambda hit: (-hit["similarity"], hit["doc_id"]))
        seen = {(hit["doc_id"], hit["metadata"]["page"], hit["text"]) for hit in selected}
        for hit in sorted(candidates, key=lambda item: (-item["similarity"], item["doc_id"])):
            identity = (hit["doc_id"], hit["metadata"]["page"], hit["text"])
            if identity in seen:
                continue
            selected.append(hit)
            seen.add(identity)
            if len(selected) >= k:
                break
        return selected[:k]

    def _expand_report_sections(self, selected: list[dict], query_vector: np.ndarray,
                                name: str, k: int) -> list[dict]:
        """Include cause/prevention pages from the top report when the question asks for them."""
        ids, vectors, metadatas, documents = self.indexes[name]
        primary = selected[0]
        doc_id = primary["doc_id"]
        if primary["metadata"]["source_type"] != "moel_report":
            return selected
        candidate_positions = [i for i, item in enumerate(metadatas) if item["doc_id"] == doc_id]
        heading_positions = [
            i for i in candidate_positions
            if "재해발생원인" in documents[i] or "재해예방대책" in documents[i]
            or "재발방지대책" in documents[i]
        ]
        if not heading_positions:
            return selected
        wanted_pages = {metadatas[i]["page"] for i in heading_positions}
        wanted_pages.update(page + 1 for page in list(wanted_pages))
        extra_positions = [i for i in candidate_positions if metadatas[i]["page"] in wanted_pages]
        extra_positions.sort(key=lambda i: (metadatas[i]["page"], ids[i]))
        query = query_vector / max(float(np.linalg.norm(query_vector)), 1e-12)
        result = [primary]
        seen = {(primary["doc_id"], primary["metadata"]["page"], primary["text"])}
        for position in extra_positions:
            item = {
                "doc_id": doc_id,
                "text": documents[position],
                "metadata": metadatas[position],
                "similarity": float(vectors[position] @ query),
            }
            identity = (item["doc_id"], item["metadata"]["page"], item["text"])
            if identity in seen:
                continue
            seen.add(identity)
            result.append(item)
            if len(result) >= min(k, 4):
                break
        for item in selected[1:]:
            if len(result) >= k:
                break
            result.append(item)
        return result[:k]
