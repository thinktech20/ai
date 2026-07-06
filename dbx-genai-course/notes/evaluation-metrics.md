# Retrieval and Response Accuracy Metrics - Databricks GenAI Exam Notes

## 1. Big Picture

In GenAI and RAG systems, evaluation usually falls into three buckets:

| Evaluation Area | What It Measures | Common Metrics |
|---|---|---|
| Retrieval quality | Did the system retrieve the right chunks/documents? | precision@k, recall@k, cosine similarity, NDCG, MRR, hit rate |
| Generated response quality | Did the model generate a good answer, summary, or translation? | BLEU, ROUGE, METEOR, human review, LLM-as-judge |
| Model prediction quality | How well does a language model predict text? | perplexity, cross-entropy |

For the exam, first identify what is being evaluated:

```text
Retriever/vector search quality?  -> precision@k, recall@k, cosine similarity, NDCG
Machine translation?              -> BLEU
Summarization?                    -> ROUGE
Language model uncertainty?       -> perplexity
Production latency/errors?        -> inference tables / monitoring metrics
```

---

# 2. Retrieval Relevance Metrics

Retrieval metrics evaluate whether the vector search or retriever is returning the right context before the LLM generates an answer.

In a RAG pipeline:

```text
User question
   -> vector search / retriever
   -> top-k chunks
   -> prompt with retrieved context
   -> LLM answer
```

If retrieval is bad, the LLM may generate a weak or hallucinated answer even if the LLM itself is strong.

---

## 2.1 Precision

**Precision** measures how many of the retrieved documents/chunks are actually relevant.

**Formula:**

```text
Precision = relevant retrieved documents / total retrieved documents
```

**Example:**

```text
System retrieves 10 chunks.
7 are relevant.
Precision = 7 / 10 = 0.70
```

Precision is about **cleanliness of retrieved context**.

For RAG:

```text
High precision = less junk context sent to the LLM
Low precision  = the LLM receives irrelevant/distracting context
```

---

## 2.2 Precision@k

**Precision@k** asks:

> Out of the top k results returned, how many were relevant?

**Formula:**

```text
Precision@k = relevant results in top k / k
```

**Example:**

```text
Retriever returns top 5 chunks.
4 of them are relevant.
Precision@5 = 4 / 5 = 80%
```

Use precision@k when the exam asks how clean or relevant the top-k retrieved results are.

---

## 2.3 Recall

**Recall** measures how many of all relevant documents/chunks were retrieved.

**Formula:**

```text
Recall = relevant retrieved documents / total relevant documents in the dataset
```

**Example:**

```text
There are 20 relevant chunks in the gold dataset.
System retrieves 15 of them.
Recall = 15 / 20 = 0.75
```

Recall is about **not missing important context**.

For RAG:

```text
High recall = the retriever finds most of the needed context
Low recall  = the retriever misses important evidence, so the LLM may answer poorly
```

---

## 2.4 Recall@k

**Recall@k** asks:

> Out of all the relevant results that should have been found, how many appeared in the top k?

**Formula:**

```text
Recall@k = relevant results in top k / total known relevant results
```

**Example:**

```text
There are 10 truly relevant chunks.
Retriever returns top 5 chunks.
4 of those top 5 are relevant.
Recall@5 = 4 / 10 = 40%
```

Use recall@k when the exam asks whether the retriever is finding the important relevant chunks.

---

## 2.5 Do Precision@k and Recall@k Require a Gold Dataset?

Usually, yes.

To calculate true precision@k and recall@k, you need to know which chunks are actually relevant for each test question.

That normally requires a **gold dataset**, also called a:

```text
labeled dataset
benchmark dataset
ground-truth query set
SME-validated test set
```

Without a gold set, you can still do manual review or LLM-as-judge evaluation, but true precision/recall requires known relevant results.

---

## 2.6 What a RAG Gold Dataset Looks Like

A practical RAG gold set usually looks like this:

