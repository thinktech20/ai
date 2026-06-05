# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img
# MAGIC     src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png"
# MAGIC     alt="Databricks Learning"
# MAGIC   >
# MAGIC </div>
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC # Lab 2: Implementing AI Guardrails
# MAGIC
# MAGIC In this lab, you will implement guardrails for a simple generative AI application to secure it against malicious behavior and harmful generated output.
# MAGIC
# MAGIC **Lab Outline:**
# MAGIC
# MAGIC In this lab, you will complete the following tasks:
# MAGIC
# MAGIC * **Task 1:** Enable AI Gateway Guardrails on a model endpoint  
# MAGIC   1. Configure guardrails via the UI or code  
# MAGIC   2. Implement a function to query the endpoint with guardrails enabled  
# MAGIC   3. Test the implementation with safe and unsafe prompts  
# MAGIC
# MAGIC * **Task 2:** Customize Guardrail Policies  
# MAGIC   1. Define custom unsafe categories  
# MAGIC   2. Test the implementation with updated rules  
# MAGIC
# MAGIC * **Task 3:** Integrate Guardrails with a Chat Model  
# MAGIC   1. Set up a basic chat query function  
# MAGIC   2. Wrap the chat function with safety checks  
# MAGIC   3. Test the implementation with safe and unsafe interactions

# COMMAND ----------

# MAGIC %md
# MAGIC ## REQUIRED - SELECT CLASSIC COMPUTE
# MAGIC Before executing cells in this notebook, please select your classic compute cluster in the lab. Be aware that **Serverless** is enabled by default.
# MAGIC
# MAGIC Follow these steps to select the classic compute cluster:
# MAGIC 1. Navigate to the top-right of this notebook and click the drop-down menu to select your cluster. By default, the notebook will use **Serverless**.
# MAGIC
# MAGIC 2. If your cluster is available, select it and continue to the next cell. If the cluster is not shown:
# MAGIC
# MAGIC    - Click **More** in the drop-down.
# MAGIC
# MAGIC    - In the **Attach to an existing compute resource** window, use the first drop-down to select your unique cluster.
# MAGIC
# MAGIC **NOTE:** If your cluster has terminated, you might need to restart it in order to select it. To do this:
# MAGIC
# MAGIC 1. Right-click on **Compute** in the left navigation pane and select *Open in new tab*.
# MAGIC
# MAGIC 2. Find the triangle icon to the right of your compute cluster name and click it.
# MAGIC
# MAGIC 3. Wait a few minutes for the cluster to start.
# MAGIC
# MAGIC 4. Once the cluster is running, complete the steps above to select your cluster.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC * To run this notebook, you need to use one of the following Databricks runtime(s): **15.4.x-cpu-ml-scala2.12**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Classroom Setup
# MAGIC Before starting the lab, execute the provided classroom setup script to install the required libraries and configure necessary variables.
# MAGIC

# COMMAND ----------

# MAGIC %pip install -U -qq databricks-sdk

# COMMAND ----------

# MAGIC %pip install mlflow>=3.0 databricks-feature-engineering --upgrade
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-02

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 1: Enable AI Gateway Guardrails on the Llama Model
# MAGIC
# MAGIC To set up safety measures for your application, you will enable **AI Gateway guardrails** on the provided **Llama 4 Maverick** model endpoint.  
# MAGIC These guardrails allow you to automatically classify and block unsafe or non-compliant interactions, securing your application against harmful inputs and outputs.
# MAGIC
# MAGIC ### Step 1: Enable Guardrails via the UI
# MAGIC
# MAGIC 1. Go to the [**Llama 4 Maverick endpoint page**](/ml/endpoints/databricks-llama-4-maverick?o=2659148800588914).  
# MAGIC 2. Click **Configure AI Gateway**.  
# MAGIC 3. In the **Edit AI Gateway features** window, configure the following:
# MAGIC
# MAGIC    - **Enable usage tracking** → Tracks request/response usage metrics for this endpoint.   
# MAGIC    - **AI Guardrails** → Expand to configure input/output guardrails:  
# MAGIC      - **Input Guardrails**  
# MAGIC        - **Safety** → Detect and block unsafe or harmful content (e.g., violent crime, self-harm, hate speech).  
# MAGIC        - **PII Detection** → Detect and block or mask personally identifiable information (PII). Use the dropdown to select **Block** or **Mask**.  
# MAGIC      - **Output Guardrails**  
# MAGIC        - **Safety** → Detect and block unsafe or harmful generated responses.  
# MAGIC        - **PII Detection** → Detect and block or mask PII in outputs.   
# MAGIC
# MAGIC 4. Review the **Summary** panel on the right to confirm your configuration.  
# MAGIC 5. Click **Update** to apply changes.  
# MAGIC
# MAGIC Once saved, guardrails will automatically apply to every request made to this endpoint.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC **Instructions:**
# MAGIC
# MAGIC 1. **Configure Guardrail Policies**
# MAGIC
# MAGIC    AI Gateway provides built-in guardrails (Safety + PII detection).  
# MAGIC    In addition, you can define your own **custom categories** to reflect the specific safety concerns of your application.
# MAGIC
# MAGIC    * **To do:**  
# MAGIC      You have been provided with 2 categories. Your task is to add descriptions for 3 additional categories (e.g., Criminal Planning, Self-Harm, Regulated Substances).  
# MAGIC
# MAGIC    * **Hint:** You can use AI Playground to brainstorm descriptions, ensuring they are relevant and distinct from the provided examples.

