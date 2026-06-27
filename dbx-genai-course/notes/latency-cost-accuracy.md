# Latency, Cost, and Accuracy Tradeoffs

## Summary

In GenAI and RAG systems, model choices affect three major factors:

1. **Latency** — how fast the system responds
2. **Cost** — how much compute, storage, and inference cost are required
3. **Accuracy** — how good or relevant the model output is

The main tradeoff is:

```text
Higher accuracy often requires larger models, larger embeddings, or larger context windows.
But these usually increase latency and cost.
```

---

# 1. Embedding Model Dimension Size

## What Is Embedding Dimension?

An embedding is a vector representation of text.

The **embedding dimension** is the number of values in that vector.

Example:

```text
384-dimensional embedding  = vector with 384 numbers
1536-dimensional embedding = vector with 1536 numbers
```

A higher-dimensional embedding can capture more semantic detail, but it also requires more storage and compute.

---

## Impact on Accuracy

Higher-dimensional embeddings can often capture more nuanced information.

They may better represent:

* Meaning
* Similarity
* Domain-specific terms
* Subtle relationships
* Fine-grained distinctions

This can improve retrieval quality in RAG systems.

Example:

```text
A 1536-dimensional embedding may capture more semantic nuance than a 384-dimensional embedding.
```

---

## Impact on Latency

Higher-dimensional embeddings usually increase latency because:

* More values must be generated.
* More values must be stored.
* More values must be compared during vector search.
* More compute is required per operation.

So:

```text
Higher dimension → more computation → higher latency
```

---

## Impact on Cost

Higher-dimensional embeddings can increase cost because they require:

* More storage
* More memory
* More vector index capacity
* More compute during search
* More network transfer

So:

```text
Higher dimension → more storage + compute → higher cost
```

---

## Why Use Large-Dimensional Embeddings?

Even though they cost more, larger embeddings may be useful when accuracy is more important than cost or latency.

### Benefits

* Richer data representation
* Better semantic understanding
* Improved retrieval precision
* Better performance on complex questions
* Better handling of subtle relationships

### Good Use Cases

Use larger-dimensional embeddings when:

* Accuracy is critical.
* Retrieval quality is the top priority.
* The domain is complex.
* The application is high-stakes.
* Fine-grained semantic distinctions matter.

Examples:

* Healthcare
* Legal
* Financial analysis
* Complex technical documents
* Enterprise knowledge search

---

## When to Use Smaller-Dimensional Embeddings

Use smaller-dimensional embeddings when:

* Low latency is important.
* Cost must be minimized.
* Search needs to be fast.
* The task is simple.
* Slightly lower accuracy is acceptable.

Examples:

* Simple FAQ search
* Low-cost prototypes
* High-volume applications
* Real-time user-facing apps

---

## Embedding Dimension Summary

| Aspect   | Effect of Larger Embedding Dimension                        |
| -------- | ----------------------------------------------------------- |
| Latency  | Increases because more values must be processed             |
| Cost     | Increases because storage, memory, and compute grow         |
| Accuracy | Often improves because more semantic detail can be captured |

### Exam Shortcut

> Larger embedding dimension usually improves retrieval quality, but increases latency and cost.

---

# 2. Model Size

## What Is Model Size?

Model size refers to how large a machine learning model is.

It is often related to:

* Number of parameters
* Memory footprint
* Number of layers
* Compute requirements
* Size on disk, such as MB or GB

Example:

```text
A 70B parameter model is larger than a 7B parameter model.
```

---

## Impact on Latency

Latency is the time it takes for a model to produce a response after receiving input.

Larger models usually have higher latency because:

* They perform more computations.
* They require more memory.
* They may need larger or more expensive hardware.
* Inference takes longer.

So:

```text
Larger model → more computation → slower inference
```

---

## Impact on Cost

Larger models usually cost more to run because they need more:

* GPU/CPU resources
* Memory
* Storage
* Serving infrastructure
* Inference time

In cloud environments, this often means higher operational cost.

So:

```text
Larger model → more compute + memory → higher cost
```

---

## Impact on Accuracy

Larger models can often capture more complex patterns.

They may perform better on:

* Reasoning
* Summarization
* Complex question-answering
* Code generation
* Multi-step tasks
* Nuanced language understanding

However, bigger is not always better.

After a certain point, accuracy gains may show **diminishing returns**, especially if:

* The task is simple.
* The data is limited.
* The prompt is poor.
* Retrieval quality is weak.
* The model is not well matched to the task.

---

## Model Size Summary

| Aspect   | Effect of Larger Model Size                                      |
| -------- | ---------------------------------------------------------------- |
| Latency  | Increases because inference is slower                            |
| Cost     | Increases because more compute and memory are needed             |
| Accuracy | Usually improves for complex tasks, but with diminishing returns |

### Exam Shortcut

> Larger models often improve accuracy, but increase latency and cost.

---

# 3. Token Context Window

## What Is a Token?

A token is a basic unit of text.

A token can be:

* A word
* Part of a word
* A punctuation mark
* A special symbol

Example:

```text
"Databricks is useful" may be split into multiple tokens.
```

---

## What Is a Context Window?

The **context window** is the maximum number of tokens a model can process at once.

Example:

```text
A model with a 4,000-token context window can process up to 4,000 tokens in one request.
```

