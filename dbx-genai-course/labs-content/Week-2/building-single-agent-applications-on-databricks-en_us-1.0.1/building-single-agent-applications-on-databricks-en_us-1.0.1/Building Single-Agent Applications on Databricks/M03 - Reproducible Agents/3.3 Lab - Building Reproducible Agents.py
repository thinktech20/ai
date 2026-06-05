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
# MAGIC # Lab - Building Reproducible AI Agents with MLflow Tracing
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC In this hands-on lab, you'll apply the concepts learned in the previous demonstrations to build, trace, and register your own AI agent with Unity Catalog. You'll implement custom tracing functions, validate agent behavior, and register your agent to Unity Catalog for production use. This lab focuses on practical implementation skills that are essential for building robust, observable AI systems in enterprise environments.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC By the end of this lab, you will be able to:
# MAGIC
# MAGIC - Implement custom tracing functions with proper validation and error handling
# MAGIC - Apply MLflow tagging strategies to organize and categorize agent traces
# MAGIC - Create tool validation functions to ensure agents use appropriate tools
# MAGIC - Log and register AI agents to Unity Catalog with complete dependency management
# MAGIC - Log, register, and inference agents from both MLflow and Unity Catalog registries

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
# MAGIC **This demo was tested using version 5 of Serverless compute.** To ensure that you are using the correct version of Serverless, please [see this documentation on viewing and changing your notebook's Serverless verison.](https://docs.databricks.com/aws/en/compute/serverless/dependencies) 

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Install Dependencies
# MAGIC
# MAGIC Install the required Python libraries for MLflow tracing and agent functionality.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-3.3

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Inspect the Airbnb Dataset 
# MAGIC As a part of the classroom setup, the Airbnb dataset has been processed and stored as a Delta table within Unity Catalog. Run the next cell to query the first few rows of the dataset.

# COMMAND ----------

df = spark.read.table('sf_airbnb_listings')
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ### A4. Load the Agent
# MAGIC
# MAGIC Import the pre-configured agent that you'll be working with throughout this lab.
# MAGIC
# MAGIC **NOTE:** `mlflow.autolog` has been configured as a part of the agent's code, so we do not need to initiate it in this notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC We'll start by using a custom function that will build the `demo_agent_config.json` file. This needs to be specific to the **catalog** and **schema** you defined above. In practice, making this dynamic or static depends on your use case.

# COMMAND ----------

# Reload the agent module
%reload_ext autoreload
%autoreload 2

from lab_agent import AGENT as agent

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Custom Tracing with Tags
# MAGIC
# MAGIC In this section, you'll implement custom tracing functions with MLflow tags to organize and categorize your traces.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Define Trace Tags
# MAGIC
# MAGIC Create a tags dictionary that will help categorize and organize your traces. These tags will be applied to your custom tracing functions.

# COMMAND ----------

## Create a tags dictionary with the following keys and values:
## - component: "input_validation"
## - stage: "preprocessing" 
## - span_scope: "tool_function"
## - env: "dev"
## - trace_version: "v1.0.0"
## - input_type: "question"

