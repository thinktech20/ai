Model Serving

Model serving in a Retrieval-Augmented Generation (RAG) pipeline involves deploying your RAG model so that it can be accessed through an API endpoint. Here’s a breakdown of what this means:

Integration with API: Model serving allows the RAG model to be queried in real time via an API, enabling users or applications to send requests and receive responses based on the model's output.

Use of the RAG Architecture: In a RAG pipeline, the process includes three main steps: retrieval of relevant documents based on user queries, augmentation where the model combines those documents with the query context, and finally, generation of responses from the model based on that combined information.

Real-Time Inference: Once the model is served, it can process incoming data and perform inference, allowing for dynamic knowledge retrieval and response generation. This means outside data sources can be updated without needing to retrain the entire model, making it more efficient.

Monitoring Usage: Model serving also includes the ability to track usage and performance metrics through logs and inferencing tables, which helps in maintaining the model and understanding its performance over time.

By placing the RAG model behind an API endpoint, you ensure that users can efficiently retrieve and utilize relevant information based on their queries with the latest documents available.

