# Architecture Decisions & Trade-offs

Running log of technology choices, alternatives considered, and the trade-offs.
**Audience: my future self in an architect interview.** Each entry should be readable as a 60–90 second answer.

Format per entry:

> **Decision** — what I chose
> **Alternatives** — what I considered
> **Why** — the deciding trade-off
> **Cost of being wrong** — what changes if this turns out to be the wrong call
> **Talk track** — the 1–2 sentence interview line

---

## 1. PDF parsing — start with PyMuPDF, escalate when needed

**Decision:** PyMuPDF (`fitz`) as the default text extractor. Treat it as tier-1.

**Alternatives:**
- **pdfplumber** — better for tables, slower.
- **PyPDF / pypdf** — pure-Python, simplest, lowest text quality.
- **Unstructured** — layout-aware partitioning + OCR (Tesseract). Heavier, slower.
- **PyMuPDF4LLM** — PyMuPDF wrapper that emits Markdown for LLMs.
- **Marker** — PDF → Markdown, GPU-accelerated, high quality.
- **Docling (IBM)** — strong layout + tables, structured output.
- **LlamaParse** — managed API, very strong on tables ($).
- **Amazon Textract** — OCR + tables + forms + queries (AWS managed, $).
- **Azure Document Intelligence** — equivalent on Azure.
- **Databricks `ai_parse_document`** — managed, integrates with Mosaic AI.

**Why:** PyMuPDF is the fastest pure-text path with the lowest setup cost. Most "clean" FSRs are text-based, so it'll work for the majority. We don't pay OCR cost or layout-engine complexity until we know we need it.

**Cost of being wrong:** scanned / heavily tabular FSRs come back with garbled or empty text. Escalation path is a **two-tier strategy**: detect low-yield extractions (chars/page below a threshold, lots of empty pages) and re-route those to Textract or Unstructured. This is the standard industry pattern.

**Talk track:**
> "We start with PyMuPDF because it's fast and good enough for clean text PDFs. We monitor extraction yield per doc, and route low-yield docs to a heavier OCR path — Textract on AWS or Unstructured locally. That keeps the common case cheap and the messy case correct."

---

## 2. Notebook layout — bronze / silver / gold under `code/`

**Decision:** mirror the medallion architecture used in `pw_sdg_ai_ser_repo`.

**Alternatives:** flat folder with numbered notebooks; one mega-notebook.

**Why:** the names already mean something to anyone who's worked with Databricks lakehouse patterns, and the parallel to prod is the whole point of the POC.

**Talk track:**
> "I kept the medallion split — bronze for raw + parsed, silver for cleaned + chunked + embedded, gold for retrieval and generation. It maps cleanly onto how this would land in production."

---

## 3. Vector store — FAISS locally, managed store in prod

**Decision:** FAISS for the POC; assume Databricks Vector Search (or OpenSearch / pgvector / Pinecone on AWS) in prod.

**What FAISS is:** Meta's open-source similarity-search library. C++ core with Python bindings. In-process, no server. The reference implementation of ANN algorithms — *HNSW*, *IVF*, *IVF-PQ*, exact (`IndexFlatL2` / `IndexFlatIP`).

**Alternatives (local / OSS):**
- **Chroma** — friendly Python API, in-process or server. Great for prototypes.
- **Qdrant** — Rust-based, runs as a server, strong filtering. Self-host or managed.
- **Weaviate** — server, hybrid search, schema. Self-host or managed.
- **Milvus** — server, scales out, more ops.
- **LanceDB** — embedded, columnar, good for notebooks.

**Alternatives (managed in our world):**
- **Databricks Mosaic AI Vector Search** — Delta Sync index ties retrieval to a Delta table; native filters; HNSW under the hood.
- **AWS OpenSearch Serverless (vector engine)** — default pairing with Bedrock Knowledge Bases.
- **Aurora PostgreSQL pgvector**, **Pinecone**, **Redis Vector**, **MongoDB Atlas Vector** — also supported by Bedrock KBs.

**Why FAISS for the POC:**
- Zero setup cost — `pip install` and you're indexing.
- Lets us learn the *algorithm* layer (HNSW, recall vs. latency, exact vs. approximate) without a service in the way.
- Most managed stores (Vector Search, OpenSearch, pgvector with HNSW) use the same algorithm under the hood — the mental model transfers cleanly.

**Why FAISS isn't prod for us:**
- No managed sync from a source table (Vector Search has Delta Sync indexes for this).
- Metadata filtering is bolt-on, not first class.
- No auth, no horizontal scaling, no replication.
- Persistence is "save the index file" — fine for one notebook, not for a service.

**Talk track:**
> "FAISS is the reference vector library — Meta's, in-process, fast. We use it locally to learn ANN concepts and inspect retrieval behavior. In prod we swap to a managed store like Databricks Vector Search or OpenSearch Serverless. The algorithm under the hood — usually HNSW — is the same, so the trade-offs we learn locally still apply."

---

## 4. Notebook format — `.ipynb` only

**Decision:** keep notebooks as `.ipynb`. Don't maintain a parallel `.py` (Databricks-source) copy.

**Why:**
- `.ipynb` runs natively in VS Code Jupyter *and* uploads cleanly to Databricks (drag-drop into a workspace folder works).
- Two files of the same notebook = drift risk.
- Conversion is one command if I ever want a script: `jupyter nbconvert --to script nb_xx.ipynb`.

**Cost of being wrong:** if we later move to Databricks Asset Bundles, `.py` notebook source is the bundle-friendly format and we'd convert then. Cheap to do.

**Talk track:** N/A — internal tooling decision, not interview-relevant.

---

_(more entries appended as I go)_
