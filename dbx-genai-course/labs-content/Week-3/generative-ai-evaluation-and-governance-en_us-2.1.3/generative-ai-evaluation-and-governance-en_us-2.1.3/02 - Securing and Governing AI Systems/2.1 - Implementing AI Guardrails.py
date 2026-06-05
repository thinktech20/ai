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
# MAGIC # Implementing AI Guardrails
# MAGIC
# MAGIC **In this demo, we will focus on implementing guardrails for a simple generative AI application.** This is important to secure our application against malicious behavior and harmful generated output.
# MAGIC
# MAGIC To start, we will test the application with a prompt that will cause it to respond in a way we'd prefer it not to. Then, we'll implement a guardrail to prevent that response, and test again to see the guardrail in action.
# MAGIC
# MAGIC **Preview Note:** This demo uses a couple of features which are in **Private Preview**. While we typically do not teach Private Preview capabilities, the timing of the official rollout of new content aligns with the expected release of these capabilities into Public Preview.
# MAGIC
# MAGIC **Learning Objectives:**
# MAGIC
# MAGIC *By the end of this demo, you will be able to:*
# MAGIC
# MAGIC * Identify the need for guardrails in your application.  
# MAGIC * Describe how to choose guardrails for a given response risk.  
# MAGIC * Implement guardrails in an AI application.  
# MAGIC * Verify that the guardrails are working successfully.  
# MAGIC

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
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Classroom Setup
# MAGIC
# MAGIC Install required libraries.

# COMMAND ----------

# MAGIC %pip install -U -qq databricks-sdk mlflow>=3.0 databricks-feature-engineering --upgrade
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC Before starting the demo, run the provided classroom setup script. This script will define configuration variables necessary for the demo. Execute the following cell:

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-02

# COMMAND ----------

# MAGIC %md
# MAGIC **Other Conventions:**
# MAGIC
# MAGIC Throughout this demo, we'll refer to the object `DA`. This object, provided by Databricks Academy, contains variables such as your username, catalog name, schema name, working directory, and dataset locations. Run the code block below to view these details:

# COMMAND ----------

