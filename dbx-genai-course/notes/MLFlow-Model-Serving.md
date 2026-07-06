MLflow is a tool used to manage the lifecycle of machine learning and GenAI applications.

In simple words:

MLflow helps you track, test, package, version, evaluate, and deploy models.

Think of it like a “project management system for models and AI applications.”

Think of MLflow as having multiple roles:

MLflow Tracking      → log experiments, metrics, parameters, artifacts
MLflow Evaluation    → evaluate model/LLM outputs
MLflow Model Format  → package code/model for deployment
MLflow Model Registry → version and manage model releases
Model Serving        → deploy the packaged model

=====
A model is the thing that processes input and returns an answer, prediction, classification, generated text, or some other output.

In your Databricks certification context, “model” can mean a few things:

LLM model
Example: GPT, Claude, Llama, DBRX
Input: prompt
Output: generated text

Embedding model
Input: text
Output: vector/embedding

Classification model
Input: text or data
Output: label/category

MLflow PyFunc model
Input: any structured input
Output: anything your Python code returns

======

When RAG becomes a PyFunc model

A RAG app becomes an MLflow PyFunc model when you wrap the RAG logic inside something like:

class RagModel(mlflow.pyfunc.PythonModel):

    def predict(self, context, model_input):
        question = model_input["question"][0]

        docs = retrieve_from_vector_search(question)
        prompt = build_prompt(question, docs)
        answer = call_llm(prompt)

        return answer

Then MLflow can treat the whole RAG workflow like a deployable model:

question → predict() → answer