"""Step 2: Retrieve ER (Engineering Record) chunks — self-contained module.

Consolidates: config, data_loader, chunking, embeddings, pipeline, retrievers,
and retrieve logic so REChainExperiment has no dependency on er_pipeline/.
"""

import time
import requests
import pandas as pd
from typing import List, Dict, Tuple
from databricks import sql
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS


from .config import (
    get_db_connection as _get_db_connection,
    ER_TABLE,
    ER_SERIALS as SERIALS,
    ER_EMBEDDING_HOST,
    ER_EMBEDDING_TOKEN,
    ER_EMBEDDING_MODEL,
    ER_EMBEDDING_VERIFY_SSL,
    ER_TOKEN_LIMIT,
    ER_OVERLAP_PCT,
    ER_RETRIEVAL_K,
)


# ── Data loading ─────────────────────────────────────────────────

def _preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df["opened_at"] = pd.to_datetime(df["opened_at"], errors="coerce")
    df = df[df["opened_at"] >= "2016-01-01"].copy()
    df["serial_number"] = df["u_serial_number"].fillna("MISSING").replace("", "BLANK")
    df = df[~df["serial_number"].isin(["MISSING", "BLANK"])].copy()
    df["er_number"] = df["number"]
    df["status"] = df["u_status"]
    return df


def _gather_data() -> pd.DataFrame:
    serial_list = ", ".join(f"'{s}'" for s in SERIALS)
    query = f"SELECT * FROM {ER_TABLE} WHERE u_serial_number IN ({serial_list})"
    with _get_db_connection() as conn:
        df = pd.read_sql(query, conn)
    print(f"[ER] Loaded {len(df):,} records")
    return _preprocess(df)


# ── Chunking ─────────────────────────────────────────────────────

_TEXT_FIELDS = [
    "close_notes", "comments", "comments_and_work_notes", "description_",
    "short_description", "u_desired_deliverable", "u_feedback_comments",
    "u_field_action_taken", "u_immediate_response_explanati",
    "u_resolve_notes", "user_input", "work_notes", "work_notes_list",
]


def _combine_fields(row) -> str:
    parts = []
    for f in _TEXT_FIELDS:
        if f in row.index and pd.notna(row[f]) and str(row[f]).strip():
            parts.append(f"[{f.upper()}]\n{row[f]}")
    return "\n\n".join(parts) if parts else ""


def _count_tokens(text) -> int:
    if pd.isna(text) or text == "":
        return 0
    return max(1, int(len(str(text).split()) * 1.33))


def _chunk_er_records(df_serial: pd.DataFrame, token_limit: int, overlap_pct: int) -> List[Document]:
    all_chunks: List[Document] = []
    for _, row in df_serial.iterrows():
        text = _combine_fields(row)
        if not text:
            continue
        tokens = _count_tokens(text)
        meta = {
            "er_number": str(row.get("er_number", row.get("number", ""))),
            "opened_at": str(row.get("opened_at", "")),
            "u_component": str(row.get("u_component", "")),
            "u_field_action_taken": str(row.get("u_field_action_taken", "")),
            "serial_number": str(row.get("u_serial_number", row.get("serial_number", ""))),
            "status": str(row.get("status", row.get("u_status", "Unknown"))),
            "equipment": str(row.get("u_equipment", "")),
            "equipment_id": str(row.get("equipment_id", "")),
            "chunk_index": 0,
            "source": "ER",
        }
        if tokens <= token_limit:
            all_chunks.append(Document(page_content=text, metadata=meta))
            continue

        words = text.split()
        max_w = int(token_limit / 1.33)
        overlap_w = int(max_w * overlap_pct / 100)
        chunk_docs: List[Document] = []
        start = 0
        while start < len(words):
            end = min(start + max_w, len(words))
            chunk_meta = meta.copy()
            chunk_meta["chunk_index"] = len(chunk_docs)
            chunk_docs.append(Document(page_content=" ".join(words[start:end]), metadata=chunk_meta))
            if end >= len(words):
                break
            start = end - overlap_w
        all_chunks.extend(chunk_docs)
    return all_chunks


