# Named Entity Recognition

## What Is Named Entity Recognition?

**Named Entity Recognition**, or **NER**, is a Natural Language Processing task that identifies and classifies important pieces of information in unstructured text.

These important pieces of information are called **entities**.

In simple terms:

> NER finds key names, places, dates, organizations, and other important values in text.

---

# 1. What Does NER Identify?

NER scans text and finds words or phrases that represent specific types of information.

Common entity types include:

| Entity Type  | Example                     |
| ------------ | --------------------------- |
| Person       | Steve Jobs                  |
| Organization | Apple                       |
| Location     | California                  |
| Date         | January 2025                |
| Time         | 10:30 AM                    |
| Money        | $5 million                  |
| Product      | iPhone                      |
| Event        | Databricks Data + AI Summit |

---

# 2. Step-by-Step Explanation

## Step 1: Entity Identification

The model scans the text and identifies words or phrases that look like named entities.

Example:

```text
Apple was founded by Steve Jobs in California.
```

Identified entities:

```text
Apple
Steve Jobs
California
```

---

## Step 2: Entity Classification

After identifying the entities, the model classifies each one into a category.

Example:

| Entity     | Category     |
| ---------- | ------------ |
| Apple      | Organization |
| Steve Jobs | Person       |
| California | Location     |

---

# 3. Example

Input text:

```text
Apple was founded by Steve Jobs in California.
```

NER output:

| Entity     | Entity Type  |
| ---------- | ------------ |
| Apple      | Organization |
| Steve Jobs | Person       |
| California | Location     |

---

# 4. How Does NER Know the Correct Category?

NER classification is determined using:

* Context
* Training data
* Learned language patterns
* Surrounding words
* Sentence structure
* Model probabilities

---

## Example: Apple vs apple

The word **Apple** can mean different things depending on context.

### Example 1

```text
Apple released a new iPhone.
```

Here, **Apple** likely means the company.

NER result:

| Entity | Type         |
| ------ | ------------ |
| Apple  | Organization |

---

### Example 2

```text
I ate an apple.
```

Here, **apple** means the fruit.

NER may not classify it as a named entity because it is a common noun, not a named entity.

---

# 5. Do We Need to Tell the Model the Category?

Usually, no.

For standard NER models, you provide the text, and the model predicts the entity categories based on what it learned during training.

However, you can guide the model if needed.

## Ways to Improve Classification

You can improve NER accuracy by providing:

* Clear sentence context
* Domain-specific training data
* Fine-tuned models
* Custom entity labels
* Better prompts if using an LLM
* Human-reviewed annotations for training

---

# 6. NER and Context

Context is very important.

The same word can have different meanings depending on nearby words.

Example:

| Sentence                                   | Meaning                               |
| ------------------------------------------ | ------------------------------------- |
| Apple released a new product.              | Apple = Organization                  |
| I bought an apple from the store.          | apple = fruit                         |
| Washington passed a new law.               | Washington may be location/government |
| George Washington was the first president. | George Washington = Person            |

---

# 7. Is NER Related to Metadata Extraction?

Yes.

NER is related to metadata extraction, but they are not exactly the same.

---

## Metadata Extraction

Metadata extraction means identifying structured information about a document or data item.

Examples of metadata:

* Author
* Date
* Organization
* Keywords
* Location
* Document type
* Customer name
* Product name
* Case number

---

## NER

NER specifically identifies and classifies named entities inside text.

Examples:

* Person names
* Company names
* Locations
* Dates
* Products

---

## Relationship Between NER and Metadata Extraction

NER can be one step in metadata extraction.

Example:

```text
A report mentions Siemens, GE Vernova, and California.
```

NER can extract:

| Extracted Entity | Entity Type  |
| ---------------- | ------------ |
| Siemens          | Organization |
| GE Vernova       | Organization |
| California       | Location     |

These entities can then be stored as metadata for the document.

---

# 8. NER vs Metadata Extraction

| Concept             | Meaning                                         | Example                           |
| ------------------- | ----------------------------------------------- | --------------------------------- |
| NER                 | Finds named entities in text                    | Apple = Organization              |
| Metadata extraction | Extracts structured attributes about a document | Author, date, company, topic      |
| Relationship        | NER can support metadata extraction             | Extract company names as metadata |

---

# 9. Use Cases of NER

NER is useful for converting unstructured text into structured data.

Common use cases include:

* Information retrieval
* Search improvement
* Question answering
* Metadata extraction
* Document classification
* Knowledge graph creation
* Compliance and PII detection
* Customer support automation
* Contract or invoice analysis

---

# 10. NER in RAG Systems

NER can improve RAG systems by helping extract important entities from documents.

Examples:

* Company names
* Product names
* Locations
* Dates
* Equipment IDs
* Customer names
* Legal entities

These entities can be stored as metadata and used for filtering or retrieval.

Example:

```text
User asks: Show incidents related to turbine unit GT-123 in Texas.
```

NER can help identify:

| Entity | Type         |
| ------ | ------------ |
| GT-123 | Equipment ID |
| Texas  | Location     |

Then retrieval can filter documents more accurately.