| query_id | test_question | relevant_document_or_section | relevant_chunk_ids |
|---|---|---|---|
| q001 | What are the inspection requirements for TIL 123? | TIL_123.pdf, Inspection section | chunk_45, chunk_46 |
| q002 | What causes compressor blade cracking? | Blade failure reports | chunk_901, chunk_914, chunk_920 |
| q003 | What repair action is recommended for issue X? | Repair recommendations section | chunk_1201 |

Then you run:

```text
question -> vector search -> top-k retrieved chunks
```

And compare:

```text
retrieved chunks vs gold relevant chunks
```

---

## 2.7 How Teams Prepare a Gold Set of Chunks

Teams usually do not label the full corpus. They create a smaller benchmark set.

### Step 1 - Pick Representative User Questions

Use questions from SMEs, UAT, support tickets, production logs, or expected user workflows.

For an engineering RAG system, examples could be:

```text
What historical repairs were performed on unit X?
What does this TIL say about applicability?
What are the known failure modes for this equipment type?
What inspection interval is recommended?
What documents mention serial number ABC123?
```

Try to cover different query patterns:

```text
fact lookup
troubleshooting
document-specific lookup
multi-document comparison
metadata filtering
rare edge cases
```

### Step 2 - Have SMEs Label Correct Sources

For each question, an SME or evaluator marks relevant chunks, sections, or documents.

Labels can be simple:

```text
Relevant
Partially relevant
Not relevant
```

Or more detailed:

```text
Gold evidence chunk
Supporting chunk
Distractor chunk
```

### Step 3 - Store Labels in an Evaluation Table

Example:

| query_id | question | relevant_chunk_ids |
|---|---|---|
| q001 | What are the inspection requirements for TIL 123? | [c45, c46] |
| q002 | What repair history exists for unit X? | [c901, c914] |

Then each experiment can run against the same gold set.

### Step 4 - Use the Same Gold Set to Compare Retrieval Settings

You can compare:

```text
chunk size 500 vs 1000
chunk overlap 50 vs 150
top_k 5 vs 10
embedding model A vs B
HNSW vs LSH
metadata filters on/off
reranker on/off
```

Log metrics such as:

```text
precision@5
recall@5
precision@10
recall@10
latency
cost
```

This is a good use case for MLflow tracking and evaluation.

---

## 2.8 Chunk-ID Gold Sets vs Document/Section Gold Sets

Hard-coding only chunk IDs can be fragile because chunk IDs may change when you change chunking strategy.

A more robust gold set labels:

```text
document ID
section name
answer span
source page
expected chunk IDs, if available
```

Then, during evaluation, you map the retrieved chunks back to the source document/section/span.

For real projects, this is often better than only labeling chunk IDs.

---

## 2.9 Cosine Similarity

**Cosine similarity** measures how close two vectors are in direction.

In vector search:

```text
higher cosine similarity = stronger semantic match
lower cosine similarity  = weaker semantic match
```

Use cosine similarity when comparing whether retrieved vectors are semantically close to known relevant vectors.

Example exam wording:

```text
Compare LSH and HNSW for semantic relevance.
```

Good metric:

```text
Measure cosine similarity between vectors returned by each index and vectors from a labeled ground-truth query set.
```

---

## 2.10 NDCG

**NDCG** stands for **Normalized Discounted Cumulative Gain**.

It evaluates ranking quality. It rewards systems that place the most relevant results near the top.

Use NDCG when:

```text
The order/ranking of retrieved results matters.
There are graded relevance labels, such as highly relevant, partially relevant, not relevant.
```

For RAG retrieval:

```text
High NDCG = best evidence appears near the top of retrieved results
```

---

## 2.11 MRR and Hit Rate

### MRR - Mean Reciprocal Rank

MRR measures how high the first relevant result appears.

Good for questions where one correct result is enough.

```text
Relevant result at rank 1 -> reciprocal rank = 1/1 = 1.0
Relevant result at rank 4 -> reciprocal rank = 1/4 = 0.25
```

### Hit Rate@k

Hit Rate@k asks:

```text
Did at least one relevant result appear in the top k?
```

Good for quick retrieval checks.

---

# 3. Response / Generation Quality Metrics

Response metrics evaluate the LLM output itself.

These usually require a reference answer, reference summary, or reference translation.

