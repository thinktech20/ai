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
# MAGIC # Demo - Tagging & Reproducible Agents
# MAGIC
# MAGIC This demonstration explores advanced MLflow tracing techniques for building production-ready AI agents. Building on foundational tracing concepts, we'll learn how to implement tagging strategies for better trace management and create reproducible agents through Unity Catalog registration.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC By the end of this demonstration, you will be able to:
# MAGIC
# MAGIC - Implement MLflow tagging strategies to organize and manage agent traces effectively
# MAGIC - Create custom trace functions with proper validation and error handling
# MAGIC - Log agent models to MLflow with appropriate configuration and dependencies
# MAGIC - Register agent models to Unity Catalog for governance and reproducibility
# MAGIC - Deploy and inference agents from both MLflow and Unity Catalog registries

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Environment Setup

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Compute Requirements
# MAGIC
# MAGIC **🚨 REQUIRED - SELECT SERVERLESS COMPUTE**
# MAGIC
# MAGIC This course has been configured to run on Serverless compute. While classic compute may also work, testing has been performed on serverless.
# MAGIC
# MAGIC **This demo was tested using version 5 of Serverless compute.** To ensure that you are using the correct version of Serverless, please [see this documentation on viewing and changing your notebook's Serverless version.](https://docs.databricks.com/aws/en/compute/serverless/dependencies)

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Install Dependencies
# MAGIC
# MAGIC As part of the workspace setup, several Python libraries will need to be installed. Run the next cell to do so.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-3.2

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Inspect the Airbnb Dataset
# MAGIC
# MAGIC As part of the classroom setup, the Airbnb dataset has been processed and stored as a Delta table within Unity Catalog. Run the next cell to query the first few rows of the dataset.

# COMMAND ----------

df = spark.read.table('sf_airbnb_listings')
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ### A4. Initialize MLflow Autologging
# MAGIC
# MAGIC MLflow's autologging automatically captures traces for supported frameworks like LangChain. When enabled, it records inputs, outputs, parameters, and metrics without requiring manual instrumentation.

# COMMAND ----------

import mlflow

mlflow.langchain.autolog()

# COMMAND ----------

# MAGIC %md
# MAGIC ### A5. Define Experiment Locations
# MAGIC
# MAGIC We'll create an experiment using the **default location** for the artifact and setting the experiment location to your **User** folder.
# MAGIC
# MAGIC > Workspace MLflow experiments cannot be created in Git folders; use a non-Git workspace experiment. Notebooks in Git folders can still log to their notebook experiment, but with management limitations.

# COMMAND ----------

# Get username
username = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()

experiment_name = f"/Workspace/Users/{username}/single_agents_demo3" 

# COMMAND ----------

# MAGIC %md
# MAGIC ### A6. Load the Agent
# MAGIC
# MAGIC We'll initialize our agent with MLflow autologging enabled and configure the experiment for trace collection. As a part of the classroom setup, we have created a config file called `demo_agent1_config.json` using a helper function (`create_demo_agent_config`) defined in the setup script. 
# MAGIC
# MAGIC > This course does not go into the details of how to build an agent, but rather assumes you have some experience with the concept of an agent.

# COMMAND ----------

# MAGIC %load_ext autoreload
# MAGIC %autoreload 2

# COMMAND ----------

