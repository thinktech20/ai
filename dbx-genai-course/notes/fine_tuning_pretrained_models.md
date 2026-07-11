# Fine-Tuning Pre-Trained Models

Fine-tuning pre-trained models is a common practice used to adapt powerful models like **BERT**, **GPT**, or **Sentence-BERT** to specific tasks or domains.

Instead of training a model from scratch, fine-tuning starts with a model that already understands general language patterns and then adapts it to a narrower task using task-specific data.

---

# Steps to Fine-Tune Pre-Trained Models

## 1. Choose the Appropriate Pre-Trained Model

Select a model suited for your task.

| Task | Example Model |
|---|---|
| Text classification | BERT-base, BERT-large |
| Named entity recognition | BERT-base, BERT-large |
| Question answering | BERT-base, BERT-large |
| Sentence similarity | Sentence-BERT |
| Retrieval / embedding tasks | Sentence-BERT |
| Text generation | GPT |
| Conversational applications | GPT |

> Use models from libraries like **Hugging Face Transformers**.

---

## 2. Prepare Your Dataset

Gather labeled data relevant to your task.

Examples:

- For classification: text + label
- For sequence labeling: tokens + annotations
- For question answering: question + context + answer span
- For retrieval: query + positive passage + negative passage

### Example Format for Classification

| text | label |
|---|---|
| This is a sample text. | 0 |
| Another example here. | 1 |

---

## 3. Tokenize and Encode Data

Use the model's tokenizer to convert text into model-ready inputs such as:

- input IDs
- attention masks
- token type IDs, if needed

```python
from transformers import BertTokenizer

tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

inputs = tokenizer(
    texts,
    padding=True,
    truncation=True,
    return_tensors="pt"
)
```

---

## 4. Define Your Model

Usually, you add a task-specific head on top of the pre-trained model.

For classification:

```python
from transformers import BertForSequenceClassification

model = BertForSequenceClassification.from_pretrained(
    "bert-base-uncased",
    num_labels=2
)
```

---

## 5. Set Up Training Parameters

Define training settings such as:

- number of epochs
- batch size
- learning rate
- evaluation strategy
- checkpoint save strategy
- logging location

Using Hugging Face's `Trainer` API simplifies this.

```python
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    logging_dir="./logs",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset
)
```

---

## 6. Train the Model

Run the training process.

```python
trainer.train()
```

---

## 7. Evaluate and Save the Fine-Tuned Model

Evaluate performance on validation data, then save the model and tokenizer.

```python
model.save_pretrained("fine_tuned_model")
tokenizer.save_pretrained("fine_tuned_model")
```

---

## 8. Apply the Fine-Tuned Model

Load the fine-tuned model for inference.

```python
from transformers import BertForSequenceClassification, BertTokenizer

model = BertForSequenceClassification.from_pretrained("fine_tuned_model")
tokenizer = BertTokenizer.from_pretrained("fine_tuned_model")
```

---

# Summary: Fine-Tuning Pre-Trained Models

1. Select a suitable pre-trained model.
2. Prepare and encode your dataset.
3. Add task-specific layers if needed.
4. Fine-tune the model on your domain data.
5. Evaluate, save, and deploy the fine-tuned model.

---

# Fast and Easy Guide: Fine-Tuning BERT for Text Classification

This example shows a quick way to fine-tune **BERT** for a simple text classification task using Hugging Face Transformers and the Trainer API.

---

## 1. Install Necessary Libraries

```bash
pip install transformers datasets
```

---

## 2. Prepare Your Data

Create a small dataset with texts and labels.

```python
texts = [
    "I love this!",
    "This is bad.",
    "Awesome experience.",
    "Not good."
]

labels = [1, 0, 1, 0]  # 1 = positive, 0 = negative
```

---

## 3. Tokenize Your Data

Use BERT's tokenizer to convert text into model-ready format.

```python
from transformers import BertTokenizer

tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

encodings = tokenizer(
    texts,
    truncation=True,
    padding=True
)
```

---

## 4. Create a Dataset Object

Wrap the tokenized data into a format the Trainer can use.

```python
import torch

class Dataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {
            key: torch.tensor(val[idx])
            for key, val in self.encodings.items()
        }
        item["labels"] = torch.tensor(self.labels[idx])
        return item

dataset = Dataset(encodings, labels)
```

---

