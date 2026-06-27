# Chunking Strategies

## Summary

Selecting a chunking strategy involves understanding:

* Your data
* Your retrieval goals
* Your system constraints
* The type of questions users will ask

A good chunking strategy usually requires an **iterative experimental approach**. You test different chunk sizes, overlaps, and splitting methods, then evaluate retrieval quality using measurable metrics.

The goal is to find the best balance between:

```text
Context quality + retrieval accuracy + system efficiency
```

---

# 1. Types of Chunking Strategies

## A. Fixed-Size Chunking

### Description

Documents are split into chunks of a fixed number of tokens, words, or characters.

Example:

```text
Chunk 1 = first 500 tokens
Chunk 2 = next 500 tokens
Chunk 3 = next 500 tokens
```

### Advantages

* Simple to implement.
* Predictable chunk size.
* Easier to manage.
* Works well with token limits.
* Easy to tune and compare.

### Use Cases

Use fixed-size chunking when:

* Uniform context size is desired.
* Document structure is less important.
* You want a simple baseline.
* Speed and simplicity matter.

### Exam Shortcut

> Choose fixed-size chunking when the question emphasizes simplicity, predictable chunk size, or easy implementation.

---

## B. Semantic or Content-Based Chunking

### Description

Documents are split based on meaningful boundaries, such as:

* Sentences
* Paragraphs
* Sections
* Headings
* Natural topic changes

Instead of cutting every fixed number of tokens, this strategy tries to keep related information together.

### Advantages

* Produces more meaningful chunks.
* Preserves semantic coherence.
* Reduces the chance of cutting important context in the middle.
* Useful for better answer quality in RAG.

### Use Cases

Use semantic/content-based chunking when:

* Preserving meaning is important.
* The document has clear sections or paragraphs.
* You are working on summarization.
* You are building a question-answering system.
* You want retrieved chunks to be easier for the LLM to understand.

### Exam Shortcut

> Choose semantic chunking when the question emphasizes preserving meaning, natural boundaries, or coherent context.

---

## C. Overlap Chunking

### Description

Consecutive chunks share some tokens or text.

Example:

```text
Chunk 1: tokens 1–500
Chunk 2: tokens 451–950
Chunk 3: tokens 901–1400
```

Here, each chunk overlaps by 50 tokens.

### Advantages

* Preserves context across chunk boundaries.
* Reduces the chance of losing important information between chunks.
* Improves retrieval for questions where the answer spans two chunks.
* Helps maintain continuity.

### Use Cases

Use overlap chunking when:

* Context may span chunk boundaries.
* Questions require nearby information from different sections.
* You want to improve retrieval quality.
* The document has long explanations or multi-step concepts.

### Tradeoff

Overlap improves context, but it also increases:

* Storage
* Embedding cost
* Index size
* Retrieval redundancy

### Exam Shortcut

> Choose overlap chunking when the question emphasizes preserving context across chunk boundaries.

---

## D. Adaptive or Dynamic Chunking

### Description

Chunk size varies based on the content.

For example:

* Short/simple sections may become smaller chunks.
* Complex sections may become larger chunks.
* Tables, code blocks, or explanations may be handled differently.

### Advantages

* More flexible than fixed-size chunking.
* Balances context richness and efficiency.
* Can preserve complex ideas better.
* Useful when documents have uneven structure.

### Use Cases

Use adaptive/dynamic chunking when:

* Documents have variable structure.
* Some sections are simple and others are complex.
* Chunk size should depend on meaning or complexity.
* You want a more advanced strategy than fixed-size chunking.

### Exam Shortcut

> Choose adaptive chunking when the question says chunk size should vary based on content complexity.

---

# 2. Choosing the Right Chunking Strategy

## A. Align with Retrieval Goals

Choose chunking based on what retrieval needs to achieve.

| Goal                              | Better Strategy     |
| --------------------------------- | ------------------- |
| Speed and simplicity              | Fixed-size chunking |
| Preserve meaning                  | Semantic chunking   |
| Avoid losing boundary context     | Overlap chunking    |
| Handle complex/variable documents | Adaptive chunking   |

