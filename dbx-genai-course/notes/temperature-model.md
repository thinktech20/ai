# Temperature in Language Models

## What Is Temperature?

**Temperature** is a parameter that controls the randomness or creativity of a language model’s generated output.

In simple terms:

> Temperature controls how predictable or creative the model’s response will be.

---

# 1. How Temperature Works

When a language model generates text, it predicts the next token based on probabilities.

A token can be:

* A word
* Part of a word
* A punctuation mark
* A symbol

Temperature changes how the model uses these probabilities.

---

## Low Temperature

A lower temperature makes the model more focused on the most likely next tokens.

This produces responses that are:

* More deterministic
* More predictable
* More conservative
* More factual
* Less creative

Example use cases:

* Factual Q&A
* Code generation
* Safety-critical responses
* Summarization
* Data extraction
* Customer support answers

---

## High Temperature

A higher temperature makes the model more willing to choose less likely tokens.

This produces responses that are:

* More random
* More creative
* More diverse
* Less predictable
* Sometimes less coherent

Example use cases:

* Brainstorming
* Creative writing
* Marketing copy
* Story generation
* Idea generation

---

# 2. Typical Temperature Values

| Temperature Range | Behavior                          | Best For                             |
| ----------------- | --------------------------------- | ------------------------------------ |
| 0.0 - 0.2         | Very focused and deterministic    | Factual answers, extraction, code    |
| 0.2 - 0.5         | Precise and conservative          | Summaries, RAG answers, support bots |
| Around 0.7        | Balanced creativity and coherence | General chat, brainstorming          |
| 0.8 - 1.0+        | More creative and diverse         | Creative writing, idea generation    |

---

# 3. Practical Use

In application development, temperature is adjusted based on the desired model behavior.

## Use Lower Temperature When

You need:

* Accuracy
* Consistency
* Factual responses
* Repeatable outputs
* Less hallucination risk

Example:

```text
Use low temperature for a RAG chatbot answering policy questions.
```

---

## Use Higher Temperature When

You need:

* Creativity
* Variety
* Imagination
* Multiple different ideas
* Less repetitive output

Example:

```text
Use high temperature for generating creative campaign slogans.
```

---

# 4. Exam Shortcut

| If the question says...   | Choose...          |
| ------------------------- | ------------------ |
| More deterministic output | Lower temperature  |
| More factual output       | Lower temperature  |
| More consistent responses | Lower temperature  |
| Less randomness           | Lower temperature  |
| More creativity           | Higher temperature |
| More diverse responses    | Higher temperature |
| More randomness           | Higher temperature |

---

# 5. Common Exam Traps

## Trap 1: High Temperature Does Not Mean Higher Accuracy

Higher temperature increases randomness, not correctness.

For factual tasks, high temperature can increase the risk of incorrect or inconsistent answers.

---

## Trap 2: Low Temperature Does Not Mean the Model Knows More

Lower temperature makes the model more deterministic, but it does not add new knowledge.

It only changes how the model selects tokens.

---

## Trap 3: Temperature Controls Generation, Not Retrieval

In a RAG system:

| Component   | What It Does                            |
| ----------- | --------------------------------------- |
| Retriever   | Finds relevant chunks                   |
| Temperature | Controls randomness of generated answer |

Temperature does not improve retrieval quality.

---

# 6. Final Summary

Temperature controls the randomness of a language model’s response.

* **Lower temperature** = focused, predictable, conservative output.
* **Higher temperature** = creative, diverse, more random output.

The key exam idea is:

> Use lower temperature for factual, deterministic tasks and higher temperature for creative, varied outputs.