The context window includes the input prompt, retrieved context, instructions, and sometimes the generated output depending on the model/API design.

---

## Impact on Latency

Larger context windows can increase latency because the model has to process more tokens.

So:

```text
Larger context window → more tokens processed → higher latency
```

Smaller context windows are faster but may not include enough information.

---

## Impact on Cost

Larger context windows can increase cost because model pricing is often based on token usage.

More tokens means:

* More input processing cost
* More memory usage
* More compute
* Higher serving cost

So:

```text
Larger context window → more tokens → higher cost
```

---

## Impact on Accuracy

Larger context windows can improve accuracy when the task requires more information.

They are useful for:

* Long document summarization
* Long conversations
* Multi-document reasoning
* RAG with many retrieved chunks
* Detailed analysis

However, larger context windows do not guarantee better answers.

If irrelevant content is included, the model may become distracted or produce worse answers.

---

## Context Window Summary

| Aspect   | Effect of Larger Token Context Window                                         |
| -------- | ----------------------------------------------------------------------------- |
| Latency  | Increases because more tokens are processed                                   |
| Cost     | Increases because more compute and token usage are required                   |
| Accuracy | Can improve when useful context is included, but may have diminishing returns |

### Exam Shortcut

> Larger context windows allow more input context, but increase latency and cost.

---

# 4. Accuracy vs Cost vs Latency Tradeoff

## General Rule

| Choice                      | Accuracy                           | Latency | Cost   |
| --------------------------- | ---------------------------------- | ------- | ------ |
| Larger embedding dimension  | Usually higher                     | Higher  | Higher |
| Smaller embedding dimension | Usually lower/moderate             | Lower   | Lower  |
| Larger model                | Usually higher                     | Higher  | Higher |
| Smaller model               | Usually lower/moderate             | Lower   | Lower  |
| Larger context window       | Can be higher                      | Higher  | Higher |
| Smaller context window      | Can be lower if context is missing | Lower   | Lower  |

---

# 5. Choosing Based on Priority

## If Low Latency Is the Priority

Choose:

* Smaller models
* Smaller embedding dimensions
* Smaller context windows
* Efficient batching
* Fewer retrieved chunks
* Shorter prompts

Best when:

* User-facing response speed matters.
* Real-time interaction matters.
* Slightly lower accuracy is acceptable.

---

## If Low Cost Is the Priority

Choose:

* Cheaper models
* Smaller models
* Smaller embedding dimensions
* Less token usage
* Fewer chunks
* Reduced overlap
* Smaller context windows

Best when:

* Application has high traffic.
* Budget is limited.
* The task does not require deep reasoning.

---

## If Accuracy Is the Priority

Choose:

* Stronger models
* Larger embedding dimensions
* Better retrieval models
* Better chunking strategy
* Enough context window
* More relevant retrieved context

Best when:

* The domain is complex.
* Mistakes are costly.
* Retrieval precision is important.
* Answer quality matters more than speed/cost.

---

# 6. Common Exam Traps

## Trap 1: Higher Accuracy Usually Costs More

If a question asks for the highest accuracy, the answer may involve a larger model, larger dimension, or larger context window.

But if the question asks for low latency or low cost, the answer is usually the smaller or more efficient option.

---

## Trap 2: Larger Context Is Not Always Better

A larger context window helps only when the extra context is relevant.

Irrelevant context can:

* Increase cost
* Increase latency
* Distract the model
* Reduce answer quality

---

## Trap 3: Higher Embedding Dimension Is Not Always Required

Higher-dimensional embeddings may improve retrieval quality, but a smaller embedding may be enough for simple search tasks.

---

## Trap 4: Model Size and Embedding Dimension Are Related but Not the Same

| Concept             | Meaning                                           |
| ------------------- | ------------------------------------------------- |
| Model size          | Number of model parameters or memory footprint    |
| Embedding dimension | Size of the vector output from an embedding model |

A model can be large but still output a fixed-size embedding vector.

---

# 7. One-Line Memory Guide

| If the question says...     | Think...                                                        |
| --------------------------- | --------------------------------------------------------------- |
| Lowest latency              | Smaller model, smaller dimension, shorter context               |
| Lowest cost                 | Smaller model, fewer tokens, smaller dimension                  |
| Highest accuracy            | Larger/better model, more relevant context, stronger embeddings |
| Better retrieval quality    | Better embedding model, good chunking, enough dimension         |
| Faster vector search        | Smaller dimension, fewer vectors                                |
| More semantic nuance        | Larger embedding dimension                                      |
| Long document understanding | Larger context window                                           |
| Real-time app               | Lower latency model setup                                       |
| High-stakes domain          | Prioritize accuracy over cost                                   |

---

# 8. Final Summary

Latency, cost, and accuracy are connected.

In general:

```text
Larger / richer model setup → better accuracy, but higher latency and cost
Smaller / simpler model setup → lower latency and cost, but may reduce accuracy
```

For the exam, remember:

* **Embedding dimension** affects vector quality, storage, search cost, and latency.
* **Model size** affects inference quality, compute cost, and response time.
* **Context window** affects how much information the model can process, but also affects token cost and latency.

The key exam idea is:

> Choose the smallest and cheapest setup that still meets the accuracy requirement.
