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
# MAGIC # Demo - Tracing Single Agents with MLflow
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC Observability is critical when building and deploying AI agents in production. Understanding what your agent is doing, how it's performing, and where issues arise can make the difference between a successful deployment and a failed one. This demonstration explores MLflow's tracing capabilities for single-agent applications, providing you with the tools to monitor, debug, and optimize your AI systems.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC _By the end of this demonstration, you will be able to:_
# MAGIC
# MAGIC - Configure MLflow experiments with both default and custom artifact locations for agent tracing
# MAGIC - Implement automatic tracing for LangChain agents using `mlflow.langchain.autolog()`
# MAGIC - Interpret trace outputs including token counts, latency metrics, and execution timelines
# MAGIC - Apply the `@mlflow.trace` decorator to add custom tracing to Python functions
# MAGIC - Analyze parent-child span relationships in complex multi-step agent workflows

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

# MAGIC %run ../Includes/Classroom-Setup-3.1

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Inspect the Airbnb Dataset 
# MAGIC As a part of the classroom setup, the Airbnb dataset has been processed and stored as a Delta table within Unity Catalog. Run the next cell to query the first few rows of the dataset.

# COMMAND ----------

df = spark.read.table('sf_airbnb_listings')
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ### A4. Initialize MLflow Autologging
# MAGIC
# MAGIC MLflow's autologging automatically captures traces for supported frameworks like LangChain. When enabled, it records inputs, outputs, parameters, metrics without requiring manual instrumentation, and much more. For more reading, please see this [link](https://mlflow.org/docs/latest/genai/flavors/langchain/autologging/). 

# COMMAND ----------

import mlflow

mlflow.langchain.autolog()

# COMMAND ----------

# MAGIC %md
# MAGIC ### A5. Define Experiment Locations
# MAGIC
# MAGIC We'll create two experiment configurations to demonstrate different artifact storage approaches:
# MAGIC
# MAGIC 1. **Default location**: Artifacts stored in the default workspace location
# MAGIC 2. **Custom location**: Artifacts stored in a Unity Catalog volume

# COMMAND ----------

# Get username
username = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()

experiment_name_1 = f"/Workspace/Users/{username}/single_agents_demo1" 
experiment_name_2 = f"/Workspace/Users/{username}/single_agents_demo2" 

artifact_path = f"dbfs:/Volumes/{catalog_name}/{schema_name}/agent_vol"