---

## 3.1 BLEU

**BLEU** stands for **Bilingual Evaluation Understudy**.

It is most commonly used for **machine translation**.

BLEU compares a model-generated translation to one or more gold-standard reference translations using n-gram overlap.

Use BLEU when the exam says:

```text
machine translation
translated text
source language to target language
gold-standard translations
labeled translation dataset
```

Example:

```text
Source:      Company must disclose annual carbon emissions.
Reference:   La empresa debe divulgar las emisiones anuales de carbono.
Generated:   La empresa debe reportar las emisiones anuales de carbono.
```

BLEU checks how much the generated translation overlaps with the trusted reference translation.

### Exam Shortcut

```text
Machine translation + gold-standard references -> BLEU
```

---

## 3.2 ROUGE

**ROUGE** stands for **Recall-Oriented Understudy for Gisting Evaluation**.

It is most commonly used for **summarization**.

ROUGE measures overlap between a generated summary and a reference summary.

It can evaluate:

```text
n-gram overlap
word sequence overlap
content coverage
```

Use ROUGE when the exam says:

```text
summarization
summary quality
reference summary
gisting
```

### Exam Shortcut

```text
Summarization + reference summary -> ROUGE
```

---

## 3.3 METEOR

**METEOR** is another metric used for machine translation evaluation.

Compared with BLEU, METEOR can account for things like stemming, synonyms, and alignment.

However, for many exam questions asking for the standard high-performance machine translation metric, the expected answer is usually **BLEU**.

Use METEOR only when the question explicitly mentions it or asks for an alternative translation metric that handles synonyms/stemming better.

---

## 3.4 Perplexity

**Perplexity** measures how surprised or uncertain a language model is when predicting text.

In simple terms:

```text
Perplexity = how confused the model is
```

Lower perplexity is better.

| Model | Perplexity | Interpretation |
|---|---:|---|
| Model A | 20 | Better |
| Model B | 50 | Worse |

Perplexity is closely related to cross-entropy loss.

Use perplexity when evaluating:

```text
language modeling
next-token prediction
model uncertainty
training quality
```

Do not use perplexity to directly evaluate retrieval quality.

### Exam Shortcut

```text
Lower perplexity = better next-token prediction
```

---

# 4. What Not To Use for Retrieval Quality

When the question asks about vector search, retrieval relevance, LSH, HNSW, ANN indexes, or RAG context quality, avoid metrics focused on generation or runtime behavior.

| Metric | Why It Is Not the Best Retrieval Metric |
|---|---|
| Perplexity | Evaluates language model prediction, not whether the right chunks were retrieved |
| Token generation latency | Measures speed, not semantic relevance |
| Temperature | Controls randomness, not retrieval quality |
| BLEU | Translation metric, not retrieval relevance |
| ROUGE | Summarization metric, not vector index quality |

---

# 5. Example: Evaluating LSH vs HNSW

If a question compares approximate nearest-neighbor indexing techniques such as LSH and HNSW, the goal is usually to evaluate which index retrieves more semantically relevant vectors.

Good evaluation methods:

```text
Measure cosine similarity against a labeled ground-truth query set.
Compute precision@k or recall@k using known relevant neighbors.
Use NDCG if ranking order matters.
```

Bad evaluation methods:

```text
Compare perplexity of downstream text generation.
Evaluate average token generation latency.
Raise model temperature.
```

Reason:

```text
The question is about retrieval quality, not generation quality or runtime speed.
```

---

# 6. Practical RAG Evaluation Workflow

A practical RAG evaluation workflow can look like this:

```text
1. Build a small SME-labeled gold set.
2. Run the retriever for each test question.
3. Compare retrieved chunks against gold chunks/sections.
4. Calculate precision@k, recall@k, NDCG, and hit rate.
5. Send retrieved context to the LLM.
6. Evaluate final answer quality using human review, LLM-as-judge, or reference-based metrics.
7. Track parameters and metrics in MLflow.
```

Useful MLflow parameters to log:

```text
chunk_size
chunk_overlap
embedding_model
top_k
similarity_threshold
index_type, such as HNSW or LSH
reranker_enabled
metadata_filters
```

