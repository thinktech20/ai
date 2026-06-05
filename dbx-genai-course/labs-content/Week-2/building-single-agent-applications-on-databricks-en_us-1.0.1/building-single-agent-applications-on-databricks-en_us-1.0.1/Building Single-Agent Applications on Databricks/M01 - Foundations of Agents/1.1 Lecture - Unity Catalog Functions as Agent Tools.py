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
# MAGIC # Lecture - Unity Catalog Functions as Agent Tools on Databricks
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC Imagine an AI agent that can instantly answer questions like "What's the average home price in the Mission district?" or "Calculate the customer lifetime value for our top clients" by automatically discovering and executing the right data operations and business logic. This is the power of Unity Catalog Functions as Agent Tools.
# MAGIC
# MAGIC Building on the foundational concepts of AI agents and tools, this session focuses on one of the most practical implementations: using both Unity Catalog SQL and Python Functions as intelligent, discoverable tools that AI agents can automatically select and execute based on natural language queries.
# MAGIC
# MAGIC This lecture establishes the technical foundation and best practices needed for the hands-on demonstrations that follow, where you'll build and test both SQL and Python Unity Catalog Functions as Agent Tools using [AI Playground](https://docs.databricks.com/aws/en/generative-ai/agent-framework/ai-playground-agent).
# MAGIC
# MAGIC ### Learning Objectives
# MAGIC
# MAGIC _By the end of this lecture, you will be able to:_
# MAGIC
# MAGIC - Understand fundamental differences between UC functions and Agent Tools
# MAGIC - Explain the differences between SQL and Python agent tools
# MAGIC - Explain how to register SQL functions
# MAGIC - Explain different ways to register Python functions
# MAGIC - Understand how to explore registered functions using the Databricks UI
# MAGIC - Understand how AI Playground integrates with UC Tools

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Understanding Unity Catalog Functions as Agent Tools

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. What Are Unity Catalog Functions as Agent Tools?
# MAGIC
# MAGIC Before getting started, it's important to keep in mind what UC functions are. Unity Catalog tools are really just Unity Catalog user-defined functions (UDFs) under the hood. When you define a Unity Catalog tool, you're registering a function in Unity Catalog. To learn more about Unity Catalog UDFs, see [this documentation](https://docs.databricks.com/aws/en/udf/unity-catalog).
# MAGIC
# MAGIC > **What's a UDF?** 
# MAGIC > User-defined functions (UDFs) in Unity Catalog extend SQL and Python capabilities within Databricks. They allow custom functions to be defined, used, and securely shared and governed across computing environments.
# MAGIC
# MAGIC **Unity Catalog Functions as Agent Tools** are Unity Catalog functions written in either SQL or Python that can be dynamically discovered, selected, and executed by AI agents to perform data operations and business logic. Unlike traditional functions that require manual programming to call, Unity Catalog Functions as Agent Tools are designed to be:
# MAGIC
# MAGIC - **Self-describing** through comprehensive metadata and documentation
# MAGIC - **Contextually appropriate** for specific business or analytical tasks
# MAGIC - **Governable** through Unity Catalog's security and access control mechanisms

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. SQL vs Python Agent Tools: Key Differences and Use Cases
# MAGIC
# MAGIC
# MAGIC
# MAGIC ![sql-fun-vs-agent-tool.png](../Includes/images/sql-fun-vs-agent-tool.png "sql-fun-vs-agent-tool.png")
# MAGIC
# MAGIC <p>
# MAGIC <em>
# MAGIC Example of how UC SQL functions should be structured for use as agent tools. 
# MAGIC </em>
# MAGIC </p>
# MAGIC
# MAGIC Understanding when to use SQL versus Python functions is crucial for effective agent tool implementation:
# MAGIC
# MAGIC **SQL Agent Tools**
# MAGIC - Optimized for data querying and analytical operations
# MAGIC - Execute using `CREATE OR REPLACE FUNCTION` statements
# MAGIC - Limited to SQL syntax and built-in functions
# MAGIC - Execute only in serverless mode
# MAGIC - Automatic query optimization and caching
# MAGIC - Ideal for: Data retrieval, aggregations, filtering, analytical calculations
# MAGIC
# MAGIC **Python Agent Tools**
# MAGIC - Execute custom Python logic and complex computations
# MAGIC - Support integration with external APIs and libraries
# MAGIC - Offer flexible execution modes (serverless and local)
# MAGIC - Require explicit type hints and Google-style docstrings
# MAGIC - Support advanced error handling and debugging capabilities
# MAGIC - Ideal for: Business logic, external integrations, complex algorithms, data transformations
# MAGIC
# MAGIC **Combining Tools**: The most powerful agent architectures use both SQL and Python tools together, where SQL handles data access and analysis while Python functions manage business logic and external integrations.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Agent Tools vs Traditional Functions
# MAGIC
# MAGIC Understanding the distinction between agent tools and traditional functions is crucial for effective implementation:
# MAGIC
# MAGIC - **Traditional Functions**
# MAGIC     - Designed for direct programmatic use by developers
# MAGIC     - Limited or minimal documentation requirements
# MAGIC     - Called explicitly with known parameters
# MAGIC     - Focus on computational efficiency and performance
# MAGIC
# MAGIC - **Unity Catalog Functions as Agent Tools**
# MAGIC     - Designed for dynamic discovery and use by AI agents
# MAGIC     - Rich metadata and comprehensive documentation required
# MAGIC     - Parameters and usage inferred from natural language queries
# MAGIC     - Focus on clarity, interpretability, and agent usability
# MAGIC     - Include business context and usage examples
# MAGIC
# MAGIC ![python-function-diagram.png](../Includes/images/python-function-diagram.png "python-function-diagram.png")
# MAGIC
# MAGIC <p align="center"><em>Similar to how SQL tools are used, the agent uses its brain to help reason and plan execution of UC Python tools.</em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Registration Methods

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Function Registration Methods
# MAGIC
# MAGIC Unity Catalog provides different approaches for registering SQL and Python functions as agent tools. Since UC-registered functions are governed by UC permissions, this differentiates registration when compared to session-scoped/notebook UDFs.
# MAGIC
# MAGIC
# MAGIC ![sql-registration-diagram](../Includes/images/sql-registration-diagram.png "sql-registration-diagram")
# MAGIC
# MAGIC
# MAGIC #### SQL Function Registration
# MAGIC - Using [`CREATE OR REPLACE FUNCTION` statements](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function):
# MAGIC   - Immediate registration and availability
# MAGIC   - Full control over function definition and metadata
# MAGIC   - Integration with existing SQL development workflows
# MAGIC   - Support for complex SQL logic and business rules
# MAGIC   - No support for custom environment or dependencies 
# MAGIC
# MAGIC ![python-registration-diagram](../Includes/images/python-registration-diagram.png "python-registration-diagram")
# MAGIC
# MAGIC #### Python Function Registration
# MAGIC - Using the [`DatabricksFunctionClient()`](https://docs.unitycatalog.io/ai/client/#databricks-function-client):
# MAGIC   - `create_python_function()` API accepts Python callables directly
# MAGIC   - Automatic extraction of type hints and docstring metadata
# MAGIC   - Integration with Unity Catalog's three-level namespace
# MAGIC   - Support for function versioning and replacement
# MAGIC   - Supports serverless (production) and local (dev) modes, though local mode does [not support SQL-based functions](https://docs.databricks.com/aws/en/generative-ai/agent-framework/create-custom-tool)
# MAGIC - Using [`CREATE OR REPLACE FUNCTION` statements](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function): 
# MAGIC   - Similar to SQL tool creation, you can also create a Python function using python logic but SQL syntax for registration (see an example [here](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function#create-python-functions)).
# MAGIC   - Can define custom dependencies using the `ENVIRONMENT` clause (read more [here](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function#define-custom-dependencies-in-python-functions)).

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. (Optional) Execution Environment Considerations
# MAGIC
# MAGIC To read more about technical considerations (serverless vs local mode) for UC Python functions, please see [this documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/create-custom-tool#running-functions-using-serverless-or-local-mode).

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Tool Registration Validation with UI 
# MAGIC
# MAGIC Once your functions have been registered to Unity Catalog, you can validate the metadata information the LLM will consume for context and query filtering. Below are two examples of what to expect when navigating the tool locations within UC.
# MAGIC
# MAGIC ![sql-func-validation.png](../Includes/images/sql-func-validation.png "sql-func-validation.png")
# MAGIC
# MAGIC <p align="center"><em>An example of a SQL UC function that has been registered with LLM-friendly notes for context and usage.</em></p>
# MAGIC
# MAGIC ![python-tool-ui.png](../Includes/images/python-tool-ui.png "python-tool-ui.png")
# MAGIC
# MAGIC <p align="center"><em> Similar to SQL functions, with registered Python functions, you can see the description, definition, and other metadata. </em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Integration with AI Playground for Prototyping

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. AI Playground Integration
# MAGIC
# MAGIC AI Playground provides a no-code interface for testing and prototyping both SQL and Python Unity Catalog Functions as Agent Tools. In the AI Playground, you have automatic UC-permission-level access to tools as well as state-of-the-art LLM like Claude and GPT models. The AI Playground should be used for prototyping queries, LLMs, and tool usage before building agent code. Below is an example of how the AI Playground looks when sending a prompt that invokes tool usage from the LLM.
# MAGIC
# MAGIC ![ai-playground-tools.png](../Includes/images/ai-playground-tools.png "ai-playground-tools.png")
# MAGIC
# MAGIC <p align="center"><em>In the AI Playground, some models have the ability to add tools, like GPT-5.1 for example.</em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC Now that you understand how UC Tools can be built, registered, visually inspected, and tested on Databricks, you are ready for the follow-along demonstration that will cover these concepts in practice.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>