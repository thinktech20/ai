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
# MAGIC # Lab - Building Single Agents with LangChain
# MAGIC
# MAGIC ##Overview 
# MAGIC
# MAGIC In this hands-on lab, you will build AI agents that leverage Unity Catalog (UC) functions as tools within the LangChain framework. You will create UC functions for analyzing NYC taxi trip data, integrate them with LangChain toolkits, and build an agent capable of reasoning and taking action using foundation models hosted in Mosaic AI Model Serving.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC By the end of this lab, you will be able to:
# MAGIC - Test pre-built Unity Catalog functions independently before agent integration
# MAGIC - Configure and integrate Unity Catalog functions with LangChain using the `UCFunctionToolkit`
# MAGIC - Build and execute a LangChain agent with tool-calling capabilities
# MAGIC - Analyze agent execution traces using MLflow for debugging and optimization
# MAGIC
# MAGIC **Note**: Before starting this lab, it is highly recommended that you first complete the previous demonstration.

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Environment Setup and Prerequisites

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
# MAGIC As part of the workspace setup, several Python libraries have been installed. To see the list of notebook-scoped libraries, please read [this documentation](https://docs.databricks.com/aws/en/compute/serverless/dependencies#configure-environment-for-job-tasks). 
# MAGIC
# MAGIC **NOTE:** If you are familiar with `langchain-databricks`, note that `databricks-langchain` replaces it. This lab uses LangChain, but a similar approach can be applied to other libraries.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-2.2

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Inspect NYC Taxi Dataset
# MAGIC
# MAGIC The dataset that will be used for this lab will come from the table `samples.nyctaxi.trips`, which is a sample dataset that [is available by default on UC-enabled workspaces](https://docs.databricks.com/aws/en/discover/databricks-datasets). Run the next cell to query the first few rows of the dataset. 

# COMMAND ----------

df = spark.read.table('samples.nyctaxi.trips')
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Initialize the Databricks Function Client
# MAGIC
# MAGIC The `DatabricksFunctionClient` provides a programmatic interface for executing Unity Catalog functions. We configure it for serverless execution mode to align with our compute requirements.
# MAGIC
# MAGIC **TODO**: Initialize the client for serverless compute.

# COMMAND ----------

from unitycatalog.ai.core.databricks import DatabricksFunctionClient

## Initialize the client for serverless compute
client = DatabricksFunctionClient(execution_mode="serverless")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B: Initialize the Databricks Function Client ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC from unitycatalog.ai.core.databricks import DatabricksFunctionClient
# MAGIC
# MAGIC # Initialize the client for serverless compute
# MAGIC client = DatabricksFunctionClient(execution_mode="serverless")
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



from unitycatalog.ai.core.databricks import DatabricksFunctionClient

# Initialize the client for serverless compute
client = DatabricksFunctionClient(execution_mode="serverless")



# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Inspect Functions Before Agent Integration
# MAGIC As a part of the classroom setup, 2 agent tools have been created for you:
# MAGIC 1. `avg_fare_by_zip`: Calculates the average fare amount for trips from a specific pickup ZIP code. Returns the average fare as a numeric value.
# MAGIC 1. `cnt_lng_dist_trip`: Counts the number of trips longer than the specified distance from a given pickup ZIP code. Returns the count as an integer.
# MAGIC
# MAGIC ### UI Inspection Instructions
# MAGIC 1. **Navigate to the Catalog**
# MAGIC - In the left sidebar, click **Catalog**.
# MAGIC
# MAGIC 2. **Locate Your Workspace Catalog and Schema**
# MAGIC - Open the **dbacademy** catalog.
# MAGIC - Select the schema that begins with **labuser** (this is the schema you have been working in).
# MAGIC
# MAGIC 3. **View Functions**
# MAGIC - Click on **Functions** in the schema sidebar.
# MAGIC - Locate the functions `avg_fare_by_zip` and `cnt_lng_dist_trip`
# MAGIC
# MAGIC 4. **Inspect Function Details**
# MAGIC - Click on a function name to open its details.
# MAGIC - Review:
# MAGIC - **Comments on input parameters**
# MAGIC - **The referenced table or data source**
# MAGIC - **Additional metadata** associated with the function

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Test Functions Before Agent Integration
# MAGIC
# MAGIC Before integrating these functions into our agent, let's verify they work correctly by testing them directly with SQL queries.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO
# MAGIC -- -- Test the average fare function with ZIP code 10001
# MAGIC SELECT avg_fare_by_zip(10001) AS manhattan_avg_fare;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task C1.1: Test Average Fare Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC -- Test the average fare function with ZIP code 10001
# MAGIC SELECT avg_fare_by_zip(10001) AS manhattan_avg_fare;
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