import demo_agent1
agent = demo_agent1.DatabricksAgent(
    catalog_name=catalog_name,
    schema_name=schema_name
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Tagging Agents with MLflow
# MAGIC
# MAGIC Following the last example from the previous demo, we will look at custom tracing that validates the user's input before sending the request to the LLM.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Why Use Tags?
# MAGIC
# MAGIC Tags make trace management easier by allowing you to:
# MAGIC
# MAGIC - **Manage Sessions:** Group traces by user conversations or interaction sessions
# MAGIC - **Track Environments:** Differentiate between development, staging, and production runs
# MAGIC - **Version Models:** Identify which model version produced each trace
# MAGIC - **Add User Context:** Link traces to specific users or audience segments
# MAGIC - **Monitor Performance:** Label traces based on latency or throughput metrics
# MAGIC - **Support A/B Testing:** Mark traces from different experimental variants for comparison
# MAGIC
# MAGIC We will focus on active traces in this demonstration, but you can read more about different tag types [here](https://mlflow.org/docs/3.2.0/genai/tracing/attach-tags/#when-to-use-trace-tags).

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Setting Up Tags
# MAGIC
# MAGIC Let's set up our tags outside the `@mlflow.trace` decorator code. Below is an example of a set of tags we can pass through to the validation function that follows. The `tags` object is made up of key-value pairs.

# COMMAND ----------

tags = {
        "component": "input_validation",
        "stage": "preprocessing",
        "span_scope": "tool_function",
        "env": "dev",
        "trace_version": "v1.0.0",
        "input_type": "question"
    }

# COMMAND ----------

# MAGIC %md
# MAGIC ### B3. Import Required Libraries
# MAGIC
# MAGIC Let's bring in the necessary libraries for our tracing implementation. Recall from the previous demo that, for example, `span_type=SpanType.TOOL` classifies a function as a tool span in the trace UI, making it easier to identify different types of operations (like `FUNC`, `TOOL`, `CHAIN`, etc.) when reviewing traces. You can read more about span types [here](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/data-model#span-types).

# COMMAND ----------

from mlflow.entities import SpanType

# COMMAND ----------

# MAGIC %md
# MAGIC ### B4. Create Tagged Validation Function
# MAGIC
# MAGIC Now we will pass the tags through to the function using `mlflow.update_current_trace(tags)`. This will occur _inside_ the function definition. Again, keep in mind this is for an _active trace_.

# COMMAND ----------

@mlflow.trace(
    span_type=SpanType.TOOL, 
    name="Validate Input"
)
def validate_input(question: str, tags: dict, min_length: int = 5):
    """Check if the user's question meets basic requirements"""
    
    mlflow.update_current_trace(tags)

    if len(question) < min_length:
        return {
            "valid": False,
            "error": f"Question too short (minimum {min_length} characters)"
        }
    if question.strip() == "":
        return {
            "valid": False,
            "error": "Question cannot be empty"
        }
    return {
        "valid": True,
        "cleaned_question": question.strip()
    }

# COMMAND ----------

@mlflow.trace(
    name="Call LLM",
    span_type=SpanType.CHAT_MODEL
)
def call_llm(question: str):
    return agent.ask(question)

# COMMAND ----------

@mlflow.trace(name="Process Question")
def process_question(user_input: str, tags: dict):
    """Main function that validates input and calls LLM"""
    # Step 1: Validate the input
    validation_result = validate_input(user_input, tags)
    
    # Step 2: If valid, call the LLM
    cleaned = validation_result["cleaned_question"]
    llm_response = call_llm(cleaned)
    
    return llm_response

# COMMAND ----------

# MAGIC %md
# MAGIC ### B5. Test Tagged Tracing
# MAGIC
# MAGIC Define the prompt and test our tagged tracing implementation.

# COMMAND ----------

prompt = "Can you tell me the average for Mission?"

# COMMAND ----------

# MAGIC %md
# MAGIC Call `process_question` using the prompt and tags defined above. Notice the MLflow Trace UI now has an additional output called **Tags**.
# MAGIC
# MAGIC **Instructions:**
# MAGIC 1. Run the next cell
# MAGIC 2. Click on **Tags** to view the tags we set up with the variable `tags` defined above

# COMMAND ----------

# Test with a valid question
result = process_question(prompt, tags)

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Reproducible Agents
# MAGIC
# MAGIC Though we have an agent's trace and tags for `process_question`, we don't yet have code that can be shared with other teams for testing and further development, not to mention proper governance of our agent. We'll accomplish this in two steps:
# MAGIC 1. Log the agent with MLflow
# MAGIC 2. Register the model to Unity Catalog

# COMMAND ----------

# MAGIC %md
# MAGIC We'll start by using a custom function that will build the `demo_agent_config.json` file. This needs to be specific to the **catalog** and **schema** you are using in this lab environment. In practice, making this dynamic or static depends on your use case.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Read Agent Configuration
# MAGIC
# MAGIC The following prints a configuration file that defines your agent's settings and tools.

# COMMAND ----------

import json
# Read in Agent JSON config file 
with open('demo_agent2_config.json', 'r') as f:
    agent_config = json.load(f)
print(agent_config)

# COMMAND ----------

# MAGIC %reload_ext autoreload
# MAGIC %autoreload 2

# COMMAND ----------

from demo_agent2 import AGENT

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Logging the Agent to MLflow
# MAGIC
# MAGIC We'll log our agent as a PyFunc model to MLflow, including all necessary dependencies and configuration files using `with mlflow.start_run`. Additionally, we will add tags (`tags_to_register`) that designate the agent's framework (`openai`), the stage of development (`dev`), and the version number (`1`) for discoverability by other teams. We do this using `mlflow.set_tags(tags)`.
# MAGIC
# MAGIC **NOTE:** In the next cell we are bringing in additional modules that will be needed for logging with MLflow:
# MAGIC 1. The `pkg_resources` module and it is going to import the `get_distribution` function. This function is used to query the installed version of a Python package at runtime (in this case `databricks-connect`)
# MAGIC 2. The `mlflow.models.resources` module will enable automatic authentication passthrough for specified resources defined by `resources`. You can read more [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-authentication#implement-automatic-authentication-passthrough)

# COMMAND ----------

from importlib.metadata import version
from mlflow.models.resources import (
    DatabricksFunction,
    DatabricksTable,
    DatabricksServingEndpoint
)

input_example = {
    "input": [
        {
            "role": "user",
            "content": prompt
        }
    ]
}

model_name = "tagging-and-reproducible-agents"

tags_to_register = {
    "framework": "openai",
    "stage": "dev",
    "version": "1"
}

resources = [
    DatabricksFunction(function_name=agent_config["tool_list"][0]),
    DatabricksFunction(function_name=agent_config["tool_list"][1]),
    DatabricksTable(table_name=f"{catalog_name}.{schema_name}.sf_airbnb_listings"),
    DatabricksServingEndpoint(endpoint_name=agent_config["llm_endpoint"])
]

# COMMAND ----------

with mlflow.start_run():
    mlflow.set_tags(tags_to_register)
    logged_agent_info = mlflow.pyfunc.log_model(
        name=model_name,
        python_model="demo_agent2.py",
        code_paths=["demo_agent2_config.json"],
        input_example=input_example,
        pip_requirements=[
            "databricks-openai",
            "backoff",
            f"databricks-connect=={version('databricks-connect')}",
        ],
        resources=resources
    )
    model_uri = logged_agent_info.model_uri # Save the model URI to model_uri for use down below

# COMMAND ----------

# MAGIC %md
# MAGIC The output above will show **View Logged Model at: <url>**. Click on the URL and see that the model has been logged to MLflow, but not registered. Notice we have configured some tags as well (you can find and edit these tags in the `demo_agent2.py` file located in the same folder as this notebook).
# MAGIC
# MAGIC **Instructions:**
# MAGIC 1. On the landing page of the URL you clicked, navigate to **Runs**
# MAGIC 2. There, you will find a randomly named run like **tasteful-slug-677**. Click on it
# MAGIC 3. This will take you to the overview page for the run, where you will see 5 tabs at the top of the page. Click on **Artifacts**
# MAGIC 4. Under **Logged models artifacts**, click the dropdown menu for `tagging-and-reproducible-agents`. This contains all the various files that define the logged models with MLflow. We won't go into all the details here, but you can read more in this [documentation](https://docs.databricks.com/aws/en/mlflow/models)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C3. Inferencing the Agent from MLflow
# MAGIC
# MAGIC As part of the MLflow run, we have saved the model URI to the variable `model_uri`. Let's load our model and perform a simple inference with the agent using the logged input data (note this is the same as the `prompt` variable defined above). Read the output from this cell and see that our UC functions were indeed called and we were returned the response like _"The average listing price for Airbnb properties in the Mission neighborhood is approximately $229.76."_

# COMMAND ----------

# Load the model (pyfunc flavor)
pyfunc_model = mlflow.pyfunc.load_model(model_uri)

# The model is logged with an input example
input_data = pyfunc_model.input_example

# Verify the model with the provided input data using the logged dependencies.
result = mlflow.models.predict(
    model_uri=model_uri,
    input_data=input_data,
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C4. Registering the Agent to Unity Catalog
# MAGIC
# MAGIC Now that we have our model logged with MLflow, it's time to register it to Unity Catalog. Recall we defined `model_name` when logging our model to MLflow above.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
UC_MODEL_NAME = f"{catalog_name}.{schema_name}.{model_name}"

# register the model to UC
uc_registered_model_info = mlflow.register_model(
    model_uri=model_uri, 
    name=UC_MODEL_NAME
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C5. Inferencing the Agent from Unity Catalog
# MAGIC
# MAGIC Inferencing the model that's registered to UC is exactly the same as inferencing the logged agent with MLflow. We will simply need to update the URI using `mlflow.set_registry_uri("databricks-uc")` as shown in the next cell. Run the next cell and view the output.

# COMMAND ----------

import mlflow
from mlflow.types.responses import ResponsesAgentRequest

mlflow.set_registry_uri("databricks-uc")

# Load the model (pyfunc flavor)
pyfunc_model = mlflow.pyfunc.load_model(model_uri)

# The model is logged with an input example
input_data = pyfunc_model.input_example

# Verify the model with the provided input data using the logged dependencies.
result = mlflow.models.predict(
    model_uri=model_uri,
    input_data=input_data,
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C6. Exploring Unity Catalog Model Interface
# MAGIC
# MAGIC Note that all traces will be logged with MLflow. However, traces for UC-registered models will appear under that model's trace in UC's UI.
# MAGIC
# MAGIC **Instructions:**
# MAGIC Navigate to your model (located at `catalog_name.schema_name.tagging-and-reproducible-agents`) and click on the most recent version of the model. There, you will find four different tabs:
# MAGIC
# MAGIC - **Overview**: here you will see any metrics that have been logged with the model, activity log, the model's signature, information about the version, active endpoints, and tags
# MAGIC - **Lineage**: this will show this current notebook as an upstream asset
# MAGIC - **Artifacts**: these are the same artifacts that are registered to MLflow
# MAGIC - **Traces**: these are traces captured for this particular version

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this demonstration, we explored advanced techniques for building production-ready AI agents with MLflow and Unity Catalog. We learned how to:
# MAGIC
# MAGIC - Implement comprehensive tagging strategies for better trace organization and management
# MAGIC - Create robust validation functions with proper error handling and trace annotation
# MAGIC - Log agent models to MLflow with complete configuration and dependency management
# MAGIC - Register agents to Unity Catalog for enterprise governance and reproducibility
# MAGIC - Deploy and inference agents from both MLflow and Unity Catalog environments
# MAGIC
# MAGIC These techniques provide the foundation for building scalable, governed, and reproducible AI agent systems in production environments. The combination of MLflow tracing with Unity Catalog registration ensures that your agents are not only functional but also maintainable and compliant with enterprise standards.
# MAGIC
# MAGIC ## Next Steps
# MAGIC
# MAGIC If you have completed the previous demo, you are ready for the hands-on lab to test your knowledge and understanding of building reproducible agents with MLflow and Unity Catalog.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>