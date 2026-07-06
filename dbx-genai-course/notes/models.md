# Databricks GenAI Associate Certification: Model Selection Cheat Sheet

## 1. How to Think About Model Questions

In the exam, model-selection questions are usually **scenario-based**.

Do not memorize models randomly. Instead, memorize them by **purpose**:

| Need                             | Best Model Type     |
| -------------------------------- | ------------------- |
| Search / similarity / retrieval  | Embedding model     |
| Code generation                  | Code-specific LLM   |
| Long document / large context    | Long-context LLM    |
| Classification / lightweight NLP | Encoder model       |
| General answer generation        | General-purpose LLM |

---

# 2. Models Organized by Category

## A. Llama Family

### Llama 2 70B

**What it is:**

* Open-weight large language model from Meta.
* The `70B` means it has 70 billion parameters.
* Good for general text generation, reasoning, summarization, and chat-style tasks.
* Older model compared to newer long-context models.
* Context window is usually around 4,000 tokens in many exam-style references.

**Best exam answer when the scenario says:**

* Need a strong open-source/open-weight general LLM.
* Need general text generation.
* Need chatbot-style response generation.

**Do not choose it when:**

* The question specifically asks for code generation.
* The question specifically asks for largest context window.
* The question asks for embeddings or semantic search.

---

### CodeLlama-34B

**What it is:**

* Code-specialized model from the Llama family.
* Designed for code generation, code completion, debugging, and programming-language tasks.
* Supports multiple programming languages.
* The `34B` means it has 34 billion parameters.

**Best exam answer when the scenario says:**

* Generate code.
* Complete code.
* Debug code.
* Translate code.
* Help developers with programming tasks.

**Exam shortcut:**

> If the question says **code generation**, choose **CodeLlama-34B** over general Llama or MPT models.

---

## B. MPT Family

MPT models come from MosaicML, which became part of Databricks.

---

### MPT-30B

**What it is:**

* Open-source/open-weight LLM from MosaicML.
* The `30B` means it has 30 billion parameters.
* Known in many Databricks mock-test questions for supporting larger context windows.
* Useful for long-input tasks like summarizing large documents or research papers.

**Best exam answer when the scenario says:**

* Large context window.
* Long document summarization.
* Need to process extensive input text.
* Need to analyze large documents or research papers.

**Exam shortcut:**

> If the question compares **MPT-30B**, **Llama2-70B**, and **DistilBERT**, and asks for **large context window**, choose **MPT-30B**.

**Important trap:**

> More parameters does not always mean larger context window.
> Llama2-70B has more parameters than MPT-30B, but MPT-30B may be the better answer for long-context scenarios.

---

### MPT-7B

**What it is:**

* Smaller general-purpose MPT model.
* The `7B` means it has 7 billion parameters.
* Less powerful than MPT-30B.
* More lightweight and cheaper to run.

**Best exam answer when the scenario says:**

* Need a smaller model.
* Need lower cost.
* Need basic general-purpose generation.
* Quality is less critical than efficiency.

**Do not choose it when:**

* The task needs high-quality code generation.
* The task needs very strong reasoning.
* The task needs a large context window and MPT-30B is available.

---

## C. BERT / DistilBERT Family

These are usually **encoder models**, not generative LLMs.

---

### DistilBERT

**What it is:**

* Smaller, distilled version of BERT.
* BERT was developed by Google.
* DistilBERT is designed to be faster and less resource-intensive while keeping much of BERT’s performance.
* Good for classification and understanding tasks.
* Not designed for open-ended text generation.

**Best exam answer when the scenario says:**

* Text classification.
* Sentiment analysis.
* Intent classification.
* Entity extraction.
* Lightweight NLP understanding.
* Simple question-answering or classification-style tasks.

**Do not choose it when:**

* The task asks for chatbot responses.
* The task asks for long-form generation.
* The task asks for summarizing long documents.
* The task asks for large context window.
* The task asks for embeddings/vector search.

**Exam shortcut:**

> DistilBERT is for **understanding/classification**, not for generating rich answers.

### DBRX

DBRX was released by Databricks as an open LLM, and Databricks says it was pretrained with a maximum context length of 32K tokens.

That makes it a strong fit for use cases like:

large document understanding
long conversations
RAG with many retrieved chunks
summarizing long reports
multi-page technical documents

### Whisper Large v3

Whisper Large v3 is an OpenAI speech-to-text model.

It is used for:

audio → text

Examples:

meeting recording → transcript
customer call audio → text
YouTube/audio file → captions
speech in another language → translated English text

OpenAI’s Whisper repo describes Whisper as a general-purpose speech recognition model that can do multilingual speech recognition, speech translation, and language identification.
---

## D. Embedding Models

Embedding models are used for retrieval, search, and similarity. They are not mainly used to generate final answers.

---

### BGE-Large

**What it is:**

* Embedding model.
* Converts text into vector representations.
* Used for semantic search, retrieval, similarity search, clustering, and RAG pipelines.
* Not a generative model.

**Best exam answer when the scenario says:**