# ── Embeddings ───────────────────────────────────────────────────

class _LiteLLMClient:
    def __init__(self, host: str, token: str, verify_ssl: bool = False):
        self.url = host.rstrip("/") + "/v1/embeddings"
        self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        self.verify_ssl = verify_ssl

    def get_embeddings(self, texts: List[str], model: str, max_retries: int = 3) -> List[List[float]]:
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(self.url, headers=self.headers,
                                     json={"model": model, "input": texts},
                                     verify=self.verify_ssl, timeout=60)
                resp.raise_for_status()
                return [item["embedding"] for item in resp.json()["data"]]
            except (requests.exceptions.ConnectionError, ConnectionResetError, OSError,
                    requests.exceptions.Timeout) as e:
                if attempt < max_retries:
                    wait = 3 * attempt
                    print(f"[Embedding] Request failed (attempt {attempt}/{max_retries}), retry in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    print(f"[Embedding] Request failed after {max_retries} attempts: {e}")
                    raise


class _AzureEmbeddings(Embeddings):
    def __init__(self, client: _LiteLLMClient, model: str):
        self.client = client
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        all_emb: List[List[float]] = []
        for i in range(0, len(texts), 100):
            all_emb.extend(self.client.get_embeddings(texts[i:i + 100], self.model))
            if i + 100 < len(texts):
                time.sleep(0.5)
        return all_emb

    def embed_query(self, text: str) -> List[float]:
        return self.client.get_embeddings([text], self.model)[0]


# ── Retrievers ───────────────────────────────────────────────────

class _EnsembleRetriever:
    def __init__(self, bm25, faiss_ret, weights=(0.6, 0.4), k=10):
        self.bm25 = bm25
        self.faiss = faiss_ret
        self.weights = weights
        self.k = k

    def invoke(self, query, bm25_docs=None, faiss_docs=None):
        if bm25_docs is None:
            try:
                bm25_docs = self.bm25.invoke(query)[:self.k]
            except Exception:
                bm25_docs = self.bm25.get_relevant_documents(query)[:self.k]
        if faiss_docs is None:
            try:
                faiss_docs = self.faiss.invoke(query)[:self.k]
            except Exception:
                faiss_docs = self.faiss.get_relevant_documents(query)[:self.k]

        doc_scores: Dict[str, float] = {}
        seen: Dict[str, Document] = {}
        for rank, doc in enumerate(bm25_docs, 1):
            h = doc.page_content[:100]
            if h not in seen:
                seen[h] = doc
                doc_scores[h] = self.weights[0] / (60 + rank)
        for rank, doc in enumerate(faiss_docs, 1):
            h = doc.page_content[:100]
            if h not in seen:
                seen[h] = doc
                doc_scores[h] = self.weights[1] / (60 + rank)
            else:
                doc_scores[h] += self.weights[1] / (60 + rank)

        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:self.k]
        return [seen[h] for h, _ in ranked]


