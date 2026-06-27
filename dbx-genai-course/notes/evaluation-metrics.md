# Retrieval and Response Accuracy Metrics

## Retrieval Relevance Metrics
- **Precision**
  - Measures the proportion of retrieved documents that are relevant.
  - **Formula:** `Precision = (Number of relevant documents retrieved) / (Total documents retrieved)`
  - **Example:** If a system retrieves 10 documents, and 7 are relevant, precision is 0.7.

- **Recall**
  - Measures the proportion of relevant documents that are retrieved out of all relevant documents available.
  - **Formula:** `Recall = (Number of relevant documents retrieved) / (Total relevant documents in the dataset)`
  - **Example:** If there are 20 relevant documents in total, and the system retrieves 15 of them, recall is 0.75.

## Response Accuracy Metrics
- **BLEU (Bilingual Evaluation Understudy)**
  - A metric used to evaluate the quality of generated text by comparing it to one or more reference texts.
  - It considers n-grams overlap (sequential word groups), giving higher scores for closer matches.
  - Commonly used in machine translation and text generation.

- **ROUGE (Recall-Oriented Understudy for Gisting Evaluation)**
  - Focuses on recall and measures the overlap of n-grams, word sequences, or summaries between generated and reference texts.
  - Used for evaluating summaries, translations, and other natural language generation tasks.
  - ROUGE is an important metric used in Natural Language Processing, especially for evaluating the quality of generated summaries. It specifically measures how well the generated summary aligns with a reference summary. By analyzing recall, precision, and F1 score, ROUGE captures the overlap between these two summaries.

  - Recall indicates how much of the reference summary's content is covered in the generated summary, reflecting information retention. Precision, on the other hand, measures how much of the generated summary is relevant to the reference, showcasing the quality of generated content. The F1 score is the harmonic mean of recall and precision, providing a single metric that balances both aspects.

Using ROUGE in your application helps ensure that the generated summaries are not only relevant but also informative, reflecting the key points from the original technical articles. Understanding these concepts will enhance your ability to assess and improve your summarization model effectively.

## Summary
- Retrieval relevance metrics like precision and recall assess how well the system retrieves pertinent data.
- Response accuracy metrics like BLEU and ROUGE evaluate the correctness and quality of generated responses by comparing them to reference texts.

---

## Examples of Metric Calculations in Practice

### Retrieval Relevance Metrics Example Scenario:
Suppose a retrieval system is tasked with finding relevant documents related to a query.

#### Precision Example:
- The system retrieves 8 documents.
- Out of these, 5 are actually relevant, and 3 are not.
- `Precision = Relevant retrieved documents / Total retrieved documents = 5 / 8 = 0.625`
- This indicates that **62.5%** of the retrieved documents are relevant.

#### Recall Example:
- There are **10** relevant documents available in total.
- The system retrieves **7** of these relevant documents.
- `Recall = Relevant retrieved documents / Total relevant documents = 7 / 10 = 0.7`
- So, the system retrieved **70%** of all relevant documents.

### Response Accuracy Metrics Example Scenario:
Evaluating the quality of a generated response in a chatbot.

#### BLEU Example:
- Reference response: "The internet connection is down."
- Generated response: "The internet is not working."
- BLEU evaluates how many n-grams (e.g., bigrams, trigrams) overlap between the generated text and reference.
- Suppose BLEU score is **0.45** (on a scale from *0 to 1*), indicating moderate similarity.

#### ROUGE Example:
- Reference summary: "The system experienced connectivity issues."
- Generated summary: "The system had connectivity problems."
to measure overlap of n-grams,
a higher ROUGE score suggests close match with reference text. a higher ROUGE score indicates better similarity between generated content and reference content.
---
the following code snippets demonstrate how to compute these metrics programmatically using Python libraries:
below each snippet is explained briefly about setup requirements or usage notes.


### Explanation of BLEU and ROUGE:
#### BLEU (Bilingual Evaluation Understudy):

Designed primarily for machine translation.
It compares the n-grams of the generated text to reference texts to measure similarity.
It emphasizes precision, ensuring the generated content includes relevant parts of the reference.
Less suitable for assessing semantic accuracy or domain relevance in summaries.

#### ROUGE (Recall-Oriented Understudy for Gisting Evaluation):

Specifically tailored for evaluating summaries.
Measures recall of overlapping n-grams between system and reference summaries, emphasizing content coverage.
More aligned with assessing semantic accuracy and relevance in summarization tasks.


# Perplexity

## What is Perplexity?

**Perplexity** is a common metric used to evaluate language models.

It measures how well a probabilistic model predicts a sample of text.

In simple terms:

> Perplexity tells us how “surprised” or “uncertain” a language model is when predicting the next word or token.

---

## How Perplexity Is Used

### 1. Measure of Uncertainty

Perplexity quantifies the model’s uncertainty in predicting the next word or token in a sequence.

* **Lower perplexity** means the model is more confident.
* **Higher perplexity** means the model is more uncertain.

### Exam Shortcut

> Lower perplexity = better prediction quality.

---

### 2. Model Evaluation

Perplexity is used to compare different language models.

A model with lower perplexity is generally considered better at predicting language on the given dataset.

Example:

| Model   | Perplexity | Interpretation |
| ------- | ---------: | -------------- |
| Model A |         20 | Better         |
| Model B |         50 | Worse          |

Model A is better because it has lower perplexity.

---

### 3. Training and Optimization

During training, perplexity is often monitored to understand how well the model is learning.

As training improves, perplexity should usually decrease.

However, perplexity itself is not usually the direct loss function. It is closely related to cross-entropy loss.

### Important Note

> Perplexity is derived from cross-entropy loss.
> Lower cross-entropy usually means lower perplexity.

---

## Why Perplexity Is Important

Perplexity is important because:

* It gives a single numeric score for language model quality.
* It helps compare language models.
* It shows how well a model fits the text data.
* It helps guide model improvements during training.
* It is useful for evaluating next-token prediction performance.

---

## Common Exam Understanding

For the exam, remember:

| Concept           | Meaning                                   |
| ----------------- | ----------------------------------------- |
| Perplexity        | Measures model uncertainty                |
| Lower perplexity  | Better language prediction                |
| Higher perplexity | Worse language prediction                 |
| Used for          | Evaluating language models                |
| Related to        | Cross-entropy loss                        |
| Best suited for   | Language modeling / next-token prediction |

---

## Simple Memory Trick

> Perplexity = how confused the model is.

So:

```text
Low perplexity  = less confused = better model
High perplexity = more confused = worse model
```

---

## Final Summary

Perplexity measures how well a language model predicts text.

* It measures uncertainty.
* Lower perplexity is better.
* It is used to evaluate and compare language models.
* It is closely related to cross-entropy loss.
* It helps determine how well the model fits the data.
