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
# MAGIC # Lab - Building AI Agent Tools with Unity Catalog Functions
# MAGIC
# MAGIC ## Overview 
# MAGIC In this hands-on lab, you will build AI agent tools using Unity Catalog functions. You'll implement both Python and SQL functions, learn to identify and fix inadequate function descriptions, and test your tools using AI Playground.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC _By the end of this lab, you will be able to:_
# MAGIC - Create and register a SQL function using SQL syntax with proper documentation
# MAGIC - Build and register a Python function in Unity Catalog using `DatabricksFunctionClient()`
# MAGIC - Identify and fix inadequate function descriptions for AI agent use cases
# MAGIC - Test both functions independently using multiple methods
# MAGIC - Validate both functions as agent tools using AI Playground
# MAGIC
# MAGIC ### Business Context
# MAGIC You work for a transportation analytics company that wants to provide AI-powered insights about NYC taxi trips. Your team needs to build reliable, governed tools that agents can use to perform trip analysis and fare calculations. These tools must be accurate, well-documented, and accessible through Unity Catalog for governance and security.

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
# MAGIC As part of the workspace setup, several Python libraries have been installed. To see the list of notebook-scoped libraries, please read [this documentation](https://docs.databricks.com/aws/en/compute/serverless/dependencies#configure-environment-for-job-tasks). In particular, we installed:
# MAGIC
# MAGIC 1. `unitycatalog-ai[databricks]`: This package provides infrastructure and tooling for creating and managing UC functions (both SQL and Python UDFs) that can be used as tools by agents.
# MAGIC
# MAGIC This demonstration uses AI Playground to test our functions, which provides a no-code interface for prototyping tool-calling agents. See the [Unity Catalog Tool Integration documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/unity-catalog-tool-integration) for more details for advanced framework integration.

# COMMAND ----------

!pip install unitycatalog-ai[databricks]==0.3.2 reportlab
%restart_python

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-1.3

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
# MAGIC ### A4. Initialize the Databricks Function Client
# MAGIC
# MAGIC **TODO:** Initialize the DatabricksFunctionClient which provides a programmatic interface for creating, managing, and executing Unity Catalog functions.

# COMMAND ----------

## Import and initialize the DatabricksFunctionClient for serverless compute
from unitycatalog.ai.core.databricks import DatabricksFunctionClient