## 5. Load Pre-Trained BERT with a Classification Head

```python
from transformers import BertForSequenceClassification

model = BertForSequenceClassification.from_pretrained(
    "bert-base-uncased",
    num_labels=2
)
```

---

## 6. Set Up Training Arguments

```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    evaluation_strategy="no",
    logging_dir="./logs",
    save_steps=10,
    warmup_steps=10,
)
```

---

## 7. Initialize Trainer and Train

```python
from transformers import Trainer

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)

trainer.train()
```

---

## 8. Run Inference with the Fine-Tuned Model

Tokenize new input and generate predictions.

```python
texts_new = [
    "I dislike this.",
    "Absolutely fantastic!"
]

encodings_new = tokenizer(
    texts_new,
    truncation=True,
    padding=True
)

inputs = {
    key: torch.tensor(val)
    for key, val in encodings_new.items()
}

outputs = model(**inputs)

predictions = torch.argmax(outputs.logits, axis=-1)

print(predictions)  # 0 or 1
```

---

# Summary: Fast BERT Fine-Tuning Flow

1. Install libraries.
2. Prepare text and labels.
3. Tokenize the text.
4. Wrap data in a Dataset object.
5. Load BERT with a classification head.
6. Set training arguments.
7. Fine-tune using Trainer.
8. Run inference on new text.

---

# Training vs Fine-Tuning

The difference between **training** and **fine-tuning** lies in the starting point and scope.

---

## 1. Training a Model

### Definition

Training a model means building the model from scratch using a large dataset.

### Process

- Initialize model weights randomly.
- Provide large amounts of training data.
- The model learns general patterns and representations from scratch.
- Requires significant compute, data, time, and cost.

### Use Case

Use training from scratch when:

- No suitable pre-trained model exists.
- You need a fully custom model architecture.
- You have very large amounts of domain-specific data.
- You have enough compute resources.

---

## 2. Fine-Tuning a Model

### Definition

Fine-tuning means adapting a pre-trained model to a specific task or domain.

### Process

- Start with a model that has already learned general patterns.
- Continue training it on a smaller, task-specific dataset.
- Adjust the model to perform better on the target task.
- Usually faster and cheaper than training from scratch.

### Use Case

Use fine-tuning when:

- A strong pre-trained model already exists.
- You have a smaller task-specific dataset.
- You want better performance on a specific domain or task.
- You want to adapt models like BERT, GPT, Sentence-BERT, or ResNet.

Examples:

- Sentiment analysis
- Medical text classification
- Legal document classification
- Customer support intent detection
- Domain-specific question answering

---

# Training vs Fine-Tuning: Comparison

| Area | Training from Scratch | Fine-Tuning |
|---|---|---|
| Starting point | Random weights | Pre-trained model |
| Data required | Very large dataset | Smaller task-specific dataset |
| Compute required | Very high | Lower |
| Time required | Long | Shorter |
| Cost | High | Lower |
| Goal | Learn general patterns from scratch | Adapt general model to a specific task |
| Example | Train a new LLM from zero | Fine-tune BERT for sentiment classification |

---

# Overall Difference

```text
Training builds a model from scratch.

Fine-tuning adjusts an existing pre-trained model for a new, specific task or dataset.
```

---

# Exam Quick Cheat Sheet

## Fine-Tuning

```text
Fine-tuning = continue training a pre-trained model on task-specific data
```

Use fine-tuning when:

- You need domain adaptation.
- You have labeled examples.
- Prompting alone is not enough.
- You want consistent task-specific behavior.

---

## Training

```text
Training = build model from scratch using large-scale data
```

Use training when:

- No existing model fits the task.
- You have huge data and compute.
- You need a custom foundational model.

---

## Prompting vs Fine-Tuning

| Method | Changes Model Weights? | Best For |
|---|---:|---|
| Prompting | No | Quick behavior guidance |
| Few-shot prompting | No | Showing examples in the prompt |
| RAG | No | Adding external knowledge/context |
| Fine-tuning | Yes | Teaching task/domain behavior |
| Training from scratch | Yes | Creating a new model |

---

## Simple Memory Trick

```text
Prompting teaches through instructions.

Few-shot prompting teaches through examples in the prompt.

RAG teaches by adding retrieved context.

Fine-tuning teaches by updating model weights.

Training teaches the model from scratch.
```