---

# 11. How Does Databricks Support NER?

Databricks supports NER through its scalable data and ML ecosystem.

You can perform NER in Databricks using:

* spaCy
* Hugging Face Transformers
* Spark NLP
* PyTorch
* TensorFlow
* MLflow
* Model Serving
* Custom fine-tuned models

---

## A. spaCy

spaCy provides pre-trained NLP pipelines that include NER.

Good for:

* Quick NER experiments
* Standard entity extraction
* Smaller or medium workloads

---

## B. Hugging Face Transformers

Hugging Face provides transformer models fine-tuned for NER.

Good for:

* Higher-quality NER
* Transformer-based extraction
* Custom fine-tuning
* Domain adaptation

Examples of model families:

* BERT
* RoBERTa
* DistilBERT
* DeBERTa

---

## C. Spark NLP

Spark NLP is useful for large-scale NLP processing with Apache Spark.

Good for:

* Distributed NER
* Large document collections
* Pre-trained NER pipelines
* Enterprise-scale text processing

---

## D. Custom NER Models

Databricks can be used to train custom NER models using labeled data.

Good for:

* Domain-specific entities
* Custom labels
* Industry-specific text
* Enterprise document extraction

Examples of custom entities:

* Equipment ID
* Policy number
* Contract ID
* Claim ID
* Serial number
* Customer account number

---

# 12. Example: NER Using Spark NLP in Databricks

## Step 1: Install Spark NLP

```python
%pip install spark-nlp
```

---

## Step 2: Import Libraries

```python
import sparknlp
from pyspark.sql import SparkSession

spark = sparknlp.start()
```

---

## Step 3: Create Sample Data

```python
data = spark.createDataFrame([
    (1, "Apple was founded by Steve Jobs in California."),
    (2, "Microsoft was founded by Bill Gates.")
], ["id", "text"])
```

---

## Step 4: Build the NER Pipeline

```python
from sparknlp.base import *
from sparknlp.annotator import *

document_assembler = DocumentAssembler() \
    .setInputCol("text") \
    .setOutputCol("document")

sentence_detector = SentenceDetector() \
    .setInputCols(["document"]) \
    .setOutputCol("sentence")

tokenizer = Tokenizer() \
    .setInputCols(["sentence"]) \
    .setOutputCol("token")

ner_model = NerDLModel.pretrained("ner_dl", "en") \
    .setInputCols(["sentence", "token"]) \
    .setOutputCol("ner")

ner_converter = NerConverter() \
    .setInputCols(["sentence", "token", "ner"]) \
    .setOutputCol("entities")
```

---

## Step 5: Build and Run the Pipeline

```python
from pyspark.ml import Pipeline

pipeline = Pipeline(stages=[
    document_assembler,
    sentence_detector,
    tokenizer,
    ner_model,
    ner_converter
])

model = pipeline.fit(data)
result = model.transform(data)
```

---

## Step 6: View the Results

```python
result.select("text", "entities.result").show(truncate=False)
```

Expected output:

```text
+--------------------------------------------------+----------------------------------+
|text                                              |result                            |
+--------------------------------------------------+----------------------------------+
|Apple was founded by Steve Jobs in California.    |[Apple, Steve Jobs, California]   |
|Microsoft was founded by Bill Gates.              |[Microsoft, Bill Gates]           |
+--------------------------------------------------+----------------------------------+
```

---

# 13. Exam Shortcuts

| If the question says...                            | Think...                            |
| -------------------------------------------------- | ----------------------------------- |
| Identify people, places, organizations             | NER                                 |
| Extract names from text                            | NER                                 |
| Classify entities in text                          | NER                                 |
| Convert unstructured text into structured entities | NER                                 |
| Extract metadata like company/location/date        | NER can help                        |
| Need domain-specific entity labels                 | Custom NER or fine-tuning           |
| Need large-scale NER in Databricks                 | Spark NLP or distributed processing |
| Need quick NER in Python                           | spaCy                               |
| Need transformer-based NER                         | Hugging Face                        |

---

# 14. Common Exam Traps

## Trap 1: NER is not summarization

NER extracts entities.

It does not summarize the whole document.

---

## Trap 2: NER is not sentiment analysis

NER identifies and classifies entities.

Sentiment analysis detects emotional tone or opinion.

---

## Trap 3: NER is not general classification

NER classifies spans of text into entity types.

General classification classifies the whole text or document.

---

## Trap 4: Entity meaning depends on context

The same word may have different meanings.

Example:

```text
Apple released a new iPhone.
I ate an apple.
```

The model uses context to decide whether something is an organization, common noun, or another entity type.

---

# 15. Final Summary

Named Entity Recognition is an NLP task that finds and classifies key entities in unstructured text.

It can identify:

* People
* Organizations
* Locations
* Dates
* Products
* Domain-specific entities

NER is related to metadata extraction because extracted entities can become structured metadata.

Databricks supports NER through:

* spaCy
* Hugging Face Transformers
* Spark NLP
* Custom model training
* MLflow and Model Serving for deployment

The key exam idea is:

> NER converts unstructured text into structured entity information.