* Semantic search.
* Vector search.
* Similarity search.
* Retrieval.
* RAG index.
* Find relevant documents.
* Convert text into embeddings.

**Do not choose it when:**

* The task asks for generating final answers.
* The task asks for summarization.
* The task asks for code generation.
* The task asks for chatbot-style response generation.

**Exam shortcut:**

> BGE-Large retrieves relevant information.
> An LLM generates the final response.



---

# 3. Exam Decision Tree

Use this simple flow in the exam:

## Step 1: Is the task about retrieval, semantic search, vector search, or RAG indexing?

Choose:

> **BGE-Large** or another embedding model.

Example keywords:

* Semantic search
* Vector search
* Similarity search
* Embeddings
* Retrieval
* RAG index
* Find similar documents

---

## Step 2: Is the task about code generation?

Choose:

> **CodeLlama-34B**

Example keywords:

* Generate code
* Complete code
* Debug code
* Translate code
* Programming languages
* Developer assistant

---

## Step 3: Is the task about large context or long documents?

Choose:

> **MPT-30B**

Example keywords:

* Large context window
* Long documents
* Research papers
* Extensive input text
* Summarize large files
* Analyze long documents

---

## Step 4: Is the task about classification or lightweight NLP?

Choose:

> **DistilBERT**

Example keywords:

* Classification
* Sentiment analysis
* Intent detection
* Entity extraction
* Lightweight NLP
* Fast inference

---

## Step 5: Is the task general text generation?

Choose:

> **Llama 2 70B** or a general-purpose MPT model.

Example keywords:

* General answer generation
* Chatbot
* Summarization
* Reasoning
* Open-ended response

---

# 4. Quick Memory Table

| Scenario                    | Best Answer   |
| --------------------------- | ------------- |
| Semantic search             | BGE-Large     |
| Vector embeddings           | BGE-Large     |
| RAG retrieval               | BGE-Large     |
| Code generation             | CodeLlama-34B |
| Code debugging              | CodeLlama-34B |
| Long document summarization | MPT-30B       |
| Large context window        | MPT-30B       |
| Lightweight classification  | DistilBERT    |
| Sentiment analysis          | DistilBERT    |
| General chatbot generation  | Llama 2 70B   |
| Smaller cheaper LLM         | MPT-7B        |

---

# 5. Common Exam Traps

## Trap 1: Large model vs large context

Do not assume the model with more parameters has the largest context window.

Example:

* **Llama2-70B** has more parameters than **MPT-30B**.
* But if the question asks for **large context window**, the expected answer may be **MPT-30B**.

---

## Trap 2: Embedding model vs generative model

**BGE-Large** is an embedding model.

It is good for:

* Search
* Similarity
* Retrieval
* RAG indexing

It is not the best choice for:

* Writing final answers
* Summarization
* Chatbot responses
* Code generation

---

## Trap 3: DistilBERT vs LLM

**DistilBERT** is not a modern generative chat model.

It is good for:

* Classification
* Lightweight NLP
* Text understanding

It is not good for:

* Long-form generation
* Long context
* Open-ended chat
* Code generation

---

## Trap 4: General LLM vs code LLM

If the task is code-specific, choose the code-specialized model.

Example:

| Model         | Best Use           |
| ------------- | ------------------ |
| Llama 2 70B   | General generation |
| CodeLlama-34B | Code generation    |

---

# 6. One-Line Exam Answers

Use these short answers to remember quickly:

* **DistilBERT**: Small, fast BERT-style model for classification and NLP understanding.
* **Llama2-70B**: Large general-purpose LLM from Meta.
* **MPT-30B**: Good choice for long-context and large-document tasks.
* **MPT-7B**: Smaller, cheaper general-purpose LLM.
* **BGE-Large**: Embedding model for semantic search and retrieval.
* **CodeLlama-34B**: Best for code generation and programming tasks.

---

# 7. Final Exam Shortcut

When reading a question, look for the keyword:

| Keyword in Question | Think         |
| ------------------- | ------------- |
| Embeddings          | BGE-Large     |
| Semantic search     | BGE-Large     |
| Retrieval           | BGE-Large     |
| RAG index           | BGE-Large     |
| Code                | CodeLlama-34B |
| Long context        | MPT-30B       |
| Large document      | MPT-30B       |
| Classification      | DistilBERT    |
| Lightweight NLP     | DistilBERT    |
| General generation  | Llama2-70B    |
| Smaller / cheaper   | MPT-7B        |

---

# 8. Summary

The most important thing is to match the model to the task:

* Use **BGE-Large** for retrieval and embeddings.
* Use **CodeLlama-34B** for code.
* Use **MPT-30B** for large context.
* Use **DistilBERT** for lightweight classification.
* Use **Llama2-70B** for general generation.
* Use **MPT-7B** when a smaller general-purpose model is enough.
 ===


 What advantage does the Instruct variant of CodeLlama 34B provide compared to the base CodeLlama 34B model? ( true or false)

Statement - The Instruct variant is fine‑tuned to follow natural‑language instructions more accurately, making it better suited for interactive coding workflows such as code generation, debugging, and explanation—without requiring prompt engineering or fine‑tuning.