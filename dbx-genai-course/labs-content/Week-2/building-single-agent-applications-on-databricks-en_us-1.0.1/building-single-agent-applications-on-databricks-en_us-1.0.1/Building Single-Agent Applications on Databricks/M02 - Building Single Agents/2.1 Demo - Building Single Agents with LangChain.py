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
# MAGIC # Demo - Building Single Agents with LangChain
# MAGIC
# MAGIC This demonstration explores how to create AI agents that leverage Unity Catalog (UC) functions as tools within the LangChain framework. You will integrate UC tools with LangChain toolkits and build an agent capable of reasoning and taking action using foundation models hosted in Mosaic AI Model Serving.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC By the end of this lesson, you will be able to:
# MAGIC - Understand the separation of tasks between tools, models, and agentic frameworks
# MAGIC - Know the process of registering, testing, and integrating Unity Catalog functions with LangChain using the `UCFunctionToolkit`
# MAGIC - Configure and execute a LangChain agent with tool-calling capabilities
# MAGIC - Know how to view and interpret the trace summary of agent execution and analyze decision-making using MLflow

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
# MAGIC **NOTE:** If you are familiar with `langchain-databricks`, note that `databricks-langchain` replaces it. This demonstration uses LangChain, but a similar approach can be applied to other libraries.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-2.1

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Inspect the Airbnb Dataset 
# MAGIC As a part of the classroom setup, the Airbnb dataset has been processed and stored as a Delta table within Unity Catalog. Run the next cell to query the first few rows of the dataset.

# COMMAND ----------

df = spark.read.table('sf_airbnb_listings')
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Initialize the Databricks Function Client
# MAGIC
# MAGIC The `DatabricksFunctionClient` provides a programmatic interface for executing Unity Catalog functions. We configure it for serverless execution mode to align with our compute requirements. This will be used to test our registered UC functions.

# COMMAND ----------

from unitycatalog.ai.core.databricks import DatabricksFunctionClient

# client = DatabricksFunctionClient()  # For classic compute
client = DatabricksFunctionClient(execution_mode="serverless")  # For serverless compute

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Understanding Agent Concepts
# MAGIC
# MAGIC It's important to understand that when using an agentic framework, we should independently test three core components of modern agents:
# MAGIC
# MAGIC 1. Tool building
# MAGIC 2. Choice of large language model (LLM)/small language model (SLM)
# MAGIC 3. Choice of agentic framework
# MAGIC
# MAGIC ### C1. Quick Review of Agent Concepts
# MAGIC
# MAGIC When building a single agent, it's important to understand how these components make up an agent. In short, _an AI agent has the ability to view and analyze its environment (plan) and take action (use tools) to achieve a specific goal_. Let's break this down a little more:
# MAGIC
# MAGIC 1. **Tool building**: This is agnostic of the underlying LLM/SLM (as long as it is capable of tool calling) and _any_ agentic framework. Building executable tools must be thoroughly tested prior to equipping an LLM/SLM to ensure reliability and consistency.
# MAGIC 2. **LLM/SLM**: You must have a language model that has the essential agentic capability of _deciding_ whether to call a tool or not based on its perceived plan, which is guided by prompts and system policies. Therefore, it is important to keep in mind that an LLM/SLM alone _may be_ considered an agent, even though its reasoning loop may be quite shallow, if it is able to act in its environment based on the outcome of its reasoning loop.
# MAGIC 3. **Agentic Framework**: The underlying framework should be pluggable across common LLMs and exists to orchestrate the _behavior_ of the model via framework-specific policies (e.g., state/memory management and tracing).
# MAGIC
# MAGIC ### C2. Focus Areas for This Demonstration
# MAGIC
# MAGIC With this in mind, please note that this demonstration _will not_ be concerned with building tools or what to consider when selecting an LLM/SLM. Instead, we will focus on:
# MAGIC
# MAGIC 1. How to configure and equip a LangChain agent (tool-calling LLM + LangChain framework) with Unity Catalog tools
# MAGIC 2. How to execute a LangChain agent
# MAGIC 3. Performing basic tracing with MLflow

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Integrate Unity Catalog Functions with LangChain
# MAGIC
# MAGIC We can leverage `databricks_langchain` to wrap UC functions as tools that can be directly integrated into LangChain.
# MAGIC
# MAGIC **`UCFunctionToolkit`** is a component of the Databricks-LangChain integration. It acts as a bridge between Unity Catalog user-defined functions (UDFs) and agent frameworks (like LangChain). When you wrap a Unity Catalog function with `UCFunctionToolkit`, it makes that function accessible as a "tool" that an LLM agent can call programmatically.

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Define the Tool List
# MAGIC
# MAGIC First, let's make a list of the functions we want to use called `function_names`. When using `UCFunctionToolkit`, you must include the catalog and schema.