def _rerank(query: str, docs: List[Document], k: int) -> List[Tuple[Document, float]]:
    qwords = set(query.lower().split())
    scored = []
    for idx, d in enumerate(docs):
        dwords = set(d.page_content.lower().split())
        overlap = len(qwords & dwords)
        union = len(qwords | dwords)
        jaccard = overlap / union if union else 0.0
        position = 1.0 / (idx + 1)
        score = (jaccard * 0.6) + (position * 0.4)
        if str(d.metadata.get("status", "")) == "Complete":
            score *= 1.2
        scored.append((d, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ── Caches ───────────────────────────────────────────────────────

_data_cache: pd.DataFrame | None = None
_pipeline_cache: Dict[str, tuple] = {}  # serial_number -> (docs, bm25, faiss_vs, emb)


def _get_data() -> pd.DataFrame:
    """Fetch ER data once and cache for the lifetime of the process."""
    global _data_cache
    if _data_cache is None:
        _data_cache = _gather_data()
    return _data_cache


# ── Pipeline (chunk + embed — cached per serial) ─────────────────

def _build_pipeline(df_serial: pd.DataFrame):
    docs = _chunk_er_records(df_serial, ER_TOKEN_LIMIT, ER_OVERLAP_PCT)
    client = _LiteLLMClient(ER_EMBEDDING_HOST, ER_EMBEDDING_TOKEN, ER_EMBEDDING_VERIFY_SSL)
    emb = _AzureEmbeddings(client, ER_EMBEDDING_MODEL)
    bm25 = BM25Retriever.from_documents(docs)
    faiss_vs = FAISS.from_documents(docs, emb)
    return docs, bm25, faiss_vs, emb


def _get_pipeline(serial_number: str):
    """Build pipeline once per serial and cache. k applied at query time."""
    if serial_number not in _pipeline_cache:
        df = _get_data()
        df_serial = df[df["serial_number"] == serial_number].copy()
        if len(df_serial) == 0:
            return None
        _pipeline_cache[serial_number] = _build_pipeline(df_serial)
        print(f"[ER] Cached pipeline for serial={serial_number}")
    else:
        print(f"[ER] Using cached pipeline for serial={serial_number}")
    return _pipeline_cache[serial_number]


# ── Public API ───────────────────────────────────────────────────

def query_er(
    serial_number: str,
    query: str,
    retriever_type: str = "ensemble",
    k: int = 5,
    do_rerank: bool = True,
) -> List[Dict]:
    """
    Retrieve relevant ER chunks for a serial + query.

    Args:
        serial_number: Equipment serial (e.g. "290T658")
        query: Search query text (e.g. issue_prompt + severity criteria)
        retriever_type: "bm25", "faiss", or "ensemble"
        k: Number of results to return
        do_rerank: Whether to apply reranking

    Returns:
        List of dicts with er_number, serial_number, opened_at, status,
        u_component, u_field_action_taken, equipment, equipment_id,
        chunk_text, chunk_index, score
    """
    cached = _get_pipeline(serial_number)
    if cached is None:
        print(f"[ER] No records for {serial_number}")
        return []

    docs, bm25, faiss_vs, emb = cached
    print(f"[ER] {serial_number}: {len(docs)} chunks")

    # Apply k at query time
    bm25.k = k
    faiss_ret = faiss_vs.as_retriever(search_kwargs={"k": k})
    ensemble = _EnsembleRetriever(bm25, faiss_ret, k=k)

    retrievers = {"bm25": bm25, "faiss": faiss_ret, "ensemble": ensemble}
    ret = retrievers.get(retriever_type.lower(), ensemble)

    t0 = time.time()
    if retriever_type.lower() == "ensemble":
        try:
            bm25_docs = bm25.invoke(query)
        except Exception:
            bm25_docs = bm25.get_relevant_documents(query)
        try:
            faiss_docs = faiss_ret.invoke(query)
        except Exception:
            faiss_docs = faiss_ret.get_relevant_documents(query)
        rdocs = ensemble.invoke(query, bm25_docs=bm25_docs, faiss_docs=faiss_docs)
    else:
        try:
            rdocs = ret.invoke(query)
        except Exception:
            rdocs = ret.get_relevant_documents(query)
    latency = round((time.time() - t0) * 1000, 2)

    if do_rerank and rdocs:
        final = _rerank(query, rdocs, k)
    else:
        final = [(d, 0.0) for d in rdocs[:k]]

    results = []
    for doc, score in final:
        results.append({
            "er_number": doc.metadata.get("er_number", ""),
            "serial_number": doc.metadata.get("serial_number", ""),
            "opened_at": doc.metadata.get("opened_at", ""),
            "status": doc.metadata.get("status", ""),
            "u_component": doc.metadata.get("u_component", ""),
            "u_field_action_taken": doc.metadata.get("u_field_action_taken", ""),
            "equipment": doc.metadata.get("equipment", ""),
            "equipment_id": doc.metadata.get("equipment_id", ""),
            "chunk_text": doc.page_content,
            "chunk_index": doc.metadata.get("chunk_index", 0),
            "score": float(round(score, 4)),
        })

    print(f"[ER] Found {len(results)} chunks for serial='{serial_number}' ({retriever_type}, k={k}, rerank={do_rerank}) in {latency}ms")
    return results