---

## B. Consider System Constraints

Chunking affects cost and performance.

| Constraint                    | Better Choice                 |
| ----------------------------- | ----------------------------- |
| Limited storage               | Smaller chunks, less overlap  |
| Limited compute               | Fixed-size chunks             |
| Need higher retrieval quality | Semantic chunks with overlap  |
| Need more context per result  | Larger chunks                 |
| Need less redundancy          | Smaller overlap or no overlap |

---

## C. Experiment and Use Objective Metrics

The best chunking strategy is usually found through experimentation.

Common retrieval metrics include:

| Metric      | Meaning                                                                                      |
| ----------- | -------------------------------------------------------------------------------------------- |
| Recall@K    | Did the correct/relevant chunk appear in the top K results?                                  |
| Precision@K | How many of the top K retrieved chunks were actually relevant?                               |
| NDCG        | Measures ranking quality, giving more credit when relevant chunks appear higher in the list. |

### Exam Shortcut

> The best chunking strategy should be selected through evaluation, not guessing.

---

## D. Balance Context and Efficiency

Chunking is a tradeoff.

| Choice          | Benefit                     | Cost                                         |
| --------------- | --------------------------- | -------------------------------------------- |
| Larger chunks   | More context                | More tokens, possibly less precise retrieval |
| Smaller chunks  | More precise retrieval      | May lose context                             |
| Overlap         | Better continuity           | More storage and duplicate content           |
| Semantic chunks | Better meaning preservation | More complex implementation                  |

---

# 3. Common Exam Traps

## Trap 1: Bigger chunks are not always better

Larger chunks provide more context, but they can reduce retrieval precision.

Example:

```text
Large chunk = more context but may contain unrelated information
Small chunk = more focused but may miss surrounding context
```

---

## Trap 2: Smaller chunks are not always better

Smaller chunks may retrieve precise information, but they can break meaning.

Example:

```text
A definition is in one chunk.
The explanation is in the next chunk.
The LLM may not see both unless overlap or good retrieval is used.
```

---

## Trap 3: Overlap improves context but increases cost

Overlap can improve retrieval quality, but it creates duplicate text.

This increases:

* Number of chunks
* Embedding cost
* Vector index size
* Retrieval redundancy

---

## Trap 4: Chunking is not the same as embedding

| Step       | Meaning                              |
| ---------- | ------------------------------------ |
| Chunking   | Splits documents into smaller pieces |
| Embedding  | Converts chunks into vectors         |
| Retrieval  | Finds similar chunks                 |
| Generation | LLM uses retrieved chunks to answer  |

---

# 4. One-Line Memory Guide

| If the question says...        | Choose...                       |
| ------------------------------ | ------------------------------- |
| Simple and predictable         | Fixed-size chunking             |
| Preserve meaning               | Semantic/content-based chunking |
| Context across boundaries      | Overlap chunking                |
| Variable document complexity   | Adaptive/dynamic chunking       |
| Improve retrieval quality      | Experiment and evaluate         |
| Limited compute/storage        | Smaller chunks, less overlap    |
| Answer spans multiple sections | Overlap or larger chunks        |
| Better ranking evaluation      | Recall@K, Precision@K, NDCG     |

---

# 5. Final Summary

Choosing a chunking strategy depends on:

* Document structure
* Retrieval goals
* Token limits
* Cost constraints
* Desired answer quality

The main strategies are:

* **Fixed-size chunking**: simple and predictable.
* **Semantic chunking**: preserves meaning.
* **Overlap chunking**: maintains context across boundaries.
* **Adaptive chunking**: adjusts chunk size based on content complexity.

The best approach is usually found by testing different strategies and measuring retrieval quality using metrics like:

* Recall@K
* Precision@K
* NDCG

The key exam idea is:

> Chunking directly affects retrieval quality, cost, and final answer quality in a RAG system.