print(f"Username:          {DA.username}")
print(f"Catalog Name:      {DA.catalog_name}")
print(f"Schema Name:       {DA.schema_name}")
print(f"Working Directory: {DA.paths.working_dir}")
print(f"Dataset Location:  {DA.paths.datasets}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo Overview
# MAGIC
# MAGIC In this demo, we'll take a look at a couple of different ways to enable guardrails on LLMs in Databricks. We'll start off with simple examples and work our way through more robust implementations.
# MAGIC
# MAGIC We will follow the below steps:
# MAGIC
# MAGIC 1. Implement guardrails using a specialized LLM with Llama Guard
# MAGIC 2. Customize guardrails with a user-specified Llama Guard taxonomy
# MAGIC 3. Integrate Llama Guard with a custom chat bot

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Enable AI Guardrails with the Llama Model
# MAGIC
# MAGIC Databricks provides built-in **AI Gateway guardrails** that you can enable directly on serving endpoints.  
# MAGIC Instead of relying on a separate “Llama Guard” model, we’ll demonstrate how to apply guardrails **on a Llama model endpoint**.
# MAGIC
# MAGIC In this demo, we will use the **[`databricks-llama-4-maverick`](/ml/endpoints/databricks-llama-4-maverick?o=2659148800588914)** endpoint as an example.
# MAGIC
# MAGIC **What are AI Gateway Guardrails?**
# MAGIC
# MAGIC AI Gateway guardrails are configurable safety and compliance features that can be enabled on Databricks Model Serving endpoints. They help prevent unsafe, harmful, or non-compliant content from being generated or returned by large language models (LLMs). Guardrails operate at the endpoint level, providing centralized and consistent enforcement without requiring custom code.
# MAGIC
# MAGIC **Key Features of AI Gateway Guardrails:**
# MAGIC
# MAGIC - **PII Detection and Blocking:** Automatically detects and blocks personally identifiable information (PII) in prompts and responses.
# MAGIC - **Safety Filters:** Identifies and blocks harmful, toxic, or disallowed content, including hate speech, violence, and self-harm.
# MAGIC - **Usage Tracking:** Monitors and logs endpoint usage for auditing and compliance.
# MAGIC - **Custom Policies:** Allows configuration of custom rules and taxonomies to tailor safety enforcement to organizational needs.
# MAGIC
# MAGIC **Why Use Endpoint-Level Guardrails?**
# MAGIC
# MAGIC - **Centralized Control:** Apply safety and compliance policies across all applications using the endpoint.
# MAGIC - **Reduced Complexity:** No need to build and maintain separate preprocessing or postprocessing pipelines for safety.
# MAGIC - **Consistent Enforcement:** Ensures all requests and responses are checked, regardless of client or application.
# MAGIC - **Scalable and Reliable:** Built into Databricks Model Serving, guardrails scale automatically with your workloads.
# MAGIC
# MAGIC
# MAGIC > **Note:** For advanced or highly customized safety requirements, you can still use specialized models like Llama Guard as a pre- or post-processing step. However, for most use cases, AI Gateway guardrails provide robust, out-of-the-box protection.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🚨 Only for Instructors: Enable Guardrails using ADMIN Account via UI (if not already done)
# MAGIC
# MAGIC 1. **Access the Workspace as Admin**
# MAGIC    - Go to the **Assignment Page**.  
# MAGIC    - Click on the **Dashboard** (top-right menu).  
# MAGIC    - From the dropdown, select **Databricks Workspace**.  
# MAGIC    - Locate the **Workspace URL** under workspace information and click on the link.  
# MAGIC    - A **Workspace Admin** pop-up will appear → click **Enter as Admin**.  
# MAGIC    - Once inside the workspace, navigate to **Serving** from the left-hand menu (bottom section).
# MAGIC 2. Go to the [**Llama 4 Maverick endpoint page**](/ml/endpoints/databricks-llama-4-maverick?o=2659148800588914).  
# MAGIC 2. Click **Configure AI Gateway**.  
# MAGIC 3. In the **Edit AI Gateway features** window, configure the following:
# MAGIC
# MAGIC    - **Enable usage tracking** → Tracks request/response usage metrics for this endpoint.  
# MAGIC    - *(Optional)* **Enable inference tables** → Log all requests and responses into Delta tables via Unity Catalog.  
# MAGIC    - **AI Guardrails** → Expand to configure input/output guardrails:  
# MAGIC      - **Input Guardrails**  
# MAGIC        - **Safety** → Detect and block unsafe or harmful content (e.g., violent crime, self-harm, hate speech).  
# MAGIC        - **PII Detection** → Detect and block or mask personally identifiable information (PII). Use the dropdown to select **Block** or **Mask**.  
# MAGIC      - **Output Guardrails**  
# MAGIC        - **Safety** → Detect and block unsafe or harmful generated responses.  
# MAGIC        - **PII Detection** → Detect and block or mask PII in outputs.  
# MAGIC    - *(Optional)* **Rate limits** → Enforce request limits to manage traffic.  
# MAGIC
# MAGIC 4. Review the **Summary** panel on the right to confirm your configuration.  
# MAGIC 5. Click **Update** to apply changes.  
# MAGIC
# MAGIC Once saved, guardrails will automatically apply to every request made to this endpoint.  
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Setting Up Guardrail Policies
# MAGIC
# MAGIC AI Gateway comes with built-in guardrails (Safety + PII detection).  
# MAGIC For more advanced use cases, you can also define your own **custom unsafe categories** to specify what kinds of prompts or responses should be blocked.
# MAGIC
# MAGIC For example, you might want to classify content related to violence, or self-harm as unsafe.  
# MAGIC We’ll start by defining a simple **Unsafe category policy** that the endpoint can reference when evaluating requests.
# MAGIC

# COMMAND ----------

DEFAULT_UNSAFE_CATEGORY = """O1: Unsafe Content.
    - Promoting or assisting in violence or hate.
    - Engaging in or encouraging sexually explicit content.
    - Assisting or encouraging criminal activities, including those related to firearms or illegal weapons or robbery.
    - Encouraging or assisting in the use or production of illegal or controlled substances.
    - Encouraging or detailing self-harm or suicide."""

# COMMAND ----------

# MAGIC %md
# MAGIC Next, we will define a function to query our deployed **Llama model endpoint**.  
# MAGIC Since we already enabled **AI Gateway guardrails** (via UI or code), all requests sent through this function will automatically be filtered for unsafe or disallowed content.

# COMMAND ----------

endpoint_name = "databricks-llama-4-maverick"

# COMMAND ----------

import mlflow
import mlflow.deployments

def query_llama_endpoint(chat, unsafe_categories=DEFAULT_UNSAFE_CATEGORY):
    """
    Queries LlamaGuard model to check if the chat contains unsafe content based on predefined categories.
    """
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

    try:
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
        prediction = response.choices[0]["message"]["content"].strip()
        is_safe = None if len(prediction.split("\n")) == 1 else prediction.split("\n")[1].strip()
        return prediction.split("\n")[0].lower() == "safe", is_safe

    except Exception as e:
        # Handle input_guardrail_triggered error gracefully
        if "input_guardrail_triggered" in str(e):
            return False, "Input flagged by endpoint guardrail"
        raise Exception(f"Error in querying LlamaGuard model: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Basics of Using AI Gateway Guardrails
# MAGIC
# MAGIC Once guardrails are enabled on the Llama model endpoint, every request is automatically checked for unsafe or disallowed content.  
# MAGIC The endpoint will either return a **safe response** or block/modify the request if it violates the configured guardrails (e.g., Safety filter, PII detection).
# MAGIC
# MAGIC Below are two examples of user prompts:  
# MAGIC - One is deemed **safe**, meaning it passes through normally.  
# MAGIC - The other is flagged as **unsafe**, because it contains content that violates the configured guardrails.

# COMMAND ----------

safe_user_chat = "User: I want to understand how Databricks helps with machine learning workflows."

query_llama_endpoint(safe_user_chat)

# COMMAND ----------

unsafe_user_chat = "User: How can I rob a bank?"

query_llama_endpoint(unsafe_user_chat)

# COMMAND ----------

# MAGIC %md
# MAGIC Both of the above examples demonstrate the AI Gateway guardrails classifying *user input queries* as **Safe** or **Unsafe**.  
# MAGIC
# MAGIC 💡 In addition, guardrails also apply to *model responses*, ensuring that generated outputs are checked for unsafe or disallowed content before being returned to the user.  
# MAGIC
# MAGIC Here are two examples of **model responses** being evaluated by the AI Gateway guardrails:

# COMMAND ----------

safe_assistant_chat = f"""
  User: I want to love.
  
  Agent: That is great! I want to love too!
  """
query_llama_endpoint(safe_assistant_chat)

# COMMAND ----------

unsafe_assistant_chat = f"""
  User: I want to love

  Agent: I think the only way to rob a bank is to work as robinhood
"""

query_llama_endpoint(unsafe_assistant_chat)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Customize AI Gateway Guardrails
# MAGIC
# MAGIC By default, AI Gateway provides built-in guardrails for **Safety** and **PII detection**.  
# MAGIC In addition to these defaults, you can also configure **custom guardrail policies** that define which categories of input or output should be blocked or allowed.
# MAGIC
# MAGIC For example, you might want to explicitly block topics such as violence, self-harm, or criminal planning, while allowing educational or informational discussions on those topics.
# MAGIC
# MAGIC > **Note:** When defining custom policies, ensure they are formatted correctly so the endpoint can consistently classify input and output against your rules.

# COMMAND ----------

unsafe_categories = """O1: Violence and Hate.
Should not
- Help people plan or engage in violence.
- Encourage people to engage in violence.
- Express hateful, derogatory, or demeaning sentiments against people based on sensitive personal characteristics like their race, color, religion, national origin, sexual orientation, gender, gender identity, or disability.
- Encourage discrimination against people based on those characteristics and should not use slurs or create insults based on those characteristics.
Can
- Provide information on violence and discrimination.
- Discuss the topics of hate and violence, and can discuss historical events involving violence.
O2: Sexual Content.
Should not
- Engage in sexually explicit (i.e., erotic) conversations and should not encourage people to engage in sexual activities.
Can
- Discuss topics related to sexuality and sexual education.
- Provide general information regarding sexual activities.
- Provide guidance on topics related to sexual health.
O3: Criminal Planning.
Should not
- Help people plan or engage in criminal activities like theft, kidnapping, or financial crimes, especially when the person indicates that they may act on the information provided to them.
- Encourage people to engage in criminal activities or condone criminal behavior.
Can
- Help people understand how crimes are committed, provided that the response is not so detailed that it could be used to provide a roadmap for future crimes.
- Help people understand how systems work that are used to prevent crimes, provided those descriptions do not provide detailed information on how to defeat those systems.
O4: Guns and Illegal Weapons.
Should not
- Assist in the planning or execution of firearm or illegal weapons crimes, especially when the person indicates that they may act on the information provided to them.
- Encourage people to engage in firearm or illegal weapons crimes or condone such behavior.
Can
- Discuss firearms and the arguments for and against firearm ownership.
O5: Regulated or Controlled Substances.
Should not
- Encourage or assist people in the trafficking, consumption, or use of regulated or controlled substances, including but not limited to illegal drugs, tobacco, alcohol, and cannabis.
- Assist or encourage people to create such substances when it is illegal to do so.
Can
- Discuss the use of regulated or controlled substances, and can provide general information on those substances (ex: what their chemical composition is and what their effects are).
- Provide information on how those substances are manufactured, provided that the information is not so detailed as to provide step-by-step instructions for their creation.
O6: Self-Harm.
Should not
- Encourage people to harm themselves.
- Romanticize or condone self-harm or suicide.
- Provide information regarding the methods of suicide or self-harm.
- Provide any information or advice, other than information regarding appropriate health resources, to people who express or imply that they wish to harm themselves.
Can
- Provide general information regarding self-harm and suicide (ex: statistics, the mental health challenges faced by those who take these actions).
Should
- Provide information regarding appropriate health resources to people who imply or express the desire to harm themselves.
O7: Financial Sensitive Data.
Should not
- Provide any information on credit card number or pin number.
Can
- Provide general information regarding the risk of sharing credit card information with LLMs.
Should
- Provide information regarding proper handling of credit card information with LLMs."""

# COMMAND ----------

# MAGIC %md
# MAGIC When we send a request to the Llama model endpoint with our **custom guardrail configuration**,  
# MAGIC we may notice that the result changes depending on the policies we applied.  
# MAGIC
# MAGIC For example, a prompt that previously passed as safe might now be flagged as **unsafe** under the new rules.

# COMMAND ----------

query_llama_endpoint(unsafe_user_chat, unsafe_categories)

# COMMAND ----------

# MAGIC %md
# MAGIC **Question:** Can we guess what the response is indicating?

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Integrate Guardrails with a Chat Model
# MAGIC
# MAGIC So far, we’ve demonstrated enabling guardrails on the **Llama model endpoint** and testing them with simple examples.  
# MAGIC In practice, guardrails are most effective when integrated directly into a **chat application workflow**.
# MAGIC
# MAGIC With this setup, every user prompt and model response is automatically evaluated against the configured guardrails, without requiring extra pre- or post-processing code.
# MAGIC
# MAGIC
# MAGIC ### Setting Up the AI System
# MAGIC
# MAGIC To illustrate this, we’ll:
# MAGIC
# MAGIC 1. Configure the endpoint name for our chat model.  
# MAGIC 2. Define a basic query function to interact with the model.  
# MAGIC 3. Observe how the guardrails automatically enforce safety checks during conversation.  
# MAGIC
# MAGIC **Note:** In this example, our chatbot leverages the **Claude 3.7 Sonnet foundation model**.  
# MAGIC This model is accessible through the built-in foundation endpoint, available at [/ml/endpoints](/ml/endpoints) and specifically via the  
# MAGIC `/serving-endpoints/databricks-claude-3-7-sonnet/invocations` API.

# COMMAND ----------

CHAT_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"

# COMMAND ----------

# MAGIC %md
# MAGIC Next, let’s define our `query_chat` function.  
# MAGIC
# MAGIC This function sends a request to the chat model using the **Databricks Foundation Models API** and returns the model’s response.  
# MAGIC Because we already enabled **AI Gateway guardrails** on the endpoint, any unsafe input or output will automatically be intercepted.

# COMMAND ----------

import mlflow
import mlflow.deployments

def query_chat(messages, *, temperature=0.1, max_tokens=512):
    """
    Queries a chat model endpoint (with AI Gateway guardrails enabled).

    Args:
        messages (list[dict]): Chat input in the form of a list of messages,
                               e.g. [{"role": "user", "content": "Hello"}]
        temperature (float): Sampling temperature.
        max_tokens (int): Maximum number of tokens to generate.

    Returns:
        str: The model's response text (if not blocked by guardrails).

    Raises:
        Exception: If an error occurs while querying the endpoint.
                   If guardrails are triggered, the error will include
                   information such as "input_guardrail_triggered" or
                   "output_guardrail_triggered".
    """
    try:
        client = mlflow.deployments.get_deploy_client("databricks")
        response = client.predict(
            endpoint=CHAT_ENDPOINT_NAME,
            inputs={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        )
        return response.choices[0]["message"]["content"]
    except Exception as e:
        raise Exception(f"Error in querying chat model: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC Next, we will define a query function that interacts with the chat model endpoint.  
# MAGIC
# MAGIC Because **AI Gateway guardrails** are enabled at the endpoint level, both user inputs and model outputs are automatically evaluated for safety and compliance.  
# MAGIC This means we don’t need extra pre- or post-processing code, the guardrails are applied transparently whenever we call the endpoint.

# COMMAND ----------

def query_chat_safely(chat: list[dict], unsafe_categories: str) -> str:
    """
    Queries a chat model safely by checking the safety of both the user's input and the model's response.
    It uses a LlamaGuard-style endpoint to assess safety.

    Args:
        chat (list[dict]): The user's chat input, e.g. [{"role":"user","content":"Hi"}].
        unsafe_categories (str): Categories/policy text used by the guardrail to determine safety.

    Returns:
        str: The chat model's response if safe, else a safety warning message.

    Raises:
        Exception: If there are issues querying the model, processing the response,
                   or assessing safety.
    """
    try:
        # 1) Pre-check user input
        is_safe, reason = query_llama_endpoint(chat, unsafe_categories)
        if not is_safe:
            category = explain_guardrail_error(reason, unsafe_categories)
            return f"User's prompt classified as **{category}**; fails safety measures."

        # 2) Query the chat model
        model_response = query_chat(chat)  # or: query_chat(messages=chat)
        full_chat = chat + [{"role": "assistant", "content": model_response}]

        # 3) Post-check model output
        is_safe, reason = query_llama_endpoint(full_chat, unsafe_categories)
        if not is_safe:
            category = explain_guardrail_error(reason, unsafe_categories)
            return f"Model's response classified as **{category}**; fails safety measures."

        return model_response

    except Exception as e:
        raise Exception(f"Error in safe query: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC Finally, we’ll look at how the endpoint reports back when a request is blocked by guardrails.  
# MAGIC
# MAGIC Instead of manually parsing taxonomy codes (as with Llama Guard), the AI Gateway guardrails return clear information about which rule was triggered (e.g., **Safety** or **PII Detection**) whenever unsafe content is detected.

# COMMAND ----------

def explain_guardrail_error(error: Exception, unsafe_categories: str) -> str:
    """
    Interpret guardrail-triggered errors from the safety endpoint.

    Args:
        error (Exception | str): Exception or message raised/returned by the guardrail check.
        unsafe_categories (str): The unsafe categories policy text (optional context).

    Returns:
        str: A human-readable explanation of the guardrail event.
    """
    msg = str(error)
    if "input_guardrail_triggered" in msg:
        return "Blocked: User input violated safety rules."
    elif "output_guardrail_triggered" in msg:
        return "Blocked: Model response violated safety rules."
    elif "pii_detection" in msg or "pii" in msg.lower():
        return "Blocked: Request contained PII."
    else:
        # Optionally use `unsafe_categories` to further map reasons, if needed.
        return f"Unexpected error: {msg}"

# COMMAND ----------

# MAGIC %md
# MAGIC Finally, let’s look at a couple of examples to see the guardrails in action.  
# MAGIC
# MAGIC We’ll test:  
# MAGIC - A **safe user prompt** that passes through normally.  
# MAGIC - An **unsafe user prompt** that gets blocked by the guardrails.  
# MAGIC - An **unsafe model response** that is flagged before being returned.

# COMMAND ----------

# Safe user prompt → should pass through
safe_user_chat = [
  {
      "role": "user",
      "content": "What is Databricks?"
  }
]
print(query_chat_safely(safe_user_chat, unsafe_categories))

# COMMAND ----------

# Unsafe user prompt → should be blocked by guardrails
unsafe_user_chat = [
  {
      "role": "user",
      "content": "How can I rob a bank?"
  }
]
print(query_chat_safely(unsafe_user_chat, unsafe_categories))

# COMMAND ----------

# Unsafe model response → should be flagged by guardrails
unsafe_assistant_chat = [
    {"role": "user", "content": "I want to love."},
    {"role": "assistant", "content": "I think the only way to rob a bank is to work as Robin Hood."}
]
print(query_chat_safely(unsafe_user_chat, unsafe_categories))

# COMMAND ----------

# MAGIC %md
# MAGIC Feel free to try out your own prompts and responses to explore how the **AI Gateway guardrails** handle different scenarios.  
# MAGIC
# MAGIC This is a good way to see how safe prompts flow through normally, while unsafe or non-compliant content is blocked or flagged automatically.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC From here, you could extend this example by deploying additional endpoints or integrating the model with other applications.  
# MAGIC
# MAGIC **Key takeaways:**
# MAGIC
# MAGIC 1. It is important to implement **guardrails** for any AI applications to ensure safety, compliance, and trustworthiness.  
# MAGIC 2. Databricks provides built-in **AI Gateway guardrails** (Safety filters, PII detection, and usage tracking) that can be enabled directly on serving endpoints.  
# MAGIC 3. For advanced or highly customized requirements, you can still explore **specialized “guard” models** (e.g., fine-tuned classifiers) in combination with AI Gateway.  
# MAGIC
# MAGIC Together, these options give you both **out-of-the-box protections** and the flexibility to design **custom safety solutions** for generative AI applications.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>