# MAGIC %sql
# MAGIC
# MAGIC
# MAGIC -- Test the average fare function with ZIP code 10001
# MAGIC SELECT avg_fare_by_zip(10001) AS manhattan_avg_fare;
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC
# MAGIC
# MAGIC -- Test the average fare function with ZIP code 10001
# MAGIC SELECT avg_fare_by_zip(10001) AS manhattan_avg_fare;
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO
# MAGIC -- -- Test the long distance trips function with ZIP code 10001 and minimum distance of 10 miles
# MAGIC SELECT cnt_lng_dist_trip(10001, 10.0) AS long_trips_count;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task C1.2: Test Long Distance Trips Function ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC -- Test the long distance trips function with ZIP code 10001 and minimum distance of 10 miles
# MAGIC SELECT cnt_lng_dist_trip(10001, 10.0) AS long_trips_count;
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

# MAGIC %sql
# MAGIC
# MAGIC
# MAGIC -- Test the long distance trips function with ZIP code 10001 and minimum distance of 10 miles
# MAGIC SELECT cnt_lng_dist_trip(10001, 10.0) AS long_trips_count;
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Integrate Unity Catalog Functions with LangChain
# MAGIC
# MAGIC Now that we know the functions work with basic SQL, we'll leverage `databricks_langchain` to wrap our UC functions as tools that can be directly integrated into LangChain. The first step is to define the tool list, which we will do next.

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Define the Tool List
# MAGIC
# MAGIC **TODO:** Create a list of the functions we want to use and format them with the catalog and schema names (this is a requirement for our agent framework).

# COMMAND ----------

tool_list_raw = [
    'avg_fare_by_zip',
    'cnt_lng_dist_trip'
]

function_names = []
for tool in tool_list_raw:
    tool = catalog_name + '.' + schema_name + '.' + tool
    function_names.append(tool)

