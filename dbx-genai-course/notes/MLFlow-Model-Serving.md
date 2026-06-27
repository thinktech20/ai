How MLflow helps this exact pipeline

Run-level observability for each notebook task.
Versioned config tracking for knobs already in your job params like batch sizes, retries, concurrency, model endpoint values: pw_sdg_fsr_ingestion.yml:38.
Side-by-side comparison of tuning changes (for example P1 batch/concurrency changes and P2 embed throughput).
Artifact logging for failed-document samples, error clusters, and quality snapshots.
Registry governance for any reusable inference logic you want to promote from notebook code into a managed model contract.
How PyFunc fits your FSR flow

P1 metadata normalization as a PyFunc model.

Input: extracted page-1 fields.

Output: normalized schema fields (title, customer, ESN, dates, IDs) already used by P1.

Benefit: you can version prompt/parsing logic independently and roll back quickly if extraction quality drops.

P2 chunk post-processing as a PyFunc model.

Input: chunk text + metadata.

Output: cleaned chunk payload, optional quality/risk score, optional routing flags.

Benefit: stable, testable interface before embedding and vector sync.

Optional downstream retrieval/rerank PyFunc for serving.

How MLflow helps this exact pipeline

Run-level observability for each notebook task.
Versioned config tracking for knobs already in your job params like batch sizes, retries, concurrency, model endpoint values: pw_sdg_fsr_ingestion.yml:38.
Side-by-side comparison of tuning changes (for example P1 batch/concurrency changes and P2 embed throughput).
Artifact logging for failed-document samples, error clusters, and quality snapshots.
Registry governance for any reusable inference logic you want to promote from notebook code into a managed model contract.
How PyFunc fits your FSR flow

P1 metadata normalization as a PyFunc model.

Input: extracted page-1 fields.

Output: normalized schema fields (title, customer, ESN, dates, IDs) already used by P1.

Benefit: you can version prompt/parsing logic independently and roll back quickly if extraction quality drops.

P2 chunk post-processing as a PyFunc model.

Input: chunk text + metadata.

Output: cleaned chunk payload, optional quality/risk score, optional routing flags.

Benefit: stable, testable interface before embedding and vector sync.

Optional downstream retrieval/rerank PyFunc for serving.

=====
Model Serving

Model serving in a Retrieval-Augmented Generation (RAG) pipeline involves deploying your RAG model so that it can be accessed through an API endpoint. Here’s a breakdown of what this means:

Integration with API: Model serving allows the RAG model to be queried in real time via an API, enabling users or applications to send requests and receive responses based on the model's output.

Use of the RAG Architecture: In a RAG pipeline, the process includes three main steps: retrieval of relevant documents based on user queries, augmentation where the model combines those documents with the query context, and finally, generation of responses from the model based on that combined information.

Real-Time Inference: Once the model is served, it can process incoming data and perform inference, allowing for dynamic knowledge retrieval and response generation. This means outside data sources can be updated without needing to retrain the entire model, making it more efficient.

Monitoring Usage: Model serving also includes the ability to track usage and performance metrics through logs and inferencing tables, which helps in maintaining the model and understanding its performance over time.

By placing the RAG model behind an API endpoint, you ensure that users can efficiently retrieve and utilize relevant information based on their queries with the latest documents available.