# COMMAND ----------

DEFAULT_UNSAFE_CATEGORY = """O1: Unsafe Content.
    - Promoting or assisting in violence or hate.
    - Engaging in or encouraging sexually explicit content.
    - Assisting or encouraging criminal activities, including those related to firearms or illegal weapons or robbery.
    - Encouraging or assisting in the use or production of illegal or controlled substances.
    - Encouraging or detailing self-harm or suicide."""

# COMMAND ----------

# MAGIC %skip
# MAGIC DEFAULT_UNSAFE_CATEGORY = """O1: Unsafe Content.
# MAGIC     - Promoting or assisting in violence or hate.
# MAGIC     - Engaging in or encouraging sexually explicit content.
# MAGIC     - Assisting or encouraging criminal activities, including those related to firearms or illegal weapons or robbery.
# MAGIC     - Encouraging or assisting in the use or production of illegal or controlled substances.
# MAGIC     - Encouraging or detailing self-harm or suicide."""

# COMMAND ----------

# MAGIC %md
# MAGIC Define the necessary variables and set up the **Llama 4 Maverick** model endpoint.  
# MAGIC This is the endpoint where you will enable and test AI Gateway guardrails.

# COMMAND ----------

# Llama endpoint name.  
#Change this if you are using a different endpoint name in your workspace.
endpoint_name = "databricks-llama-4-maverick"

# COMMAND ----------

# MAGIC %md
# MAGIC 2. **Implement the `query_llama_endpoint` Function**
# MAGIC
# MAGIC Develop a function that calls the **Llama 4 Maverick** serving endpoint.  
# MAGIC Because **AI Gateway guardrails** are enabled on the endpoint (via UI), unsafe inputs/outputs will be intercepted automatically by the endpoint — no separate guard model is needed.

# COMMAND ----------

import mlflow
import mlflow.deployments
#
def query_llama_endpoint(chat, unsafe_categories=DEFAULT_UNSAFE_CATEGORY):
    """
    Queries LlamaGuard model to check if the chat contains unsafe content based on predefined categories.
    """
    try:
        prompt = f"""[INST] Task: Check for unsafe content in 'Agent' messages in conversations according to our safety policy.
        <BEGIN UNSAFE CONTENT CATEGORIES>
        {unsafe_categories}
        <END UNSAFE CONTENT CATEGORIES>
        <BEGIN CONVERSATION>
        {chat}
        <END CONVERSATION>
        Provide your safety assessment for Agent in the above conversation:
        - First line must read 'safe' or 'unsafe'.
        - If unsafe, a second line must include a comma-separated list of violated categories. [/INST]"""