# COMMAND ----------

tool_list_raw = [
    'avg_neigh_price',
    'cnt_by_room_type'
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
# MAGIC The toolkit wraps our Unity Catalog functions and makes them available as LangChain tools.

# COMMAND ----------

from databricks_langchain import UCFunctionToolkit

# Create a toolkit with the Unity Catalog functions
toolkit = UCFunctionToolkit(function_names=function_names)
tools = toolkit.tools

# COMMAND ----------

# MAGIC %md
# MAGIC ### D3. Test the Toolkit
# MAGIC
# MAGIC Now that our toolkit has been created, let's perform a quick check to make sure we can execute the tools using it. Here we execute example payloads using the toolkit defined by `tools` previously and the `DatabricksFunctionClient` by sending test payloads using the `execute_function` API. Note the output from the next two cells will be the same as testing with SQL queries like we did above.

# COMMAND ----------

payload1 = {'neighborhood_name': 'Mission'}
payload1_test_result = client.execute_function(
    function_name=tools[0].uc_function_name,
    parameters=payload1
)
print(payload1_test_result.value)

# COMMAND ----------

payload2 = {
    'neighborhood_name': 'Mission',
    'room_type_filter': 'Private room'
}
payload2_test_result = client.execute_function(
    function_name=tools[1].uc_function_name,
    parameters=payload2
)
print(payload2_test_result.value)

# COMMAND ----------

# MAGIC %md
# MAGIC ### D4. Progress Checkpoint
# MAGIC
# MAGIC To recap, so far we have:
# MAGIC
# MAGIC 1. Built UC functions and registered those functions to UC via SQL queries.
# MAGIC 2. Tested our UC functions locally in this notebook using SQL queries.
# MAGIC 3. Created a **LangChain** toolkit called `tools` and tested this toolkit using the same sample payloads as in the previous step.
# MAGIC
# MAGIC Next, we will configure and execute the agent.

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Configure and Execute the Agent
# MAGIC
# MAGIC The `AgentExecutor` method from `langchain.agents` acts as the orchestrator for the LLM to repeatedly invoke the agent's decision function, handle tool execution, and manage the flow of information between the reasoning, action, and observation steps.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E1. Load Agent Configuration
# MAGIC
# MAGIC For clarity, we have stored the endpoint we wish to query, the LLM's temperature value, and the system prompt in another file called `demo_agent.json`. Decoupling the agent's configuration from this main notebook helps with debugging and updates. Let's first read in this configuration using `json.load()`.

# COMMAND ----------

import json

# Load JSON file
with open("./demo_agent.json", "r") as f:
    config = json.load(f)

llm_endpoint = config['llm_endpoint']
llm_temperature = config['llm_temperature']
system_prompt = config["system_prompt"]

print("Endpoint:", llm_endpoint)
print("Temperature:", llm_temperature)
print("System Prompt:", system_prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC ### E2. Optional Exercise
# MAGIC
# MAGIC To demonstrate how the framework is independent of the LLM, try switching out the LLM endpoint name by navigating to **Serving** in the menu bar to the left.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E3. Import Required Libraries
# MAGIC
# MAGIC Import the necessary Python libraries for building and executing the agent.

# COMMAND ----------

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate

from databricks_langchain import ChatDatabricks

import mlflow

# COMMAND ----------

# MAGIC %md
# MAGIC ### E4. Initialize the Language Model
# MAGIC
# MAGIC Initialize the LLM stored as `llm_endpoint` with temperature `llm_temperature`. We do so using `ChatDatabricks`, which is a class provided by the `databricks-langchain` package that serves as a conversational LLM interface specifically designed for use within LangChain applications.

# COMMAND ----------

llm_config = ChatDatabricks(
    endpoint=llm_endpoint,
    temperature=llm_temperature
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### E5. Define the Prompt Template
# MAGIC
# MAGIC Here, we use the variable `system_prompt`, which was brought in from `demo_agent.json`. We also configure the chat history, input, and the agent scratchpad.
# MAGIC
# MAGIC `ChatPromptTemplate.from_messages()` constructs a reusable template for generating a list of all messages, each with its own role and content, that will be sent to a chat-focused LLM in _sequence_. That is, first a system prompt is used, then we inject the ongoing conversation, followed by the user input and the agent's stepwise reasoning for intermediate results.

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
# MAGIC ### E6. Enable MLflow Tracing
# MAGIC Enable automatic tracing with MLflow to capture agent execution details for debugging and analysis. Note that when using a serverless environment, you will need to enable autologging for the MLflow tracing UI to appear as a part of the agent's output. Because MLflow is [integrated with popular GenAI libraries](https://mlflow.org/docs/latest/genai/tracing/#one-line-auto-tracing-integrations), this is actually quite simple to initiate with `mlflow.<framework>.autolog()` as shown in the next cell. 

# COMMAND ----------

mlflow.langchain.autolog()

# COMMAND ----------

# MAGIC %md
# MAGIC ### E7. Create the Agent Configuration
# MAGIC
# MAGIC Define the agent, specifying the LLM's configuration (`llm_config`), tools from the toolkit we defined previously, along with the prompt payload that we defined above (`prompt_payload`).

# COMMAND ----------

agent_config = create_tool_calling_agent(
    llm_config,
    tools,
    prompt_payload
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### E8. Execute the Agent
# MAGIC
# MAGIC Now that we have our agent's configuration in place, we are ready to execute the agent with `AgentExecutor`. The `verbose=True` parameter enables detailed logging of the agent's reasoning and tool-calling process.

# COMMAND ----------

agent_executor = AgentExecutor(agent=agent_config, tools=tools, verbose=True)
response = agent_executor.invoke(
    {
        "input": "Get the average for Mission and tell me the number of properties there that have a shared room"
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## F. High-Level Analysis of the Agent Response and Tracing with MLflow
# MAGIC
# MAGIC The MLflow Trace UI is presented as part of the output when running the agent. Click on the **Summary** tab to see a high-level view of the agent's reasoning loop. This provides detailed visibility into the agent's decision-making process.
# MAGIC
# MAGIC ![optional alt text](../Includes/images/mlflow-tool-use-2.png)
# MAGIC
# MAGIC Your output should look similar to the above screenshot, which will include:
# MAGIC
# MAGIC - **Which tools were called**: The nature of the query above invokes both tools.
# MAGIC - **What parameters were passed to `ChatDatabricks` and UC tools**: For example, in the image below, we see that for the tool `avg_neigh_price`, the string `Mission` was an input and the output was `{"format": "SCALAR", "value": "229.7557803468208"}`.
# MAGIC
# MAGIC ![optional alt text](../Includes/images/mlflow-tool-use-1.png)
# MAGIC
# MAGIC - **The results returned from each tool**: For example, if you click on the `ChatDatabricks_2` dropdown arrow, you will see the tool's result fed to the LLM as an input and output as part of the reasoning chain.
# MAGIC - **The final response generated by the agent** with `ChatDatabricks_3`.
# MAGIC
# MAGIC The output from the previous cell shows that both of the tools that we created earlier were called.

# COMMAND ----------

# MAGIC %md
# MAGIC ### F1. Parse the Agent's Response
# MAGIC
# MAGIC Parse and display the agent's response in a readable format.

# COMMAND ----------

# Extract text segments from the response
output_segments = response['output']

for segment in output_segments:
    if isinstance(segment, dict) and segment.get('type') == 'text':
        print(segment['text'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC By running through this demonstration, you have successfully built a LangChain agent that is attached to your tools stored and governed by Unity Catalog. You learned how to:
# MAGIC
# MAGIC - Bridge Unity Catalog functions into LangChain using the `UCFunctionToolkit`
# MAGIC - Configure a foundation model with tool-calling capabilities
# MAGIC - Execute an AI agent that reasons about user queries and invokes appropriate tools
# MAGIC - Trace and analyze agent behavior using MLflow
# MAGIC
# MAGIC This approach enables you to build production-ready AI agents that leverage your organization's data assets stored in Unity Catalog while maintaining governance, security, and lineage tracking.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>