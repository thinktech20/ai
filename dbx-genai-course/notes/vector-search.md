# LSH vs HNSW for Semantic Relevance

## What Are LSH and HNSW?

LSH and HNSW are both **vector index techniques** used to make vector search faster.

In a RAG system, documents are converted into embeddings and stored in a vector database.

```text
User question
   ↓
Create query embedding
   ↓
Search vector index
   ↓
Retrieve top matching chunks
   ↓
Send chunks to LLM

LSH
Meaning

LSH = Locality-Sensitive Hashing

LSH uses hashing to place similar vectors into the same or nearby buckets.

Similar vectors → same bucket
Different vectors → different buckets

When a query comes in, the system searches the most likely buckets instead of the full vector database.

Simple Analogy

Think of LSH like sorting books into rough topic bins:

Turbine failure
Maintenance schedule
Inspection rules
Repair history

When someone asks a question, you search the most relevant bin instead of the whole library.

Strengths
Fast approximate search
Conceptually simple
Can scale to large datasets
Often lower memory than graph-based methods
Weaknesses
Can miss semantically relevant results
Retrieval quality can be less stable
May need multiple hash tables for better recall
Less effective for nuanced semantic similarity
Exam Shortcut
LSH = hash similar vectors into buckets
HNSW
Meaning

HNSW = Hierarchical Navigable Small World

HNSW builds a graph where each vector is connected to nearby vectors.

Search starts at a higher-level graph and navigates toward closer and closer vectors.

Start broad
   ↓
Move through nearby vector connections
   ↓
Zoom into best neighborhood
   ↓
Return nearest vectors
Simple Analogy

Think of HNSW like navigation on a map:

Highways → main roads → local streets → destination

It starts with a broad search and gradually moves toward the closest matching vectors.

Strengths
Usually stronger semantic retrieval quality
High recall@k
Good precision@k
Common in modern vector databases
Strong for nearest-neighbor search
Weaknesses
Uses more memory
Index creation can be heavier
Needs tuning for speed vs recall
Exam Shortcut
HNSW = graph-based vector search, usually better semantic recall
LSH vs HNSW Comparison
Area	LSH	HNSW
Full name	Locality-Sensitive Hashing	Hierarchical Navigable Small World
Main idea	Hash vectors into buckets	Build graph of nearby vectors
Search style	Bucket lookup	Graph traversal
Retrieval quality	Moderate	Usually higher
Semantic relevance	Can miss nuanced matches	Usually better
Recall@k	Often lower	Often higher
Precision@k	Less stable	Often stronger
Speed	Fast	Fast, depending on tuning
Memory usage	Often lower	Higher
Best for	Simple fast approximate search	High-quality semantic search
Which Is Better for Semantic Relevance?

For semantic relevance, HNSW is usually better.

Why?

Because HNSW is designed to navigate through neighborhoods of similar vectors and often finds closer semantic matches than LSH.

Better semantic relevance
→ usually HNSW

LSH can be fast, but because it depends on hash buckets, it may miss relevant vectors that fall into different buckets.

How to Evaluate LSH vs HNSW

Do not compare them only by speed.

For RAG, the main question is:

Which index retrieves the most relevant chunks?

Use retrieval quality metrics such as:

cosine similarity against labeled ground-truth results
precision@k
recall@k
hit rate
MRR
NDCG
Example
Query
What are the known causes of compressor blade cracking?
Gold Relevant Chunks
chunk_10
chunk_18
chunk_25
LSH Top 5 Results
chunk_10
chunk_44
chunk_90
chunk_102
chunk_200

LSH found only 1 relevant chunk.

Relevant found = 1 out of 3
HNSW Top 5 Results
chunk_10
chunk_18
chunk_25
chunk_71
chunk_88

HNSW found all 3 relevant chunks.

Relevant found = 3 out of 3

In this example, HNSW has better semantic retrieval.

Metrics to Use
Precision@k

Precision@k asks:

Out of the top k retrieved chunks, how many were relevant?

Example:

Top 5 retrieved chunks = 5
Relevant retrieved chunks = 4

Precision@5 = 4 / 5 = 80%

Precision is about how clean the retrieved context is.

High precision means the LLM receives less irrelevant context.

Recall@k

Recall@k asks:

Out of all relevant chunks that should have been found, how many were retrieved in the top k?

Example:

Total relevant chunks = 10
Relevant chunks retrieved in top 5 = 4

Recall@5 = 4 / 10 = 40%

Recall is about not missing important relevant context.

For RAG, recall is important because if the retriever misses the right chunk, the LLM may not have enough information to answer correctly.

Cosine Similarity

Cosine similarity measures how close two vectors are in direction.

Higher cosine similarity
→ stronger semantic similarity

Use it when comparing retrieved vectors against known relevant vectors.

What Not to Use for This Comparison

Do not use these as primary metrics for LSH vs HNSW semantic relevance:

Metric	Why Not
Perplexity	Measures language model prediction quality, not retrieval quality
Temperature	Controls generation randomness, not retrieval relevance
Token generation latency	Measures LLM response speed, not vector search relevance
BLEU	Used mainly for machine translation
ROUGE	Used mainly for summarization
Exam Shortcut
LSH
= hash-based approximate vector search
= fast, but may miss relevant semantic matches

HNSW
= graph-based approximate vector search
= usually better semantic relevance and recall

For questions asking how to compare LSH and HNSW for semantic relevance, choose:

cosine similarity with ground truth
precision@k
recall@k

Avoid answers focused on:

perplexity
temperature
token generation latency

Those measure generation behavior, not retrieval quality.