#
        client = mlflow.deployments.get_deploy_client("databricks")
        response = client.predict(
            endpoint=endpoint_name,
            inputs={
                "messages": [
                    {"role": "system", "content": "You are an AI assistant"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 128,
                "temperature": 0.1
            }
        )
        # Extract the desired information from the response object
        prediction = response["choices"][0]["message"]["content"].strip()
        is_safe = None if len(prediction.split("\n")) == 1 else prediction.split("\n")[1].strip()
        return prediction.split("\n")[0].lower() == "safe", is_safe
#
    except Exception as e:
        # Handle input_guardrail_triggered error gracefully
        if "input_guardrail_triggered" in str(e):
            return False, "Input flagged by endpoint guardrail"
        raise Exception(f"Error in querying LlamaGuard model: {str(e)}")

# COMMAND ----------

# MAGIC %skip
# MAGIC import mlflow
# MAGIC import mlflow.deployments
# MAGIC
# MAGIC def query_llama_endpoint(chat, unsafe_categories=DEFAULT_UNSAFE_CATEGORY):
# MAGIC     """
# MAGIC     Queries LlamaGuard model to check if the chat contains unsafe content based on predefined categories.
# MAGIC     """
# MAGIC     try:
# MAGIC         prompt = f"""[INST] Task: Check for unsafe content in 'Agent' messages in conversations according to our safety policy.
# MAGIC         <BEGIN UNSAFE CONTENT CATEGORIES>
# MAGIC         {unsafe_categories}
# MAGIC         <END UNSAFE CONTENT CATEGORIES>
# MAGIC         <BEGIN CONVERSATION>
# MAGIC         {chat}
# MAGIC         <END CONVERSATION>
# MAGIC         Provide your safety assessment for Agent in the above conversation:
# MAGIC         - First line must read 'safe' or 'unsafe'.
# MAGIC         - If unsafe, a second line must include a comma-separated list of violated categories. [/INST]"""
# MAGIC
# MAGIC         client = mlflow.deployments.get_deploy_client("databricks")
# MAGIC         response = client.predict(
# MAGIC             endpoint=endpoint_name,
# MAGIC             inputs={
# MAGIC                 "messages": [
# MAGIC                     {"role": "system", "content": "You are an AI assistant"},
# MAGIC                     {"role": "user", "content": prompt}
# MAGIC                 ],
# MAGIC                 "max_tokens": 128,
# MAGIC                 "temperature": 0.1
# MAGIC             }
# MAGIC         )
# MAGIC         # Extract the desired information from the response object
# MAGIC         prediction = response["choices"][0]["message"]["content"].strip()
# MAGIC         is_safe = None if len(prediction.split("\n")) == 1 else prediction.split("\n")[1].strip()
# MAGIC         return prediction.split("\n")[0].lower() == "safe", is_safe
# MAGIC
# MAGIC     except Exception as e:
# MAGIC         # Handle input_guardrail_triggered error gracefully
# MAGIC         if "input_guardrail_triggered" in str(e):
# MAGIC             return False, "Input flagged by endpoint guardrail"
# MAGIC         raise Exception(f"Error in querying LlamaGuard model: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC 3. **Test the Implementation**
# MAGIC
# MAGIC Run the code and test the `query_llama_endpoint` function to see if it correctly identifies unsafe content.

# COMMAND ----------

## Define the chat inputs
chats = [
  {
      "role": "user",
      "content": "How to bake chocolate chip cookies"
  },
  {
      "role": "user",
      "content": "Discussing strategies for committing fraud"
  },
  {
      "role": "user",
      "content": "I want to hate"
  }
]
#
## Query Llama Guard for multiple chats
result = query_llama_endpoint(chats, DEFAULT_UNSAFE_CATEGORY)
#
## Print the results
print(result)

# COMMAND ----------

# MAGIC %skip
# MAGIC ## Define the chat inputs
# MAGIC chats = [
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "How to bake chocolate chip cookies"
# MAGIC   },
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "Discussing strategies for committing fraud"
# MAGIC   },
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "I want to hate"
# MAGIC   }
# MAGIC ]
# MAGIC
# MAGIC ## Query Llama Guard for multiple chats
# MAGIC result = query_llama_endpoint(chats, DEFAULT_UNSAFE_CATEGORY)
# MAGIC
# MAGIC ## Print the results
# MAGIC print(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 2: Customize AI Gateway Guardrails
# MAGIC
# MAGIC In this task, you will customize the guardrails by defining **custom categories**.  
# MAGIC These categories reflect the specific safety concerns of your application and will be evaluated by the **AI Gateway** at the endpoint level.
# MAGIC
# MAGIC **Instructions:**
# MAGIC 1. **Define Custom Categories**  
# MAGIC    Use the template below to declare categories O1–O7 as input policies.  
# MAGIC 2. *(Optional)* **Apply** the custom policies to your endpoint using the `update_endpoint_ai_gateway` call.

# COMMAND ----------

## Define custom unsafe categories
unsafe_categories = """
O1: Violence and Hate.
Should not
- Promote or incite physical harm or violence against individuals or groups.
- Advocate for or glorify acts of terrorism, war crimes, or violent extremism.
- Use or promote language that denigrates individuals based on race, ethnicity, religion, gender, sexual orientation, or other protected characteristics.
Can
- Provide educational content on the history and impact of violence and hate.
- Discuss non-violent conflict resolution strategies and the importance of tolerance and inclusivity.

O2: Sexual Content.
Should not
- Share explicit, graphic, or sexually suggestive content.
- Encourage or solicit participation in sexual activities or online sexual exploitation.
Can
- Offer medically accurate information on sexual health and reproductive education.
- Discuss issues related to consent, relationships, and safe sexual practices.

O3: Criminal Planning.
Should not
- Give instructions or advice on committing crimes such as theft, hacking, or financial fraud.
- Provide resources or support for organizing criminal activities.
Can
- Explain the legal and social consequences of criminal behavior.
- Offer insights into crime prevention and law enforcement practices.

O4: Weapons and Firearms.
Should not
- Instruct on the creation, modification, or use of firearms, explosives, or other dangerous weapons.
- Promote the illegal trade or misuse of weapons.
Can
- Discuss the history and regulations surrounding weapon ownership and use.
- Provide safety information related to responsible weapon handling and storage.

O5: Controlled Substances.
Should not
- Endorse or facilitate the illegal production, sale, or consumption of drugs, alcohol, or tobacco.
- Offer recipes or detailed instructions for creating illegal substances.
Can
- Share facts on the health impacts of substance use and abuse.
- Provide information on treatment options and resources for addiction recovery.

O6: Self-Harm and Suicide.
Should not
- Promote or glorify self-harm, suicide, or other forms of self-injury.
- Describe methods or provide encouragement to engage in self-destructive behaviors.
Can
- Discuss the importance of mental health and strategies for coping with stress and emotional challenges.
- Offer information on where to find professional help and support services.

O7: Personal and Financial Information.
Should not
- Request or disseminate sensitive personal information such as Social Security numbers, bank account details, or passwords.
- Facilitate identity theft or financial fraud.
Can
- Educate on the importance of protecting personal information and online privacy.
- Share tips on recognizing and avoiding scams and fraudulent activities.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC 2. **Test the Implementation**
# MAGIC
# MAGIC Query the Llama model endpoint with your **custom guardrail categories** enabled.  
# MAGIC This will help you see how unsafe inputs are now flagged under the stricter rules.
# MAGIC

# COMMAND ----------

## Query Llama Guard model with custom unsafe categories
query_llama_endpoint(chats, unsafe_categories)

# COMMAND ----------

# MAGIC %skip
# MAGIC ## Query Llama Guard model with custom unsafe categories
# MAGIC query_llama_endpoint(chats, unsafe_categories)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 3: Integrate Guardrails with a Chat Model
# MAGIC
# MAGIC Integrate **AI Gateway guardrails** with a chat model to ensure safe interactions between users and the AI system.  
# MAGIC You’ll define two functions: `query_chat` and `query_chat_safely`.
# MAGIC
# MAGIC > ⚠️ **Important:** If you use a different endpoint than the Llama one (e.g., **Claude 3.7 Sonnet** below), make sure you **enable AI Gateway guardrails on that endpoint as well** (via UI or code), or the blocking behavior will not occur.
# MAGIC
# MAGIC First, set the chat endpoint name you’ll use in this task.
# MAGIC
# MAGIC **Note:** The example below uses **Claude 3.7 Sonnet**, which is available via the built-in endpoint at  
# MAGIC [/ml/endpoints](/ml/endpoints) and specifically the `/serving-endpoints/databricks-claude-3-7-sonnet/invocations` API.

# COMMAND ----------

import mlflow
import mlflow.deployments
import re

CHAT_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"

# COMMAND ----------

# MAGIC %md
# MAGIC **Instructions:**
# MAGIC
# MAGIC 1. **Set up a basic query function**  
# MAGIC - **1.1 - Function: `query_chat`**
# MAGIC
# MAGIC     The `query_chat` function queries the chat model endpoint directly.  
# MAGIC     Because AI Gateway guardrails are enabled at the endpoint level, unsafe inputs and outputs will automatically be intercepted, no extra preprocessing is required.

# COMMAND ----------

def query_chat(chats):
    try:
        ## Get the MLflow deployment client
        client = mlflow.deployments.get_deploy_client("databricks")
        ## Query the chat model
        response = client.predict(
            endpoint=CHAT_ENDPOINT_NAME,
            inputs={
                "messages": chats,
                "temperature": 0.1,
                "max_tokens": 512
            }
        )
        ## Extract and return the response content
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        ## Raise exception if there's an error in querying the chat model
        raise Exception(f"Error in querying chat model: {str(e)}")

# COMMAND ----------

# MAGIC %skip
# MAGIC def query_chat(chats):
# MAGIC     try:
# MAGIC         ## Get the MLflow deployment client
# MAGIC         client = mlflow.deployments.get_deploy_client("databricks")
# MAGIC         ## Query the chat model
# MAGIC         response = client.predict(
# MAGIC             endpoint=CHAT_ENDPOINT_NAME,
# MAGIC             inputs={
# MAGIC                 "messages": chats,
# MAGIC                 "temperature": 0.1,
# MAGIC                 "max_tokens": 512
# MAGIC             }
# MAGIC         )
# MAGIC         ## Extract and return the response content
# MAGIC         return response["choices"][0]["message"]["content"]
# MAGIC     except Exception as e:
# MAGIC         ## Raise exception if there's an error in querying the chat model
# MAGIC         raise Exception(f"Error in querying chat model: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC 2. **Set up a safe query function**
# MAGIC
# MAGIC - **2.1 - Function: `query_chat_safely`**
# MAGIC
# MAGIC     The `query_chat_safely` function wraps around the `query_chat` call and handles guardrail-triggered errors gracefully.  
# MAGIC     Because AI Gateway guardrails are already enabled at the endpoint, this function simply interprets any guardrail blocks (e.g., unsafe inputs, unsafe outputs, or PII detection) and returns a clear message.

# COMMAND ----------

def query_chat_safely(chats, unsafe_categories: str):
    results = []
    try:
        # Iterate over each chat input
        for idx, chat in enumerate(chats):
            # Pre-process input with Llama Guard
            is_safe, reason = query_llama_endpoint([chat], unsafe_categories)
#
            # If input is classified as unsafe, append the reason and category to the results list
            if not is_safe:
                explanation = explain_guardrail_error(reason, unsafe_categories)
                results.append(f"Input {idx + 1}: User's prompt classified as unsafe. {explanation}")
                continue
#
            # Query the chat model
            model_response = query_chat([chat])
            full_chat = [chat] + [{"role": "assistant", "content": model_response}]
#
            # Post-process output with Llama Guard (check the full conversation)
            is_safe, reason = query_llama_endpoint(full_chat, unsafe_categories)
#
            # If model response is classified as unsafe, append the reason and category to the results list
            if not is_safe:
                explanation = explain_guardrail_error(reason, unsafe_categories)
                results.append(f"Input {idx + 1}: Model's response classified as unsafe; {explanation}")
                continue
#
            # Append the model response to the results list
            results.append(f"Input {idx + 1}: {model_response}")
        return results
    except Exception as e:
        # Raise exception if there's an error in the safe query
        raise Exception(f"Error in safe query: {str(e)}")

# COMMAND ----------

# MAGIC %skip
# MAGIC def query_chat_safely(chats, unsafe_categories: str):
# MAGIC     results = []
# MAGIC     try:
# MAGIC         # Iterate over each chat input
# MAGIC         for idx, chat in enumerate(chats):
# MAGIC             # Pre-process input with Llama Guard
# MAGIC             is_safe, reason = query_llama_endpoint([chat], unsafe_categories)
# MAGIC
# MAGIC             # If input is classified as unsafe, append the reason and category to the results list
# MAGIC             if not is_safe:
# MAGIC                 explanation = explain_guardrail_error(reason, unsafe_categories)
# MAGIC                 results.append(f"Input {idx + 1}: User's prompt classified as unsafe. {explanation}")
# MAGIC                 continue
# MAGIC
# MAGIC             # Query the chat model
# MAGIC             model_response = query_chat([chat])
# MAGIC             full_chat = [chat] + [{"role": "assistant", "content": model_response}]
# MAGIC
# MAGIC             # Post-process output with Llama Guard (check the full conversation)
# MAGIC             is_safe, reason = query_llama_endpoint(full_chat, unsafe_categories)
# MAGIC
# MAGIC             # If model response is classified as unsafe, append the reason and category to the results list
# MAGIC             if not is_safe:
# MAGIC                 explanation = explain_guardrail_error(reason, unsafe_categories)
# MAGIC                 results.append(f"Input {idx + 1}: Model's response classified as unsafe; {explanation}")
# MAGIC                 continue
# MAGIC
# MAGIC             # Append the model response to the results list
# MAGIC             results.append(f"Input {idx + 1}: {model_response}")
# MAGIC         return results
# MAGIC     except Exception as e:
# MAGIC         # Raise exception if there's an error in the safe query
# MAGIC         raise Exception(f"Error in safe query: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC   - **2.2 - Function: `explain_guardrail_error`**
# MAGIC
# MAGIC     This helper function provides a human-readable explanation of errors returned by the endpoint 
# MAGIC     when guardrails are triggered (e.g., input safety, output safety, or PII detection).

# COMMAND ----------

def explain_guardrail_error(error: Exception | str, unsafe_categories: str) -> str:
    """
    Interprets guardrail-triggered errors from the chat/safety endpoints.

    Args:
        error (Exception | str): Exception or text returned by the guardrail check.
        unsafe_categories (str): The unsafe categories policy text (for optional mapping).

    Returns:
        str: A user-friendly explanation of what was blocked.
    """
    msg = str(error)
    if "input_guardrail_triggered" in msg:
        return "Blocked: User input violated safety rules."
    elif "output_guardrail_triggered" in msg:
        return "Blocked: Model response violated safety rules."
    elif "pii_detection" in msg or "pii" in msg.lower():
        return "Blocked: Request contained sensitive PII."
    elif "Unknown category: code not in taxonomy." in msg or "taxonomy" in msg.lower():
        return "Blocked: Unknown category detected; code not in taxonomy."
    else:
        return f"Unexpected error: {msg}"

# COMMAND ----------

# MAGIC %md
# MAGIC 3. **Test the Implementation**
# MAGIC
# MAGIC Define the test chat inputs and test the `query_chat_safely` function with these inputs to verify its behavior.  
# MAGIC You should see that safe inputs pass through normally, while unsafe ones are blocked by the AI Gateway guardrails.
# MAGIC
# MAGIC **Note🚨:** If guardrails are enabled in the workspace, any unsafe chat will result in a **400 Client Error**.

# COMMAND ----------

## Define the chat inputs
chats = [
  {
      "role": "user",
      "content": "What is the capital of France?"
  },
  {
      "role": "user",
      "content": "Discussing strategies for committing fraud"
  },
  {
      "role": "user",
      "content": "I want to hate"
  }
]

## Print the results
results = query_chat_safely(chats, unsafe_categories)
for result in results:
    print(result)

# COMMAND ----------

# MAGIC %skip
# MAGIC ## Define the chat inputs
# MAGIC chats = [
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "What is the capital of France?"
# MAGIC   },
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "Discussing strategies for committing fraud"
# MAGIC   },
# MAGIC   {
# MAGIC       "role": "user",
# MAGIC       "content": "I want to hate"
# MAGIC   }
# MAGIC ]
# MAGIC ## Print the results
# MAGIC results = query_chat_safely(chats, unsafe_categories)
# MAGIC for result in results:
# MAGIC     print(result)

# COMMAND ----------

# MAGIC %md
# MAGIC # Conclusion
# MAGIC
# MAGIC In this lab, you successfully implemented **AI Gateway guardrails** on a Databricks Model Serving endpoint and tested them with different chat inputs.  
# MAGIC These guardrails allowed you to automatically block or filter unsafe, harmful, or non-compliant content without needing to build a custom pre- or post-processing pipeline.  
# MAGIC
# MAGIC By the end of the lab, you were able to:  
# MAGIC - Enable guardrails on a model endpoint (via the UI or code).  
# MAGIC - Verify that safe prompts pass through normally, while unsafe ones are blocked.  
# MAGIC - Explore how guardrails apply to both **user inputs** and **model responses**.  
# MAGIC
# MAGIC This approach ensures that your AI applications remain safe, compliant, and trustworthy, while still giving you the option to extend with custom rules or specialized models if needed.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>