tags = {
    "component": "input_validation",
    "stage": "preprocessing",
    "span_scope": "tool_function",
    "env": "dev",
    "trace_version": "v1.0.0",
    "input_type": "question"
}

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B1.1: Define Trace Tags ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC tags = {
# MAGIC     "component": "input_validation",
# MAGIC     "stage": "preprocessing",
# MAGIC     "span_scope": "tool_function",
# MAGIC     "env": "dev",
# MAGIC     "trace_version": "v1.0.0",
# MAGIC     "input_type": "question"
# MAGIC }
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Import Required Libraries
# MAGIC
# MAGIC Import the necessary MLflow libraries for custom tracing implementation. Specifically, bring in the module `SpanType` from `mlflow.entities`.

# COMMAND ----------

import mlflow 
from mlflow.entities import SpanType

# COMMAND ----------

# MAGIC %md
# MAGIC ### B3. Create Tool Validation Functions
# MAGIC
# MAGIC You'll create two helper agent tools (Python functions) that validate whether the agent used tools in its response. This is useful for ensuring your agent follows expected behavior patterns. This section will mimic what `lab_agent_update.py` is doing - but will focus on the fundamentals of custom tracing and testing your custom traces with tags. The step for integrating the code below into your agent has been completed for you and you can always view `lab_agent_update.py` for the full integration.
# MAGIC
# MAGIC The code present in this section is mostly complete, allowing you to focus on the MLflow aspect rather than the specific use case. However, feel free to add your own custom code as needed.

# COMMAND ----------

# MAGIC %md
# MAGIC #### B3.1 Tool Usage Validation Function
# MAGIC
# MAGIC This function checks whether the model response used a tool and returns structured results. Note most of the custom code has been created for you.

# COMMAND ----------

## Complete the validate_tool_usage function
## Use the @mlflow.trace decorator with span_type=SpanType.TOOL and name="Check Tool Usage"

@mlflow.trace(
    span_type=SpanType.TOOL,
    name="Check Tool Usage"
)
def validate_tool_usage(result):
    """Check whether the model response used a tool and return a structured result."""
    
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default) if hasattr(obj, key) else default

    # Extract outputs from result
    output_list = _get(result, "output", []) or []

    # Find tool usage
    tool_calls = [
        item for item in output_list
        if _get(item, "type") in ("function_call", "function_call_output")
    ]

    if not tool_calls:
        return {
            "used_tool": False,
            "error": "No tools were used during the model response.",
        }

    # Collect tool names and call IDs for debugging
    tools_info = [
        {
            "name": _get(item, "name"),
            "call_id": _get(item, "call_id"),
            "type": _get(item, "type"),
        }
        for item in tool_calls
    ]

    return {
        "used_tool": True,
        "tools": tools_info,
        "tool_count": len(tools_info)
    }

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B3.1: Tool Usage Validation Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC @mlflow.trace(
# MAGIC     span_type=SpanType.TOOL,
# MAGIC     name="Check Tool Usage"
# MAGIC )
# MAGIC def validate_tool_usage(result):
# MAGIC     """Check whether the model response used a tool and return a structured result."""
# MAGIC     
# MAGIC     def _get(obj, key, default=None):
# MAGIC         if isinstance(obj, dict):
# MAGIC             return obj.get(key, default)
# MAGIC         return getattr(obj, key, default) if hasattr(obj, key) else default
# MAGIC
# MAGIC     # Extract outputs from result
# MAGIC     output_list = _get(result, "output", []) or []
# MAGIC
# MAGIC     # Find tool usage
# MAGIC     tool_calls = [
# MAGIC         item for item in output_list
# MAGIC         if _get(item, "type") in ("function_call", "function_call_output")
# MAGIC     ]
# MAGIC
# MAGIC     if not tool_calls:
# MAGIC         return {
# MAGIC             "used_tool": False,
# MAGIC             "error": "No tools were used during the model response.",
# MAGIC         }
# MAGIC
# MAGIC     # Collect tool names and call IDs for debugging
# MAGIC     tools_info = [
# MAGIC         {
# MAGIC             "name": _get(item, "name"),
# MAGIC             "call_id": _get(item, "call_id"),
# MAGIC             "type": _get(item, "type"),
# MAGIC         }
# MAGIC         for item in tool_calls
# MAGIC     ]
# MAGIC
# MAGIC     return {
# MAGIC         "used_tool": True,
# MAGIC         "tools": tools_info,
# MAGIC         "tool_count": len(tools_info)
# MAGIC     }
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC #### B3.2 Response Evaluation Function
# MAGIC
# MAGIC This function evaluates the model response and raises an error if no tool was used. Note most of the code has been completed for you.

# COMMAND ----------

## Complete the evaluate_response function
## Use the @mlflow.trace decorator with name="Evaluate Response"

@mlflow.trace(name="Evaluate Response")
def evaluate_response(result):
    """Evaluate the model response and raise error if no tool was used."""
    
    validation = validate_tool_usage(result)
    
    if not validation["used_tool"]:
        # If no tool was used, explicitly raise an error
        raise ValueError(validation["error"])
    
    return {
        "message": f"{validation['tool_count']} tool(s) used successfully.",
        "details": validation["tools"]
    }

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B3.2: Response Evaluation Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC @mlflow.trace(name="Evaluate Response")
# MAGIC def evaluate_response(result):
# MAGIC     """Evaluate the model response and raise error if no tool was used."""
# MAGIC     
# MAGIC     validation = validate_tool_usage(result)
# MAGIC     
# MAGIC     if not validation["used_tool"]:
# MAGIC         # If no tool was used, explicitly raise an error
# MAGIC         raise ValueError(validation["error"])
# MAGIC     
# MAGIC     return {
# MAGIC         "message": f"{validation['tool_count']} tool(s) used successfully.",
# MAGIC         "details": validation["tools"]
# MAGIC     }
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### B4. Create LLM Call Function
# MAGIC
# MAGIC Create a traced function that calls the agent and captures the interaction. Note this time you will need to build your function from scratch.

# COMMAND ----------

## Create a function called call_llm that:
## - Uses the @mlflow.trace decorator with name="Call LLM" and span_type=SpanType.CHAT_MODEL
## - Takes a question parameter
## - Returns agent.predict(question)

@mlflow.trace(
    name="Call LLM",
    span_type=SpanType.CHAT_MODEL
)
def call_llm(question: str):
    return agent.predict(question)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B4.1: Create LLM Call Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC @mlflow.trace(
# MAGIC     name="Call LLM",
# MAGIC     span_type=SpanType.CHAT_MODEL
# MAGIC )
# MAGIC def call_llm(question: str):
# MAGIC     return agent.predict(question)
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### B5. Create Main Processing Function
# MAGIC
# MAGIC Create the main function that orchestrates the entire process, including tagging and validation. Note you will have to create this function from scratch with 3 main steps:
# MAGIC 1. Update the current trace with new tags
# MAGIC 2. Call the LLM using `call_llm()` you defined earlier
# MAGIC 3. Get the tool evaluation using `evaluate_response()`

# COMMAND ----------

## Create a function called process_question that:
## - Uses the @mlflow.trace decorator with name="Process Question"
## - Takes user_input and include_metadata parameters
## - Updates the current trace with tags using mlflow.update_current_trace(tags)
## - Calls call_llm with the user_input
## - Evaluates the response using evaluate_response
## - Handles ValueError exceptions and prints appropriate messages

@mlflow.trace(name="Process Question")
def process_question(user_input: str, include_metadata: bool = True):
    """Main function that calls LLM and formats response"""

    # Step 1: Update the current trace with new tags
    mlflow.update_current_trace(tags)
    
    # Step 2: Call the LLM
    llm_response = call_llm(user_input)
    
    # Step 3: Get tool evaluation
    try:
        summary = evaluate_response(llm_response)
        print(summary)
    except ValueError as e:
        print(f"Tool validation failed: {e}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B5.1: Create Main Processing Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC @mlflow.trace(name="Process Question")
# MAGIC def process_question(user_input: str, include_metadata: bool = True):
# MAGIC     """Main function that calls LLM and formats response"""
# MAGIC
# MAGIC     # Step 1: Update the current trace with new tags
# MAGIC     mlflow.update_current_trace(tags)
# MAGIC     
# MAGIC     # Step 2: Call the LLM
# MAGIC     llm_response = call_llm(user_input)
# MAGIC     
# MAGIC     # Step 3: Get tool evaluation
# MAGIC     try:
# MAGIC         summary = evaluate_response(llm_response)
# MAGIC         print(summary)
# MAGIC     except ValueError as e:
# MAGIC         print(f"Tool validation failed: {e}")
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Testing Custom Traces
# MAGIC
# MAGIC Now you will test your custom tracing implementation with different types of prompts.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Define Helper Functions and Test Prompts
# MAGIC
# MAGIC The following creates a helper function to format prompts and define test cases. We also define what a success/fail prompt looks like for proper testing based on the logic you built up above.

# COMMAND ----------

def format_prompt(prompt: str) -> dict:
    return {
        "input": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

# COMMAND ----------

# Define test prompts
success_prompt = "What is the price average for Mission?"
fail_prompt = "Hi!"

success_prompt_formatted = format_prompt(success_prompt)
fail_prompt_formatted = format_prompt(fail_prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Test Successful Tool Usage
# MAGIC
# MAGIC Test your tracing with a prompt that should trigger tool usage.

# COMMAND ----------

## Call process_question with success_prompt_formatted and tags
## This should result in successful tool usage

result = process_question(success_prompt_formatted, tags)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task C2.1: Test Successful Tool Usage ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC result = process_question(success_prompt_formatted, tags)
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### C3. Test Failed Tool Usage
# MAGIC
# MAGIC Test your tracing with a prompt that should not trigger tool usage.

# COMMAND ----------

## Call process_question with fail_prompt_formatted and tags
## This should result in a tool validation failure

result = process_question(fail_prompt_formatted, tags)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task C3.1: Test Failed Tool Usage ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC result = process_question(fail_prompt_formatted, tags)
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Agent MLflow Logging and UC Registration 
# MAGIC
# MAGIC In this section, you'll log your agent to MLflow and register it to Unity Catalog for production deployment. As a part of this classroom setup, there is a `.py` file named `lab_agent_update`. This file implements the custom tracing you filled out above but fit for using alongside `mlflow.types.responses`. Navigate to this file in the left side menu and scan the code for awareness before continuing.

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Read Agent Configuration
# MAGIC
# MAGIC The following prints a configuration file that defines your agent's settings and tools.

# COMMAND ----------

import json
# Read in Agent JSON config file 
with open('lab_agent_config.json', 'r') as f:
    agent_config = json.load(f)
print(agent_config)

# COMMAND ----------

# MAGIC %md
# MAGIC ### D2. Import Required Resources
# MAGIC
# MAGIC Import the necessary MLflow resources for Unity Catalog integration. You will need to bring the proper libraries that will allow the model to access:
# MAGIC - Functions registered to Unity Catalog
# MAGIC - Tables registered to Unity Catalog
# MAGIC - Model serving endpoints hosted by Databricks
# MAGIC
# MAGIC **NOTE:** For a review of the proper libraries, please see [this documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-authentication#implement-automatic-authentication-passthrough).

# COMMAND ----------

## Import the required classes from mlflow.models.resources

from importlib.metadata import version
from mlflow.models.resources import (
    DatabricksFunction,
    DatabricksTable,
    DatabricksServingEndpoint
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D2.1: Import Required Resources ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC from importlib.metadata import version
# MAGIC from mlflow.models.resources import (
# MAGIC     DatabricksFunction,
# MAGIC     DatabricksTable,
# MAGIC     DatabricksServingEndpoint
# MAGIC )
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D3. Define Model Metadata
# MAGIC
# MAGIC Set up the input example, model name, and registration tags. Below is an example of metadata that you need to log with your model. Feel free to update them as needed:
# MAGIC - Input example
# MAGIC - Model name
# MAGIC - Tags

# COMMAND ----------

input_example = format_prompt(success_prompt)

model_name = "reproducible-agents-lab"

tags_to_register = {
    "framework": "openai",
    "stage": "dev",
    "version": "1"
}

# COMMAND ----------

# MAGIC %md
# MAGIC ### D4. Configure Resources
# MAGIC
# MAGIC Define the Unity Catalog resources that your agent will use. Note this list should contain the same libraries you brought in earlier.
# MAGIC - Recall `agent_config` contains the tool list created earlier along with the endpoint name
# MAGIC - Also recall that at the start of this lab, a table was created for you called `sf_airbnb_listings`, which is what our tools' logic is based on

# COMMAND ----------

## Create a resources list with:

resources = [
    DatabricksFunction(function_name=f"{agent_config.get('tool_list')[0]}"),
    DatabricksFunction(function_name=f"{agent_config.get('tool_list')[1]}"),
    DatabricksTable(table_name=f"{catalog_name}.{schema_name}.sf_airbnb_listings"),
    DatabricksServingEndpoint(endpoint_name=agent_config['llm_endpoint'])
]

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D4.1: Configure Resources ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC resources = [
# MAGIC     DatabricksFunction(function_name=f"{agent_config.get('tool_list')[0]}"),
# MAGIC     DatabricksFunction(function_name=f"{agent_config.get('tool_list')[1]}"),
# MAGIC     DatabricksTable(table_name=f"{catalog_name}.{schema_name}.sf_airbnb_listings"),
# MAGIC     DatabricksServingEndpoint(endpoint_name=agent_config['llm_endpoint'])
# MAGIC ]
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D5. Load Updated Agent
# MAGIC
# MAGIC Load the updated agent that includes your custom tracing functionality.

# COMMAND ----------

# MAGIC %reload_ext autoreload
# MAGIC %autoreload 2
# MAGIC
# MAGIC from lab_agent_update import AGENT as updated_agent

# COMMAND ----------

# MAGIC %md
# MAGIC ### D6. Test Updated Agent
# MAGIC
# MAGIC Verify that your updated agent works correctly before logging it. Recall we had our two variables `success_prompt_formatted` and `fail_prompt_formatted` that succeeded and failed, respectively, during our testing in section **B. Custom Tracing with Tags**.

# COMMAND ----------

updated_agent.predict(success_prompt_formatted)

# COMMAND ----------

try:
    updated_agent.predict(fail_prompt_formatted)
except ValueError as e:
    print(f"Expected failure — Tool validation error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### D7. Log Agent to MLflow
# MAGIC
# MAGIC Log your agent to MLflow with all necessary dependencies and configuration.

# COMMAND ----------

## Complete the MLflow logging process:
## - Start an MLflow run
## - Set tags using mlflow.set_tags()
## - Log the model using mlflow.pyfunc.log_model() with appropriate parameters
## - Save the model URI for later use

with mlflow.start_run():
    mlflow.set_tags(tags_to_register)
    logged_agent_info = mlflow.pyfunc.log_model(
        name=model_name,
        python_model="lab_agent_update.py",
        code_paths=["lab_agent_config.json"],
        input_example=input_example,
        pip_requirements=[
            "databricks-openai",
            "backoff",
            f"databricks-connect=={version('databricks-connect')}",
        ],
        resources=resources
    )
    model_uri = logged_agent_info.model_uri

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D7.1: Log Agent to MLflow ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC with mlflow.start_run():
# MAGIC     mlflow.set_tags(tags_to_register)
# MAGIC     logged_agent_info = mlflow.pyfunc.log_model(
# MAGIC         name=model_name,
# MAGIC         python_model="lab_agent_update.py",
# MAGIC         code_paths=["lab_agent_config.json"],
# MAGIC         input_example=input_example,
# MAGIC         pip_requirements=[
# MAGIC             "databricks-openai",
# MAGIC             "backoff",
# MAGIC             f"databricks-connect=={version('databricks-connect')}",
# MAGIC         ],
# MAGIC         resources=resources
# MAGIC     )
# MAGIC     model_uri = logged_agent_info.model_uri
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D8. Test MLflow Model Inference
# MAGIC
# MAGIC Test your logged model to ensure it works correctly.

# COMMAND ----------

## Load the model (pyfunc flavor)
## The model is logged with the input example you defined earlier
## Verify the model with the provided input data using the logged dependencies

pyfunc_model = mlflow.pyfunc.load_model(model_uri)

input_data = pyfunc_model.input_example

result = mlflow.models.predict(
    model_uri=model_uri,
    input_data=input_data,
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D8.1: Test MLflow Model Inference ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Load the model (pyfunc flavor)
# MAGIC # The model is logged with the input example you defined earlier
# MAGIC # Verify the model with the provided input data using the logged dependencies
# MAGIC
# MAGIC pyfunc_model = mlflow.pyfunc.load_model(model_uri)
# MAGIC
# MAGIC input_data = pyfunc_model.input_example
# MAGIC
# MAGIC result = mlflow.models.predict(
# MAGIC     model_uri=model_uri,
# MAGIC     input_data=input_data,
# MAGIC     env_manager="uv",
# MAGIC )
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D9. Register Agent to Unity Catalog
# MAGIC
# MAGIC Register your agent to Unity Catalog for governance and production deployment.

# COMMAND ----------

## Complete the Unity Catalog registration:
## - Set the registry URI to "databricks-uc"
## - Create the UC model name using catalog, schema, and model name
## - Register the model using mlflow.register_model()

mlflow.set_registry_uri("databricks-uc")
UC_MODEL_NAME = f"{catalog_name}.{schema_name}.{model_name}"

uc_registered_model_info = mlflow.register_model(
    model_uri=model_uri, 
    name=UC_MODEL_NAME
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D9.1: Register Agent to Unity Catalog ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC mlflow.set_registry_uri("databricks-uc")
# MAGIC UC_MODEL_NAME = f"{catalog_name}.{schema_name}.{model_name}"
# MAGIC
# MAGIC uc_registered_model_info = mlflow.register_model(
# MAGIC     model_uri=model_uri, 
# MAGIC     name=UC_MODEL_NAME
# MAGIC )
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC const el = document.getElementById("copy-block");
# MAGIC if (!el) return;
# MAGIC
# MAGIC const text = el.innerText;
# MAGIC
# MAGIC // Preferred modern API
# MAGIC if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC navigator.clipboard.writeText(text)
# MAGIC .then(() => alert("Copied to clipboard"))
# MAGIC .catch(err => {
# MAGIC console.error("Clipboard write failed:", err);
# MAGIC fallbackCopy(text);
# MAGIC });
# MAGIC } else {
# MAGIC fallbackCopy(text);
# MAGIC }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC const textarea = document.createElement("textarea");
# MAGIC textarea.value = text;
# MAGIC textarea.style.position = "fixed";
# MAGIC textarea.style.left = "-9999px";
# MAGIC document.body.appendChild(textarea);
# MAGIC textarea.select();
# MAGIC try {
# MAGIC document.execCommand("copy");
# MAGIC alert("Copied to clipboard");
# MAGIC } catch (err) {
# MAGIC console.error("Fallback copy failed:", err);
# MAGIC alert("Could not copy to clipboard. Please copy manually.");
# MAGIC } finally {
# MAGIC document.body.removeChild(textarea);
# MAGIC }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D10. Test Unity Catalog Model Inference
# MAGIC
# MAGIC Test your Unity Catalog registered model to ensure it works correctly and verify that the trace appears in the UI by navigating to your model (located at `catalog_name.schema_name.reproducible-agents-lab`) and click on the most recent version of the model. There, you will find **Traces** - click on it and view the trace after running the next cell.

# COMMAND ----------

import mlflow
from mlflow.types.responses import ResponsesAgentRequest

# Load the model (pyfunc flavor)
pyfunc_model = mlflow.pyfunc.load_model(model_uri)

# The model is logged with an input example
input_data = format_prompt("What is the price average for Haight Ashbury")

# Verify the model with the provided input data using the logged dependencies
result = mlflow.models.predict(
    model_uri=model_uri,
    input_data=input_data,
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC By completing this lab, you have successfully completed this lab on building reproducible AI agents with MLflow tracing. Throughout this hands-on exercise, you have:
# MAGIC
# MAGIC - **Implemented custom tracing functions** with proper validation and error handling to monitor agent behavior
# MAGIC - **Applied MLflow tagging strategies** to organize and categorize traces for better observability and debugging
# MAGIC - **Created tool validation functions** that ensure your agents use appropriate tools and follow expected behavior patterns
# MAGIC - **Logged and registered AI agents** to Unity Catalog with complete dependency management for production deployment
# MAGIC - **Successfully registered and tested agents** from both MLflow and Unity Catalog registries
# MAGIC
# MAGIC These skills are essential for building production-ready AI systems that are observable, reproducible, and governable.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>