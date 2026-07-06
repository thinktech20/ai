MLflow model tracking is mostly for development-time tracking.
Inference tables are for production-time monitoring.

Think:

Before deployment → MLflow tracking
After deployment  → inference tables
1. MLflow Model Tracking

Use MLflow tracking when you are building, testing, training, evaluating, or tuning your model/RAG pipeline.

It helps you log things like parameters, metrics, artifacts, notebooks, datasets, and model versions. Databricks describes MLflow tracking as a way to log notebooks, training datasets, parameters, metrics, tags, and artifacts related to model development.

For your GE RAG project, this is where MLflow fits:

Parsing run
  - parser = pdfplumber
  - OCR = false
  - table extraction = enabled
  - failed documents = 23

Chunking run
  - chunk_size = 800
  - chunk_overlap = 100
  - section-aware = true
  - number_of_chunks = 1.09M

Embedding run
  - embedding_model = xyz
  - batch_size = 64
  - embedding_latency = 2.3 sec/batch
  - indexing_success_rate = 99.3%

Evaluation run
  - retrieval_precision
  - citation_accuracy
  - latency
  - cost
  - answer correctness

So MLflow tracking answers:

What experiment did I run?
What settings did I use?
Which version performed better?
What metrics did I get?
Can I reproduce this run?
2. Inference Tables

Use inference tables after a model or AI service is deployed and receiving real requests.

Databricks inference tables log model service requests and responses into Unity Catalog Delta tables, so you can monitor, debug, and optimize production model behavior.

They help you capture things like:

request timestamp
input prompt
model response
latency
status code
endpoint name
model version
errors
possibly request/response payloads

So inference tables answer:

What are users actually asking in production?
What did the model return?
Is latency increasing?
Are errors happening?
Are certain prompts causing bad outputs?
Which served model version produced this answer?
Simple comparison
Question	Use
I am testing chunk size 500 vs 1000	MLflow tracking
I want to compare embedding models	MLflow tracking
I want to log parsing accuracy during pipeline development	MLflow tracking
I want to evaluate RAG answer quality before deployment	MLflow evaluation/tracking
I want to deploy a model version	MLflow Registry + Databricks Model Serving
I want to see real production requests and responses	Inference tables
I want to debug why a user got a bad answer yesterday	Inference tables
I want to monitor production latency/errors	Inference tables
In your GE project

You were correctly using MLflow tracking/evaluation for:

parsing quality
chunking settings
embedding pipeline runs
retrieval/evaluation metrics
accuracy and efficiency comparison

If that RAG app went live behind a Databricks Model Serving endpoint or AI Gateway model service, then you would use inference tables to monitor actual production usage:

user question
retrieved context or response metadata
generated answer
latency
errors
model version
endpoint behavior
Certification shortcut
MLflow tracking = during build/test/evaluation

Inference tables = after serving, observe real inference traffic

A nice way to remember:

MLflow tells you what you built.
Inference tables tell you what happened when users used it.