print(f"Tool list: {function_names}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D1: Define the Tool List ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC tool_list_raw = [
# MAGIC 'avg_fare_by_zip',
# MAGIC 'cnt_lng_dist_trip'
# MAGIC ]
# MAGIC
# MAGIC function_names = []
# MAGIC for tool in tool_list_raw:
# MAGIC   tool = catalog_name + '.' + schema_name + '.' + tool
# MAGIC   function_names.append(tool)
# MAGIC
# MAGIC print(f"Tool list: {function_names}")
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



tool_list_raw = [
'avg_fare_by_zip',
'cnt_lng_dist_trip'
]

function_names = []
for tool in tool_list_raw:
  tool = catalog_name + '.' + schema_name + '.' + tool
  function_names.append(tool)

print(f"Tool list: {function_names}")



# COMMAND ----------

# MAGIC %md
# MAGIC ### D2. Create the UCFunctionToolkit
# MAGIC
# MAGIC **TODO:** Create the toolkit that wraps our Unity Catalog functions and makes them available as LangChain tools using `UCFunctionToolkit`.

# COMMAND ----------

from databricks_langchain import UCFunctionToolkit

## Create a toolkit with the Unity Catalog functions
toolkit = UCFunctionToolkit(function_names=function_names)
tools = toolkit.tools

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D2: Create the UCFunctionToolkit ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC from databricks_langchain import UCFunctionToolkit
# MAGIC
# MAGIC # Create a toolkit with the Unity Catalog functions
# MAGIC toolkit = UCFunctionToolkit(function_names=function_names)
# MAGIC tools = toolkit.tools
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



from databricks_langchain import UCFunctionToolkit

# Create a toolkit with the Unity Catalog functions
toolkit = UCFunctionToolkit(function_names=function_names)
tools = toolkit.tools



# COMMAND ----------

# MAGIC %md
# MAGIC ### D3. Test the Toolkit
# MAGIC Finally we are ready to test our toolkit. Note that the outputs from the following query will be the exact same as above since only the syntax for the query has changed from SQL to using `client.execute_function()`
# MAGIC > Recall that `client` is defined as `client = DatabricksFunctionClient(execution_mode="serverless")` from your work above.
# MAGIC
# MAGIC **TODO:** Test the toolkit by executing sample payloads using the `DatabricksFunctionClient`.

# COMMAND ----------

## Test the first tool (average fare by pickup ZIP)
payload1 = {'pickup_zip_code': 10001}
payload1_test_result = client.execute_function(
    function_name=tools[0].uc_function_name,
    parameters=payload1
)
print(payload1_test_result.value)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D3.1: Test First Tool ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Test the first tool (average fare by pickup ZIP)
# MAGIC payload1 = {'pickup_zip_code': 10001}
# MAGIC payload1_test_result = client.execute_function(
# MAGIC function_name=tools[0].uc_function_name,
# MAGIC parameters=payload1
# MAGIC )
# MAGIC print(payload1_test_result.value)
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



# Test the first tool (average fare by pickup ZIP)
payload1 = {'pickup_zip_code': 10001}
payload1_test_result = client.execute_function(
function_name=tools[0].uc_function_name,
parameters=payload1
)
print(payload1_test_result.value)



# COMMAND ----------

## Test the second tool (count long distance trips)
payload2 = {
    'pickup_zip_code': 10001,
    'min_distance': 10.0
}
payload2_test_result = client.execute_function(
    function_name=tools[1].uc_function_name,
    parameters=payload2
)
print(payload2_test_result.value)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D3.2: Test Second Tool ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Test the second tool (count long distance trips)
# MAGIC payload2 = {
# MAGIC 'pickup_zip_code': 10001,
# MAGIC 'min_distance': 10.0
# MAGIC }
# MAGIC payload2_test_result = client.execute_function(
# MAGIC   function_name=tools[1].uc_function_name,
# MAGIC   parameters=payload2
# MAGIC )
# MAGIC print(payload2_test_result.value)
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



# Test the second tool (count long distance trips)
payload2 = {
'pickup_zip_code': 10001,
'min_distance': 10.0
}
payload2_test_result = client.execute_function(
  function_name=tools[1].uc_function_name,
  parameters=payload2
)
print(payload2_test_result.value)



# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Configure and Execute the Agent
# MAGIC
# MAGIC Now that we have our toolkit configured and tested, we're ready to create an agent configuration file that will be decoupled from the agent code. As a part of the classroom setup, a JSON file has been loaded into the same directory where this lab is located, called `lab_agent.json`.
# MAGIC 1. Navigate to the left menu and inspect the file `lab_agent.json` before completing the next task.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E1. Load Agent Configuration
# MAGIC
# MAGIC **TODO:** Load the agent configuration from the JSON file and extract the necessary parameters.

# COMMAND ----------

import json

## Load JSON file
with open("./lab_agent.json", "r") as f:
    config = json.load(f)

llm_endpoint = config['llm_endpoint']
llm_temperature = config['llm_temperature']
system_prompt = config['system_prompt']

print("Endpoint:", llm_endpoint)
print("Temperature:", llm_temperature)
print("System Prompt:", system_prompt)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task E1: Load Agent Configuration ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC import json
# MAGIC
# MAGIC # Load JSON file
# MAGIC with open("./lab_agent.json", "r") as f:
# MAGIC   config = json.load(f)
# MAGIC
# MAGIC llm_endpoint = config['llm_endpoint']
# MAGIC llm_temperature = config['llm_temperature']
# MAGIC system_prompt = config["system_prompt"]
# MAGIC
# MAGIC print("Endpoint:", llm_endpoint)
# MAGIC print("Temperature:", llm_temperature)
# MAGIC print("System Prompt:", system_prompt)
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



import json

# Load JSON file
with open("./lab_agent.json", "r") as f:
  config = json.load(f)

llm_endpoint = config['llm_endpoint']
llm_temperature = config['llm_temperature']
system_prompt = config["system_prompt"]

print("Endpoint:", llm_endpoint)
print("Temperature:", llm_temperature)
print("System Prompt:", system_prompt)



# COMMAND ----------

# MAGIC %md
# MAGIC ### E2. Import Required Libraries and Initialize Components
# MAGIC
# MAGIC **TODO:** Import the necessary libraries and initialize the language model using `ChatDatabricks`.

# COMMAND ----------

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate
from databricks_langchain import ChatDatabricks
import mlflow

## Initialize the language model using ChatDatabricks
llm_config = ChatDatabricks(
    endpoint=llm_endpoint,
    temperature=llm_temperature
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task E2: Initialize Language Model ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC from langchain.agents import AgentExecutor, create_tool_calling_agent
# MAGIC from langchain.prompts import ChatPromptTemplate
# MAGIC from databricks_langchain import ChatDatabricks
# MAGIC import mlflow
# MAGIC
# MAGIC # Initialize the language model
# MAGIC llm_config = ChatDatabricks(
# MAGIC   endpoint=llm_endpoint,
# MAGIC   temperature=llm_temperature
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



from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate
from databricks_langchain import ChatDatabricks
import mlflow

# Initialize the language model
llm_config = ChatDatabricks(
  endpoint=llm_endpoint,
  temperature=llm_temperature
)



# COMMAND ----------

# MAGIC %md
# MAGIC ### E3. Define the Prompt Template
# MAGIC
# MAGIC **TODO:** Create the prompt template using the _system prompt_ and conversation structure.

# COMMAND ----------

prompt_payload = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            system_prompt,
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task E3: Define Prompt Template ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC prompt_payload = ChatPromptTemplate.from_messages(
# MAGIC   [
# MAGIC     (
# MAGIC       "system",
# MAGIC       system_prompt,
# MAGIC     ),
# MAGIC     ("placeholder", "{chat_history}"),
# MAGIC     ("human", "{input}"),
# MAGIC     ("placeholder", "{agent_scratchpad}"),
# MAGIC   ]
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



prompt_payload = ChatPromptTemplate.from_messages(
  [
    (
      "system",
      system_prompt,
    ),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
  ]
)



# COMMAND ----------

# MAGIC %md
# MAGIC ### E4. Enable MLflow Tracing and Create Agent Configuration
# MAGIC
# MAGIC **TODO:** Enable MLflow autologging and create the agent configuration using `create_tool_calling_agent` from the `langchain` library.

# COMMAND ----------

## Enable MLflow tracing
mlflow.langchain.autolog()

## Create the agent configuration
agent_config = create_tool_calling_agent(
    llm_config,
    tools,
    prompt_payload
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task E4: Enable MLflow and Create Agent ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Enable MLflow tracing
# MAGIC mlflow.langchain.autolog()
# MAGIC
# MAGIC # Create the agent configuration
# MAGIC agent_config = create_tool_calling_agent(
# MAGIC   llm_config,
# MAGIC   tools,
# MAGIC   prompt_payload
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



# Enable MLflow tracing
mlflow.langchain.autolog()

# Create the agent configuration
agent_config = create_tool_calling_agent(
  llm_config,
  tools,
  prompt_payload
)



# COMMAND ----------

# MAGIC %md
# MAGIC ### E5. Execute the Agent
# MAGIC
# MAGIC **TODO:** Create the agent executor and run it with a query about NYC taxi data use `AgentExecutor()` and get the response.
# MAGIC
# MAGIC **Bonus**: Construct a query that will call both tools.

# COMMAND ----------

agent_executor = AgentExecutor(agent=agent_config, tools=tools, verbose=True)
response = agent_executor.invoke(
    {
        "input": "What's the average fare for trips from ZIP code 10001 and how many trips from that ZIP code are longer than 15 miles?"
    }
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task E5: Execute the Agent ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC agent_executor = AgentExecutor(agent=agent_config, tools=tools, verbose=True)
# MAGIC response = agent_executor.invoke(
# MAGIC   {
# MAGIC     "input": "What's the average fare for trips from ZIP code 10001 and how many trips from that ZIP code are longer than 15 miles?"
# MAGIC   }
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



agent_executor = AgentExecutor(agent=agent_config, tools=tools, verbose=True)
response = agent_executor.invoke(
  {
    "input": "What's the average fare for trips from ZIP code 10001 and how many trips from that ZIP code are longer than 15 miles?"
  }
)



# COMMAND ----------

# MAGIC %md
# MAGIC ## F. Analyze Agent Response and Tracing

# COMMAND ----------

# MAGIC %md
# MAGIC ### F1. Parse the Agent's Response
# MAGIC
# MAGIC **TODO:** Extract and display the agent's response in a readable format.

# COMMAND ----------

## Extract text segments from the response
output_segments = response['output']

print(output_segments)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task F1: Parse Agent Response ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Extract text segments from the response
# MAGIC output_segments = response['output']
# MAGIC
# MAGIC print(output_segments)
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



# Extract text segments from the response
output_segments = response['output']

print(output_segments)



# COMMAND ----------

# MAGIC %md
# MAGIC ### F2. Experiment with Different Queries
# MAGIC
# MAGIC **TODO:** Try running the agent with different queries to test its capabilities.
# MAGIC
# MAGIC **Bonus**: Create a query that demonstrates the agent's ability to search among different input values like supplying more than one ZIP code.

# COMMAND ----------

## Try a different query
custom_response = agent_executor.invoke(
    {
        "input": "Compare the average fare for ZIP codes 10001 and 10002, and tell me which one has more trips over 20 miles"
    }
)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task F2: Experiment with Different Queries ANSWER
# MAGIC <details>
# MAGIC <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC # Try a different query
# MAGIC custom_response = agent_executor.invoke(
# MAGIC   {
# MAGIC     "input": "Compare the average fare for ZIP codes 10001 and 10002, and tell me which one has more trips over 20 miles"
# MAGIC   }
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



# Try a different query
custom_response = agent_executor.invoke(
  {
    "input": "Compare the average fare for ZIP codes 10001 and 10002, and tell me which one has more trips over 20 miles"
  }
)



# COMMAND ----------

# MAGIC %md
# MAGIC ## G. Review and Analysis
# MAGIC
# MAGIC ### MLflow Trace Analysis
# MAGIC
# MAGIC Review the MLflow Trace UI that appears in the outputs above. Click on the **Summary** tab to see:
# MAGIC
# MAGIC - **Which tools were called**: Both tools should have been invoked for the queries
# MAGIC - **What parameters were passed**: Examine the inputs to each UC function
# MAGIC - **The results returned from each tool**: Review the numeric outputs
# MAGIC - **The final response generated by the agent**: See how the LLM synthesized the tool results
# MAGIC
# MAGIC ### Key Observations
# MAGIC
# MAGIC Based on your agent execution, consider:
# MAGIC
# MAGIC 1. **Tool Selection**: Did the agent choose the appropriate tools for each query?
# MAGIC 2. **Parameter Passing**: Were the correct parameters passed to each function?
# MAGIC 3. **Response Quality**: How well did the agent synthesize the tool results into a coherent answer?
# MAGIC 4. **Error Handling**: What happens if you provide invalid ZIP codes or parameters?

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC You have successfully built a LangChain agent that leverages Unity Catalog functions as tools for analyzing NYC taxi trip data. This approach demonstrates how to build production-ready AI agents that can reason about and act upon your organization's data assets while maintaining the governance, security, and lineage tracking provided by Unity Catalog.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>