Useful MLflow metrics to log:

```text
precision@5
recall@5
precision@10
recall@10
NDCG@k
latency
cost
answer_correctness
citation_accuracy
```

---

# 7. Exam Quick Cheat Sheet

## Metric Selection Cheat Sheet

| Exam Phrase | Choose This Metric |
|---|---|
| Machine translation quality with gold-standard translations | BLEU |
| Translation metric with synonyms/stemming alignment | METEOR |
| Summarization quality with reference summaries | ROUGE |
| Retrieval quality in RAG | precision@k, recall@k |
| Vector semantic similarity | cosine similarity |
| Ranking quality of retrieved results | NDCG |
| First relevant result should appear early | MRR |
| At least one relevant result in top k | hit rate@k |
| Language model uncertainty / next-token prediction | perplexity |
| Classification correctness | accuracy, precision, recall, F1 |
| Production request/response monitoring | inference tables |
| Experiment comparison during development | MLflow tracking/evaluation |

---

## Retrieval vs Generation Cheat Sheet

| Question Is About | Use |
|---|---|
| Did we retrieve the right chunks? | precision@k, recall@k, cosine similarity, NDCG |
| Did we generate a good translation? | BLEU |
| Did we generate a good summary? | ROUGE |
| Is the language model good at predicting text? | perplexity |
| Is the production app slow or failing? | latency/error monitoring, inference tables |

---

## Precision vs Recall Cheat Sheet

| Metric | Main Question | RAG Meaning |
|---|---|---|
| Precision@k | Of what I retrieved, how much was relevant? | Is the context clean? |
| Recall@k | Of what was relevant, how much did I retrieve? | Did I miss important context? |

Memory trick:

```text
Precision = purity of retrieved results
Recall    = coverage of relevant results
```

---

## Gold Dataset Cheat Sheet

Precision@k and recall@k usually require:

```text
representative test questions
known relevant chunks/documents/sections
SME or human validation
stable benchmark table
```

A small gold set is enough to start:

```text
25-50 high-quality questions
3-5 relevant sources per question
coverage across common and edge-case workflows
```

---

## Databricks / RAG Exam Memory

```text
Vector search / semantic relevance -> cosine similarity, precision@k, recall@k
RAG retrieval comparison           -> precision@k, recall@k, NDCG
Machine translation                -> BLEU
Summarization                      -> ROUGE
Language model uncertainty         -> perplexity
Build-time experiment tracking     -> MLflow
Production inference monitoring    -> inference tables
```

---

# 8. Final Summary

- Precision and recall evaluate retrieval quality.
- Precision@k measures how clean the top-k retrieved context is.
- Recall@k measures how much of the known relevant context was found.
- Precision@k and recall@k normally require a gold or labeled benchmark dataset.
- Gold sets are usually built from representative questions and SME-labeled relevant chunks, documents, sections, or answer spans.
- Cosine similarity evaluates semantic closeness between vectors.
- NDCG evaluates ranking quality when order matters.
- BLEU is the standard exam answer for machine translation with gold references.
- ROUGE is the standard exam answer for summarization with reference summaries.
- Perplexity evaluates model uncertainty / next-token prediction, not retrieval relevance.


===

BLEU   = checks exact word/phrase overlap
METEOR = checks overlap more flexibly, including meaning-related matches
=========

Why BLEU is Correct

BLEU (Bilingual Evaluation Understudy) is the most widely used automatic metric for benchmarking machine translation systems.

It measures similarity between a model‑generated translation and one or more high‑quality reference translations using n‑gram overlap.

It is efficient, widely supported, and standard in translation research and industry settings.

Why the Other Options Don’t Fit

B. NDCG → Used for ranking tasks (e.g., search relevance), not translation.

C. ROUGE → Designed for summarization evaluation, not translation accuracy.

D. Recall → Too simple; does not reflect translation fluency or adequacy.

E. METEOR → Reasonable alternative but less commonly used than BLEU as the primary benchmark.

F. Precision → Insufficient alone for evaluating full‑sentence translation quality.