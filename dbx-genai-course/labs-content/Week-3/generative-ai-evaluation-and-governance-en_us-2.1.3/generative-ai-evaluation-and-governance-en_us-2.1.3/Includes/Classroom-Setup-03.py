# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

DA = DBAcademyHelper()
DA.init()

# COMMAND ----------

from databricks.sdk.service.serving import ChatMessage
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------

def query_chatbot_system(input: str) -> str:
   
    messages = [
        {
            "role": "system",
            "content": "You are a chatbot that specializes in assisting with Databricks-related questions. You should remain impartial when providing assistance and answering questions."
        },
        { 
            "role": "user", 
            "content": input 
        }
    ]
    messages = [ChatMessage.from_dict(message) for message in messages]
    chat_response = w.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=messages,
        max_tokens=128
    )

    return chat_response.as_dict()["choices"][0]["message"]["content"]

# COMMAND ----------

def query_product_summary_system(input: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "You are an assistant that summarizes text. Given a text input, you need to provide a one-sentence summary. You specialize in summiarizing reviews of grocery products. Please keep the reviews in first-person perspective if they're originally written in first person. Do not change the sentiment. Do not create a run-on sentence – be concise."
        },
        { 
            "role": "user", 
            "content": input 
        }
    ]
    messages = [ChatMessage.from_dict(message) for message in messages]
    chat_response = w.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=messages,
        max_tokens=128
    )

    return chat_response.as_dict()["choices"][0]["message"]["content"]