client = DatabricksFunctionClient(execution_mode="serverless")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task A4: Initialize the Databricks Function Client ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC from unitycatalog.ai.core.databricks import DatabricksFunctionClient
# MAGIC
# MAGIC client = DatabricksFunctionClient(execution_mode="serverless")
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Build a SQL Function for Average Trip Distance
# MAGIC
# MAGIC First, let's drop any existing functions with the same name as what will be created below.

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP FUNCTION IF EXISTS avg_fare_by_zip;
# MAGIC DROP FUNCTION IF EXISTS est_taxi_fare;

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Create the SQL Function
# MAGIC
# MAGIC **TODO:** Create a SQL function that calculates the average trip distance for trips originating from a specific pickup zip code using the `samples.nyctaxi.trips` table.
# MAGIC
# MAGIC **Requirements:**
# MAGIC - Function name: `avg_fare_by_zip`
# MAGIC - Parameter: `pickup_zip_code` (INT)
# MAGIC - Return type: DOUBLE
# MAGIC - Include proper COMMENT clauses for both the function and parameter
# MAGIC - Mark as DETERMINISTIC
# MAGIC - Handle NULL values appropriately
# MAGIC - Query the `samples.nyctaxi.trips` table

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO
# MAGIC -- -- Create the SQL function using CREATE OR REPLACE FUNCTION
# MAGIC CREATE OR REPLACE FUNCTION avg_fare_by_zip(
# MAGIC   pickup_zip_code INT COMMENT "The pickup zip code to filter trips by (e.g., 10001 for Midtown Manhattan)"
# MAGIC )
# MAGIC RETURNS DOUBLE
# MAGIC LANGUAGE SQL
# MAGIC DETERMINISTIC
# MAGIC COMMENT 'Calculates the average trip distance in miles for all NYC taxi trips originating from a specific pickup zip code. Returns the average distance as a numeric value.'
# MAGIC RETURN 
# MAGIC   SELECT AVG(trip_distance)
# MAGIC   FROM samples.nyctaxi.trips
# MAGIC   WHERE pickup_zip = pickup_zip_code
# MAGIC     AND trip_distance IS NOT NULL

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B1: Create the SQL Function ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC CREATE OR REPLACE FUNCTION avg_fare_by_zip(
# MAGIC   pickup_zip_code INT COMMENT "The pickup zip code to filter trips by (e.g., 10001 for Midtown Manhattan)"
# MAGIC )
# MAGIC RETURNS DOUBLE
# MAGIC LANGUAGE SQL
# MAGIC DETERMINISTIC
# MAGIC COMMENT 'Calculates the average trip distance in miles for all NYC taxi trips originating from a specific pickup zip code. Returns the average distance as a numeric value.'
# MAGIC RETURN 
# MAGIC   SELECT AVG(trip_distance)
# MAGIC   FROM samples.nyctaxi.trips
# MAGIC   WHERE pickup_zip = pickup_zip_code
# MAGIC     AND trip_distance IS NOT NULL
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Test the SQL Function
# MAGIC
# MAGIC **TODO:** Test your SQL function using direct SQL queries to verify it works correctly. Test with zip code 10001 (Midtown Manhattan).

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO
# MAGIC -- -- Test the function with zip code 10001
# MAGIC SELECT avg_fare_by_zip(10001) AS avg_distance

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task B2: Test the SQL Function ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC SELECT avg_fare_by_zip(10001) AS avg_distance
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Build a Python Function for Fare Estimation

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. A Bad Python Example
# MAGIC
# MAGIC **TODO:** Test the following Python function in AI Playground. The original intention of this function is to estimate the total fare for a taxi trip based on distance and time. Run the next cell to bypass best practices and immediately push the code as a UC tool and open the AI Playground for testing.
# MAGIC
# MAGIC As you can see from the function's definition, the fare calculation formula is:
# MAGIC - Base fare: $3.00
# MAGIC - Per mile: $2.50
# MAGIC - Per minute: $0.50
# MAGIC - Total = base_fare + (distance * per_mile_rate) + (time_minutes * per_minute_rate)

# COMMAND ----------

def est_taxi_fare(
    my_param: float, 
    param2: float
) -> float:
    """
    This is my calculation function.
    
    Args:
        my_param: parameter_1
        param2: my second parameter for my function
    
    Returns:
        the answer
    """
    base_fare = 3.00
    per_mile_rate = 2.50
    per_minute_rate = 0.50
    
    total_fare = base_fare + (my_param * per_mile_rate) + (param2 * per_minute_rate)
    return total_fare

function_info = client.create_python_function(
    func=est_taxi_fare,
    catalog=catalog_name,
    schema=schema_name,
    replace=True
)

print("Python function registered successfully!")
print(f"Function name: {function_info.full_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Test the Function
# MAGIC Navigate to **AI Playground** and attach the tool `est_taxi_fare()`:
# MAGIC
# MAGIC To test your Python functions as agent tools in AI Playground:
# MAGIC
# MAGIC 1. Navigate to **Playground** from your Databricks workspace
# MAGIC 1. Select a model with the **Tools enabled** label (e.g., `GPT OSS 120B` or another tool-capable model) from the model selection dropdown menu at the top of the Playground
# MAGIC 1. Click **Use endpoint** to begin your session
# MAGIC 1. Click **Tools > + Add tool**
# MAGIC 1. Under **UC Function**, select **Hosted Function** as the tool type
# MAGIC 1. Select the function you created: `est_taxi_fare`
# MAGIC 1. Click **Save** at the bottom right
# MAGIC 1. Validate that the tool is equipped. You should see **Tools (1)** in the **Tools** dropdown menu
# MAGIC 1. Enter the following question and observe that the model will _not_ use the tool as intended. Instead, you will see the model attempt to reason its way to the answer _without_ the tool call.
# MAGIC
# MAGIC > I'm traveling next week and I think it's about 20 minutes and 7 miles. How much will it cost me?
# MAGIC
# MAGIC Note that the answer should be calculated as
# MAGIC - Base fare: $3.00
# MAGIC - Per mile: $2.50
# MAGIC - Per minute: $0.50
# MAGIC Total = 3 + (7 * 2.5) + (20 * 0.5) = **30.5 dollars**
# MAGIC However, the LLM will confuse the first input with the second input (because of the incomplete lack of context brought on by the docstring) and return a value of **56.50 dollars**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Identify and Fix the Inadequate Function Description

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Understanding the Problem
# MAGIC
# MAGIC The Python function you created has an inadequate description. For example, the agent won't be able to determine what the function actually does, what the parameters represent, or what the return value means based on the current docstring. Let's fix that.
# MAGIC
# MAGIC **TODO:** Review your function's docstring above. Identify what's missing or unclear.

# COMMAND ----------

# MAGIC %md
# MAGIC ### D2. Fix the Python Function Description
# MAGIC
# MAGIC **TODO:** Redefine the Python function with a comprehensive, detailed docstring that follows best practices for AI agent tools.
# MAGIC
# MAGIC **Best practices for function descriptions:**
# MAGIC 1. Clear, concise summary of what the function does
# MAGIC 2. Detailed parameter descriptions including units and examples
# MAGIC 3. Explanation of the return value
# MAGIC 4. Context about when to use this function
# MAGIC 5. Any important notes or limitations

# COMMAND ----------

## Redefine the function with an improved docstring
def est_taxi_fare(
    distance_miles: float, 
    time_minutes: float
) -> float:
    """
    Estimates the total fare for a NYC taxi trip based on distance and duration.
    
    This function calculates the estimated fare using NYC taxi rate structure:
    - Base fare: $3.00
    - Distance rate: $2.50 per mile
    - Time rate: $0.50 per minute
    
    Use this function to provide fare estimates before a trip or to validate fare calculations.
    
    Args:
        distance_miles (float): The trip distance in miles (e.g., 5.5 for a 5.5-mile trip). Must be non-negative.
        time_minutes (float): The trip duration in minutes (e.g., 15.0 for a 15-minute trip). Must be non-negative.
    
    Returns:
        float: The estimated total fare in US dollars. For example, a 5-mile trip taking 15 minutes 
               would return 18.50 (3.00 + 12.50 + 7.50).
    """
    base_fare = 3.00
    per_mile_rate = 2.50
    per_minute_rate = 0.50
    
    total_fare = base_fare + (distance_miles * per_mile_rate) + (time_minutes * per_minute_rate)
    return total_fare

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D2: Fix the Python Function Description ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC def est_taxi_fare(
# MAGIC     distance_miles: float, 
# MAGIC     time_minutes: float
# MAGIC ) -> float:
# MAGIC     """
# MAGIC     Estimates the total fare for a NYC taxi trip based on distance and duration.
# MAGIC     
# MAGIC     This function calculates the estimated fare using NYC taxi rate structure:
# MAGIC     - Base fare: $3.00
# MAGIC     - Distance rate: $2.50 per mile
# MAGIC     - Time rate: $0.50 per minute
# MAGIC     
# MAGIC     Use this function to provide fare estimates before a trip or to validate fare calculations.
# MAGIC     
# MAGIC     Args:
# MAGIC         distance_miles (float): The trip distance in miles (e.g., 5.5 for a 5.5-mile trip). Must be non-negative.
# MAGIC         time_minutes (float): The trip duration in minutes (e.g., 15.0 for a 15-minute trip). Must be non-negative.
# MAGIC     
# MAGIC     Returns:
# MAGIC         float: The estimated total fare in US dollars. For example, a 5-mile trip taking 15 minutes 
# MAGIC                would return 18.50 (3.00 + 12.50 + 7.50).
# MAGIC     """
# MAGIC     base_fare = 3.00
# MAGIC     per_mile_rate = 2.50
# MAGIC     per_minute_rate = 0.50
# MAGIC     
# MAGIC     total_fare = base_fare + (distance_miles * per_mile_rate) + (time_minutes * per_minute_rate)
# MAGIC     return total_fare
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D3. Test the Function
# MAGIC Following best practices, let's test the new function here in the notebook before registering with Unity Catalog.
# MAGIC **TODO**: Run the next cell to test a distance of **7 miles** and a time of **20 minutes**, giving a total of **30.5** that we calculated earlier.

# COMMAND ----------

est_taxi_fare(
        distance_miles= 7.0,
        time_minutes= 20.0
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ### D4. Re-register the Python Function with Improved Description
# MAGIC Now we need to re-register our bad Python example. This can be accomplished with the `create_python_function()` API.
# MAGIC > We can wrap the Python function in SQL code and use `CREATE OR REPLACE FUNCTION`.
# MAGIC
# MAGIC **TODO:** Re-register the Python function with the improved description. Be sure to set `replace=True` to overwrite the original version of the function.

# COMMAND ----------

## Re-register the function with the improved docstring
function_info_improved = client.create_python_function(
    func=est_taxi_fare,
    catalog=catalog_name,
    schema=schema_name,
    replace=True
)

print("Python function re-registered with improved description!")
print(f"Function name: {function_info_improved.full_name}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D4: Re-register the Python Function with Improved Description ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC function_info_improved = client.create_python_function(
# MAGIC     func=est_taxi_fare,
# MAGIC     catalog=catalog_name,
# MAGIC     schema=schema_name,
# MAGIC     replace=True
# MAGIC )
# MAGIC
# MAGIC print("Python function re-registered with improved description!")
# MAGIC print(f"Function name: {function_info_improved.full_name}")
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D5. Verify the Improved Function Still Works
# MAGIC Next, let's test our new version of the function.
# MAGIC
# MAGIC **TODO:** Test the re-registered function to ensure it still works correctly. Note, you should get the same result as testing the function directly from the function definition above.

# COMMAND ----------

## Test the improved function
result_improved = client.execute_function(
    function_name=f"{catalog_name}.{schema_name}.est_taxi_fare",
    parameters={
        "distance_miles": 7.0,
        "time_minutes": 20.0
    }
)

print(f"Estimated Fare (Improved Function): ${result_improved.value}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ##### Task D5: Verify the Improved Function Still Works ANSWER
# MAGIC <details>
# MAGIC   <summary>EXPAND FOR SOLUTION CODE</summary>
# MAGIC <button onclick="copyBlock()">Copy to clipboard</button>
# MAGIC
# MAGIC <pre id="copy-block" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; border:1px solid #e5e7eb; border-radius:10px; background:#f8fafc; padding:14px 16px; font-size:0.85rem; line-height:1.35; white-space:pre;">
# MAGIC <code>
# MAGIC <!-------------------ADD SOLUTION CODE BELOW------------------->
# MAGIC result_improved = client.execute_function(
# MAGIC     function_name=f"{catalog_name}.{schema_name}.est_taxi_fare",
# MAGIC     parameters={
# MAGIC         "distance_miles": 7.0,
# MAGIC         "time_minutes": 20.0
# MAGIC     }
# MAGIC )
# MAGIC
# MAGIC print(f"Estimated Fare (Improved Function): ${result_improved.value}")
# MAGIC <!-------------------END SOLUTION CODE------------------->
# MAGIC </code></pre>
# MAGIC
# MAGIC <script>
# MAGIC function copyBlock() {
# MAGIC   const el = document.getElementById("copy-block");
# MAGIC   if (!el) return;
# MAGIC
# MAGIC   const text = el.innerText;
# MAGIC
# MAGIC   // Preferred modern API
# MAGIC   if (navigator.clipboard && navigator.clipboard.writeText) {
# MAGIC     navigator.clipboard.writeText(text)
# MAGIC       .then(() => alert("Copied to clipboard"))
# MAGIC       .catch(err => {
# MAGIC         console.error("Clipboard write failed:", err);
# MAGIC         fallbackCopy(text);
# MAGIC       });
# MAGIC   } else {
# MAGIC     fallbackCopy(text);
# MAGIC   }
# MAGIC }
# MAGIC
# MAGIC function fallbackCopy(text) {
# MAGIC   const textarea = document.createElement("textarea");
# MAGIC   textarea.value = text;
# MAGIC   textarea.style.position = "fixed";
# MAGIC   textarea.style.left = "-9999px";
# MAGIC   document.body.appendChild(textarea);
# MAGIC   textarea.select();
# MAGIC   try {
# MAGIC     document.execCommand("copy");
# MAGIC     alert("Copied to clipboard");
# MAGIC   } catch (err) {
# MAGIC     console.error("Fallback copy failed:", err);
# MAGIC     alert("Could not copy to clipboard. Please copy manually.");
# MAGIC   } finally {
# MAGIC     document.body.removeChild(textarea);
# MAGIC   }
# MAGIC }
# MAGIC </script>
# MAGIC </details>

# COMMAND ----------



result_improved = client.execute_function(
    function_name=f"{catalog_name}.{schema_name}.est_taxi_fare",
    parameters={
        "distance_miles": 7.0,
        "time_minutes": 20.0
    }
)

print(f"Estimated Fare (Improved Function): ${result_improved.value}")



# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Testing Tools with AI Playground

# COMMAND ----------

# MAGIC %md
# MAGIC ### E1. Attach your Tools
# MAGIC
# MAGIC To test your functions as agent tools in AI Playground:
# MAGIC
# MAGIC 1. Navigate to **Playground** from your Databricks workspace
# MAGIC 1. Select a model with the **Tools enabled** label (e.g., `GPT OSS 120B`) from the model selection dropdown menu at the top of the **Playground**
# MAGIC 1. Click **Use endpoint**
# MAGIC
# MAGIC
# MAGIC Now let's attach both functions you created as tools for the AI agent:
# MAGIC
# MAGIC 1. Click **Tools > + Add tool**
# MAGIC 2. Under **UC Function**, click on **Hosted Function** as the tool type
# MAGIC 3. Select `avg_fare_by_zip` from your catalog and schema
# MAGIC 4. Click **Save** at the bottom right
# MAGIC 5. Repeat steps 1-4 to add the `est_taxi_fare` function
# MAGIC 6. Validate that both tools are equipped; you should see **Tools (2)** in the **Tools** dropdown menu

# COMMAND ----------

# MAGIC %md
# MAGIC ### E2. Test your Tools
# MAGIC
# MAGIC #### Checking what the agent has access to
# MAGIC Before sending actual queries for the use case, you can check to see what your agent has access to with something like 
# MAGIC > What tools can you use?
# MAGIC or 
# MAGIC > What tools do you have access to?
# MAGIC
# MAGIC You will see a response that lists all the tools available (it should list the two we attached).
# MAGIC
# MAGIC #### Begin sending questions
# MAGIC
# MAGIC Now you're ready to send some sample questions and begin testing your functions. Here are some sample questions to help you get started:
# MAGIC
# MAGIC > Sample Question 1: I'm traveling next week and I think it's about 20 minutes and 7 miles. How much will it cost me?
# MAGIC - Note this is the same question we used in section **C2**.
# MAGIC
# MAGIC > Sample Question 2: What is the average trip distance for pickups from zip code 10001?
# MAGIC - This will test the SQL function
# MAGIC
# MAGIC > Can you get the average trip distance in miles for zip code 10001? I want to see how much it would take to travel for 20 mins for that zip code.
# MAGIC - This will (hopefully) call both functions. Keep in mind that outputs vary depending on the type of LLM being leveraged. Below is a screenshot of an example output using **GPT OSS 20B**. If one (or both) functions are not called, you can add a system prompt explicitly telling the LLM to call available functions by clicking on **Add system prompt** in the Playground and sending a message like _"Exhaust all tool options before deriving your answer"_.
# MAGIC
# MAGIC <!-- Output image -->
# MAGIC
# MAGIC ![optional alt text](../Includes/images/llm_output.png)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC The skills you've developed enable you to create production-ready agent tools that combine Unity Catalog's governance framework with the power of both SQL and Python. By following best practices for function descriptions, you ensure that AI agents can effectively understand and utilize your tools to provide accurate, reliable insights. 

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>