print(f"Experiment 1 name: {experiment_name_1}")
print(f"Experiment 2 name: {experiment_name_2}")
print(f"Artifact location: {artifact_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Understanding Agent Traces
# MAGIC
# MAGIC Before diving into implementation, let's understand what traces are and why they're essential for agent observability.
# MAGIC
# MAGIC A trace gives you visibility into what's happening inside your AI application by capturing each step as a "span." You can think of a trace like a detailed receipt—it shows what you asked the model, what it responded with, how long it took, and how much it cost in tokens.
# MAGIC
# MAGIC - For **simple** apps, this helps you understand performance and costs at a glance.
# MAGIC - For **complex multi-step** applications like agents or RAG systems, traces become even more powerful by revealing exactly how each component works together, making it easier to debug issues and optimize your application.

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Automatic Tracing with MLflow Experiments
# MAGIC
# MAGIC MLflow provides two methods for configuring where your experiment data and artifacts are stored: `set_experiment()` and `create_experiment()`. Let's explore both approaches.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Tracing with Default Artifact Location
# MAGIC
# MAGIC Using `set_experiment()` creates an experiment with artifacts stored in the default workspace location. This approach is straightforward and works well for development and testing.
# MAGIC
# MAGIC **Note:** This does _not_ register the model to Unity Catalog. It simply records the trace.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC 1. Run the next cell and view the output.
# MAGIC 2. Navigate to your User folder and see the experiment `single_agents_demo1`. Note that if you click on this experiment you will find there are no traces since we haven't called our agent yet. We'll do this next.

# COMMAND ----------

mlflow.set_experiment(experiment_name_1)

artifact_location = mlflow.get_experiment_by_name(experiment_name_1).artifact_location

print(f"Artifact location: {artifact_location}")

# COMMAND ----------

# MAGIC %md
# MAGIC #### C1.1 Load the Agent
# MAGIC
# MAGIC Next, let's bring in our simple agent defined in the `.py` file called `demo_agent1`.
# MAGIC
# MAGIC #### What does the agent do?
# MAGIC
# MAGIC The `demo_agent1.py` module defines a `DatabricksAgent` class that creates a conversational AI agent capable of calling Unity Catalog functions as tools. It loads configuration from a JSON file (including LLM endpoint, temperature, system prompt, and tool list), builds fully qualified function names using the provided catalog and schema, and sets up a LangChain agent executor. The class provides `query()` and `ask()` methods to interact with the agent using natural language prompts, with optional chat history support for conversational context.

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
# MAGIC #### C1.2 Test the Agent with Tracing
# MAGIC
# MAGIC Now we'll send a prompt to the agent and examine the resulting trace.

# COMMAND ----------

prompt = "Get the average for Mission."

# COMMAND ----------

# MAGIC %md
# MAGIC 1. Run the next cell to pass the prompt to the agent using the `ask()` method.
# MAGIC 2. Examine the trace output that appears below the cell.

# COMMAND ----------

agent.ask(prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC #### C1.3 Analyze the Trace Output
# MAGIC
# MAGIC The trace output provides rich information about your agent's execution. Let's explore what's available.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC - View the output at either the **Summary** level or the **Details & Timeline** tab. Both will show you that our agent used a single UC tool to help answer this question. You can also see the token count as well as the latency.
# MAGIC - Click on **Details & Timeline** and click on **Show execution time** (to the left of **Inputs / Outputs**). This will show you which components of the agent reasoning took the most/least time.
# MAGIC
# MAGIC ![Token count and latency view](../Includes/images/token-count-latency.png)
# MAGIC
# MAGIC - In **Details & Timeline**, click on **Attributes**. Here you can see metadata like model name, token counts (both input and output), and timing information.
# MAGIC
# MAGIC ![Execution time view](../Includes/images/show-execution-time.png)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Custom Artifact Location with Unity Catalog
# MAGIC
# MAGIC Next, let's see how we can change the artifact location to Unity Catalog. Using `create_experiment()` allows you to specify a custom artifact location, such as a Unity Catalog volume, for storing your agent's traces and artifacts.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC Run the next cell to create a new experiment based on `experiment_name_2` with the artifact path pointing to `artifact_path`. Note that there is some additional logic for error handling in case you happen to run the cell more than once.
# MAGIC > Note that when creating a new experiment with `mlflow.create_experiment()`, you will need to follow it up with `mlflow.set_experiment()`. 

# COMMAND ----------

experiment_status = mlflow.get_experiment_by_name(experiment_name_2)

if experiment_status is None:
    print("Experiment does not exist. Creating new experiment.")
    mlflow.create_experiment(
        name=experiment_name_2,
        artifact_location=artifact_path
    )
    mlflow.set_experiment(experiment_name_2)
else:
    print("Experiment already exists.")
    experiment_id = experiment_status.experiment_id
    mlflow.set_experiment(experiment_id=experiment_id)
    print(f"Experiment ID: {experiment_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC #### C2.1 Test with Custom Artifact Location
# MAGIC
# MAGIC Now let's call the agent again and see the artifacts stored in our custom Unity Catalog volume.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC 1. Run the next cell to call the agent with the same prompt.

# COMMAND ----------

agent.ask(prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC #### C2.2 Inspect Custom Artifact Storage
# MAGIC
# MAGIC Now we can see the custom artifact directory populate with our trace data.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC 1. Navigate to `agent_vol` in your Unity Catalog volume and see that there is a new folder corresponding to the trace ID shown above (see screenshot below for an example).
# MAGIC
# MAGIC ![Trace ID in volume](../Includes/images/trace-id.png)
# MAGIC
# MAGIC 2. Navigate to **agent_vol → Trace ID → artifacts → traces.json** and expand the JSON object. It will look something like the following image.
# MAGIC
# MAGIC ![JSON trace structure](../Includes/images/json-trace.png)

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Custom Tracing with the `@mlflow.trace` Decorator
# MAGIC
# MAGIC While automatic tracing works well for supported frameworks, you may need to trace custom Python functions or business logic. MLflow provides high-level APIs for manual tracing to handle these scenarios.

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Manual Tracing Approaches
# MAGIC
# MAGIC There are two ways to implement custom tracing:
# MAGIC
# MAGIC 1. **Using the `@mlflow.trace` decorator**: Best for function-level tracing with minimal code changes
# MAGIC 2. **Using the context manager**: Best for tracing code blocks and complex workflows
# MAGIC
# MAGIC We'll focus on the decorator approach in this demonstration. Keep in mind that low-level client APIs also exist, but these go beyond the scope of this demonstration. You can read more [here](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/manual-tracing/low-level-api).

# COMMAND ----------

# MAGIC %md
# MAGIC ### D2. Understanding the `@mlflow.trace` Decorator
# MAGIC
# MAGIC The `@mlflow.trace` decorator lets you add tracing to any function with just _one_ line of code: add `@mlflow.trace` above your function, and MLflow automatically captures what goes in, what comes out, how long it takes, and any errors that occur. We summarize the capabilities here, but you can read more about the decorator [here](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/manual-tracing/fluent-apis#context-manager).
# MAGIC
# MAGIC Key capabilities:
# MAGIC
# MAGIC - It understands parent-child relationships between functions and can work alongside auto-tracing features like `mlflow.langchain.autolog()`.
# MAGIC - The decorator supports all common function types including synchronous, asynchronous, and generator functions, making it flexible for any application architecture.
# MAGIC - To ensure complete observability, the `@mlflow.trace` decorator should generally be the outermost one when using [multiple decorators](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/manual-tracing/fluent-apis#using-mlflowtrace-with-other-decorators).

# COMMAND ----------

# MAGIC %md
# MAGIC ### D3. Example 1: Simple Function Tracing
# MAGIC
# MAGIC First, we will look at a simple example of using the `@mlflow.trace` decorator to add observability to custom Python functions. This example demonstrates how to trace functions that aren't automatically captured by framework integrations (like OpenAI or LangChain auto-tracing).
# MAGIC
# MAGIC In the cell below, we are using `@mlflow.trace` with a custom `span_type` parameter. The `span_type=SpanType.TOOL` classifies this as a tool span in the trace UI, making it easier to identify different types of operations (like `FUNC`, `TOOL`, `CHAIN`, etc.) when reviewing traces. You can read more about span types [here](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/data-model#span-types). Note that you can always pass a custom `str` value for `span_type`.
# MAGIC
# MAGIC > **What is a span?** Spans are used to record data about each of the steps within the application. When you see the trace within the MLflow UI, you are viewing a collection of spans. The name `span` is in reference to [OpenTelemetry traces](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/integrations/open-telemetry).
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC Run the next cell to create a simple Python validation function called `validate_input` that takes in a question and enforces a minimum length requirement. We also define `process_question`, which calls the validation function. Note, it's always best practice to test your custom traces prior to integrating with your agent.

# COMMAND ----------

import mlflow
from mlflow.entities import SpanType

@mlflow.trace(
    span_type=SpanType.TOOL, 
    name="Validate Input"
)
def validate_input(question: str, min_length: int = 5):
    """Check if the user's question meets basic requirements"""
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

@mlflow.trace(name="Process Question")
def process_question(user_input: str):
    """Process and validate user input"""
    # Step 1: Validate the input
    validation_result = validate_input(user_input)
    
    # Step 2: Process the question
    cleaned = validation_result["cleaned_question"]
    return f"Processing: {cleaned}"

# COMMAND ----------

# MAGIC %md
# MAGIC ### D4. Test the Traced Functions
# MAGIC
# MAGIC Let's test our traced functions with valid and invalid inputs.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC 1. Run the next cell and inspect the trace. Notice that `process_question` is the parent span and shows the overall process. The child span, `validate_input`, uses the user's input to perform a quick check to ensure the user met some basic requirements. The prompt given below will pass with no problem.

# COMMAND ----------

# Test with valid input
result = process_question("What is the average for Mission?")
print(result)

# COMMAND ----------

# MAGIC %md
# MAGIC 2. The next prompt **"Hi"** will fail because it does not meet the length requirements as defined in the `validate_input` function. Notice that in the output, MLflow handles the error and provides a report in the Trace UI under **Events** (see the screenshot below). Inspect **Events** to spot the issue under **exception.message** showing `cleaned_question`, which was configured as part of our error handling when defining `validate_input`. 
# MAGIC
# MAGIC ![MLflow trace error handling](../Includes/images/mlflow-trace-error.png)

# COMMAND ----------

# Test with invalid input - this will fail validation
result2 = process_question("Hi")
print(result2)

# COMMAND ----------

# MAGIC %md
# MAGIC ### D5. Example 2: Tracing LLM Calls with Custom Functions
# MAGIC
# MAGIC This example builds on the previous one by adding an LLM layer. We'll use the `validate_input` function defined above, but add an additional layer that passes the question to an LLM using the `call_llm` function defined below. This function will have the span type `CHAT_MODEL` passed to it, which represents a query to a chat model. This will call the same `agent` object defined previously (which has the ability to use tools defined in `demo_agent1_config.json`).

# COMMAND ----------

import mlflow
from mlflow.entities import SpanType

@mlflow.trace(
    name="Call LLM",
    span_type=SpanType.CHAT_MODEL
)
def call_llm(question: str):
    return agent.ask(question)

@mlflow.trace(name="Process Question")
def process_question(user_input: str):
    """Main function that validates input and calls LLM"""
    # Step 1: Validate the input
    validation_result = validate_input(user_input)
    
    # Step 2: If valid, call the LLM
    cleaned = validation_result["cleaned_question"]
    llm_response = call_llm(cleaned)
    
    return llm_response

# COMMAND ----------

# MAGIC %md
# MAGIC ### D6. Test the Multi-Step Traced Workflow
# MAGIC
# MAGIC Now let's test our complete workflow that includes validation and LLM interaction.
# MAGIC
# MAGIC #### Instructions
# MAGIC
# MAGIC 1. Run the next cell with a valid question and examine the trace hierarchy.
# MAGIC 2. Notice how the trace shows our custom trace as well as the UC tool when using `Call LLM`. 
# MAGIC
# MAGIC This is a pattern that allows for declarative tool calling while giving the agent the ability to use tools it has been equipped with. 

# COMMAND ----------

# Test with a valid question
result = process_question(prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC 3. Test with an invalid question to see how errors propagate through the trace. This is the same error we saw previously. 

# COMMAND ----------

# Test with an invalid question
result2 = process_question("Hi")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this demonstration, you explored comprehensive tracing strategies for single-agent applications using MLflow. You learned how to implement both automatic and manual tracing approaches, each serving different use cases in your agent development workflow.
# MAGIC
# MAGIC ## Next Steps
# MAGIC Now that you have an understanding of tracing single agents with MLflow, you can continue to learn about MLflow for tagging and building reproducible agents in the next demonstration.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>