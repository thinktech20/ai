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
# MAGIC # Lecture - Foundations of AI Agents and Tools on Databricks
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This lecture introduces the fundamental concepts of AI agents and tools within the Databricks platform. Modern AI applications require agents that can interact with data, perform analytical tasks, and make informed decisions based on available information. By understanding these foundational concepts, you'll be prepared to build robust, scalable AI solutions that combine governance, security, and analytical power.
# MAGIC
# MAGIC AI agents represent a revolutionary shift from traditional AI systems that simply provide information based on user prompts. Instead, agents use available tools to help them make more accurate and informed decisions, acting autonomously within their environment to achieve user-defined goals.
# MAGIC
# MAGIC ### Learning Objectives
# MAGIC
# MAGIC _By the end of this lecture, you will be able to:_
# MAGIC
# MAGIC - Define what AI agents are and understand their core components and capabilities
# MAGIC - Explain the role of tools in AI agent architectures and how they extend agent functionality
# MAGIC - Identify the benefits of using Unity Catalog for agent tool governance and management

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Understanding AI Agents

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. What Are AI Agents?
# MAGIC
# MAGIC An **AI agent** is an intelligent software system that can perceive its environment, make decisions, and take actions to achieve specific goals. Unlike traditional AI systems that require continuous inputs from users, AI agents are autonomous systems that can:
# MAGIC
# MAGIC - **Reason** about complex problems and situations
# MAGIC - **Plan** sequences of actions to achieve objectives
# MAGIC - **Adapt** their behavior based on new information
# MAGIC - **Interact** with external systems and data sources
# MAGIC - **Learn** from experience to improve future performance
# MAGIC
# MAGIC What makes AI agents exciting is their **adaptability**. They use tools that dynamically pull up-to-date datasets to inform decisions and processes, making them ideal for complex and unpredictable tasks. While humans set the goals, AI agents determine the best way to achieve those goals.
# MAGIC
# MAGIC In the context of data analytics and business intelligence, AI agents serve as intelligent intermediaries between users and data systems, capable of understanding natural language queries and executing complex analytical tasks.
# MAGIC
# MAGIC ![agent-framework.png](../Includes/images/agent-framework.png "agent-framework.png")

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Evolution of AI Agents
# MAGIC
# MAGIC AI agents have evolved significantly since their inception:
# MAGIC
# MAGIC - **1960s - Rule-Based Systems**
# MAGIC     - Basic chatbots with predetermined logic trees
# MAGIC     - Rigid, rule-based programming
# MAGIC     - Limited to simple, scripted responses
# MAGIC
# MAGIC - **1990s - Statistical Learning**
# MAGIC     - More autonomous systems processing information
# MAGIC     - Simple decision-making capabilities
# MAGIC     - Foundation for consumer-grade AI devices
# MAGIC
# MAGIC - **2000s - Machine Learning Integration**
# MAGIC     - Consumer devices like robot vacuums and digital assistants (Siri, Alexa)
# MAGIC     - Statistical machine learning models and neural networks
# MAGIC     - Enhanced decision-making and analysis capabilities
# MAGIC
# MAGIC - **2020s - Large Language Models**
# MAGIC     - Breakthrough with deep reinforcement learning and transformer-based large language models (LLMs)
# MAGIC     - Multimodal interfaces and advanced reasoning
# MAGIC     - Dynamic interaction with complex environments
# MAGIC     - Tool-calling capabilities for enhanced functionality

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Key Principles of AI Agents
# MAGIC
# MAGIC AI agents operate on three fundamental principles that distinguish them from traditional software:
# MAGIC
# MAGIC #### **Perception**
# MAGIC The first step for agents to understand the context in which they're operating. For language models, this includes:
# MAGIC - User inputs and queries via text, photos, or audio
# MAGIC - Environmental data from sensors or APIs
# MAGIC - Historical context and conversation memory
# MAGIC
# MAGIC #### **Decision-Making**
# MAGIC The agent processes collected information through algorithms and determines proper actions according to user goals:
# MAGIC - Analyzing requirements and constraints
# MAGIC - Determining necessary steps and tool usage
# MAGIC - Planning optimal execution sequences
# MAGIC
# MAGIC #### **Action**
# MAGIC Finally, an agent takes concrete steps to achieve objectives:
# MAGIC - Executing database queries and API calls
# MAGIC - Processing and transforming data
# MAGIC - Generating reports and recommendations
# MAGIC - Making decisions that affect real-world outcomes

# COMMAND ----------

# MAGIC %md
# MAGIC ### A4. Core Components of AI Agents
# MAGIC Modern AI agents typically consist of several key components working together:
# MAGIC
# MAGIC 1. **Large Language Model (LLM) Brain**
# MAGIC The central reasoning engine that processes natural language, understands context, and makes decisions about what actions to take.
# MAGIC 2. **Memory System**
# MAGIC Stores conversation history, context, and learned information to maintain coherent interactions over time.
# MAGIC 3. **Planning Module**
# MAGIC Breaks down complex requests into smaller, manageable tasks and determines the optimal sequence of actions.
# MAGIC 4. **Tool Interface**
# MAGIC Connects the agent to external systems, databases, APIs, and functions that extend its capabilities beyond text generation.
# MAGIC 5. **Execution Engine**
# MAGIC Manages the actual execution of planned actions and handles responses from external tools and systems.
# MAGIC
# MAGIC <p align="center">
# MAGIC <img src="../Includes/images/example-agent-framework.png" alt="a4-core-components-of-ai-agents" width="50%">
# MAGIC </p>
# MAGIC <p align="center"><em>Example agent pattern: The LLM acts as the brain to plan and execute tasks within its environment based on the user's request. Tools can be stored securely within Unity Catalog while agent memory can be used with Delta Lake and Lakebase. </em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ### A5. Types of AI Agents by Complexity
# MAGIC
# MAGIC AI agents differ based on their complexity and application. Understanding these types helps in selecting the right approach for specific use cases:
# MAGIC 1. **Simple Reflex Agents**
# MAGIC     - Make decisions based on current conditions only
# MAGIC     - Example: Robot vacuum that cleans only when it senses dirt
# MAGIC     - No consideration of history or future implications
# MAGIC 2. **Model-Based Reflex Agents**
# MAGIC     - Account for current state and use world models to guide actions
# MAGIC     - Example: Smart thermostat adjusting based on time, weather, and preferences
# MAGIC     - More sophisticated than simple reflex agents
# MAGIC 3. **Goal-Based Agents**
# MAGIC     - Plan specific strategies to achieve desired goals
# MAGIC     - Develop action sequences and evaluate progress
# MAGIC     - Example: Navigation systems like Google Maps considering traffic and routes
# MAGIC 4. **Utility-Based Agents**
# MAGIC     - Evaluate multiple ways to achieve goals for optimal efficiency
# MAGIC     - Consider risk-reward models and optimization criteria
# MAGIC     - Example: AI trading bots adjusting investment strategies
# MAGIC 5. **Learning Agents**
# MAGIC     - Learn from past actions and adapt to future situations
# MAGIC     - Analyze performance and seek efficiency improvements
# MAGIC     - Example: Recommendation systems that improve based on user behavior

# COMMAND ----------

# MAGIC %md
# MAGIC ### A6. Can All LLMs Use Tools?
# MAGIC No, not all LLMs have the tool-calling capability. On Databricks, tool usage by LLMs is enabled through specific frameworks and integrations, such as Databricks Assistant or custom agent frameworks that allow LLMs to interact with external systems, databases, or APIs. This capability is not inherent to all LLMs; it requires additional engineering, orchestration, and security controls to ensure safe and effective tool usage. For example, Databricks Assistant is designed to use tools to answer questions and perform actions within the Databricks environment, but this is a feature of the platform, not a universal capability of all LLMs. 
# MAGIC
# MAGIC > For a complete list of Foundation Model APIs that can perform tool-calling, please read more [here](https://docs.databricks.com/aws/en/machine-learning/model-serving/function-calling#supported-models). 

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Understanding Agent Tools

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. What Are Agent Tools?
# MAGIC
# MAGIC **Agent tools** are specialized functions or capabilities that extend an AI agent's ability to interact with external systems and perform specific tasks. Think of tools as the "hands" of an AI agent, while the LLM provides the "brain" for reasoning and decision-making, tools enable the agent to actually manipulate data, call APIs, perform calculations, and interact with the real world.
# MAGIC
# MAGIC Tools transform agents from purely conversational systems into actionable, productive assistants. Some examples include:
# MAGIC
# MAGIC - Execute database queries and retrieve specific information
# MAGIC - Perform complex calculations and statistical analysis
# MAGIC - Interact with external APIs and web services
# MAGIC - Process and transform data in various formats
# MAGIC - Generate reports, visualizations, and summaries
# MAGIC - Make real-time decisions based on current data

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. How Tools Differ from Traditional AI Components
# MAGIC
# MAGIC It's important to understand how agent tools relate to other AI technologies. Here are examples to help distinguish between tools and machine learning models, chatbots, and traditional APIs:
# MAGIC
# MAGIC #### **Tools vs. Machine Learning Models**
# MAGIC - **ML Models**: Provide intelligence (prediction, generation, reasoning) used by agents
# MAGIC - **Agent Tools**: Executable capabilities an agent can call to take action or retrieve information — some tools may call ML models, others may call APIs, databases, or run business logic
# MAGIC - **Example**: A sentiment model scores a customer message; the agent uses a tool (e.g., `escalate_ticket`) to act based on that score
# MAGIC
# MAGIC #### **Tools vs. Chatbots**
# MAGIC - **Chatbots**: Provide conversational responses within a bounded scope (scripts, retrieval, predefined flows)
# MAGIC - **Agent Tools**: Allow an agent to go beyond responding — the agent can decide to execute actions (e.g., search a database, send an email, write to a record)
# MAGIC - **Key Point**: Chatbots converse; agents use tools to *do things* in the real world
# MAGIC
# MAGIC #### **Tools vs. Traditional APIs**
# MAGIC - **Traditional APIs**: Require manual programming to choose and call functions
# MAGIC - **Agent Tools**: Can be dynamically selected and orchestrated by AI reasoning based on context and goals
# MAGIC - **Intelligence**: Tools expose metadata and descriptions so the agent understands *when* and *how* to use them

# COMMAND ----------

# MAGIC %md
# MAGIC ### B3. Tool Selection and Orchestration
# MAGIC
# MAGIC One of the key capabilities of modern AI agents is **intelligent tool selection**. When presented with a user request, the agent must:
# MAGIC
# MAGIC 1. **Analyze the Request**: Understand what the user is trying to accomplish
# MAGIC 2. **Identify Required Tools**: Determine which tools are needed to fulfill the request
# MAGIC 3. **Plan Execution Order**: Decide the sequence in which tools should be called
# MAGIC 4. **Execute and Coordinate**: Call tools with appropriate parameters and handle responses
# MAGIC 5. **Synthesize Results**: Combine outputs from multiple tools into a coherent response
# MAGIC 6. **Learn and Adapt**: Improve tool selection based on success patterns
# MAGIC
# MAGIC This orchestration capability allows agents to handle complex, multi-step workflows automatically, making them ideal for scenarios requiring dynamic problem-solving approaches.

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Unity Catalog and Agent Tool Governance
# MAGIC It's important to understand the tooling ecosystem on Databricks, so you can decide which tool use case is best for you. Currently, there are three options for creating agent tools:
# MAGIC 1. **Unity Catalog function tools**: This is the primary focus of this course. Your tools are defined as UC UDFs and are managed in UC as a central registry for your agent's tools. This allows for built-in security and compliance features while granting easier discoverability and reuse. 
# MAGIC 1. **Agent-code tools**: These are tools defined directly in an agent's code. This is best for calling REST APIs, running arbitrary code, or running low-latency tools. However, this approach lacks built-in governance and discoverability that UC brings to the table. 
# MAGIC 1. **Model Context Protocol (MCP) tools**: These are tools that follow the MCP standard for tool interoperability. Databricks-managed MCP servers are currently available and you can check the release status [here](https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp). 

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Why Unity Catalog for Agent Tools?
# MAGIC Now that we have an understanding of what the basics of what makes an agent an agent, let's turn our attention to understanding how Databricks enables tool calling by first looking at where tools are stored and how they're governed on the platform via Unity Catalog. 
# MAGIC
# MAGIC ![example-agent-framework-with-uc.png](../Includes/images/example-agent-framework-with-uc.png "example-agent-framework-with-uc.png")
# MAGIC
# MAGIC <p align="center"><em>Traditional tool calling lacks comprehensive governance. With Unity Catalog, users can build tools for retrieving structured and unstructured data and test those tools in the AI Playground. When connecting external tools (such as Slack, Google Calendar, or any API service) via Unity Catalog connections, the management of credentials and authentication is governed by Unity Catalog policies. This means you can ensure secure, auditable access and apply organization-wide governance for integrations with external services </em></p>
# MAGIC
# MAGIC **Unity Catalog** provides the foundation for agent tool management with enterprise-grade capabilities:
# MAGIC
# MAGIC 1. **Centralized Governance**
# MAGIC     - Unified object model and three-level namespace for data and AI assets, including functions, across all UC-enabled workspaces.
# MAGIC     - Built-in auditing and lineage, with system tables to simplify access and analysis.
# MAGIC     - Consistent metadata and discoverability via Catalog Explorer and search.
# MAGIC     - Governed tools: functions registered in UC can be used as agent tools, enabling reuse and control.
# MAGIC 1. **Security and Access Control**
# MAGIC     - Fine-grained permissions (ANSI GRANTs), including EXECUTE on functions/tools.
# MAGIC     - Centralized identity integration (SCIM, account-level identities) for consistent access across workspaces.
# MAGIC     - Secure, isolated execution for Python UDFs; governed access to external connections and locations.
# MAGIC         - Python UDFs require Unity Catalog and either a serverless/pro SQL warehouse, or UC-enabled clusters. 
# MAGIC     - Role-based hierarchical privileges aligned to catalogs → schemas → objects (tables, views, volumes, models, functions).
# MAGIC 1. **Discoverability and Documentation**
# MAGIC     - Searchable catalog with rich metadata (function and parameter comments), lineage, and browse capabilities.
# MAGIC     - Recommended docstrings for functions (purpose, parameters, return value, examples, change log) to aid tool calling.
# MAGIC     - Platform support for AI-powered documentation to accelerate discovery for governed assets.
# MAGIC 1. **Scalability and Performance**
# MAGIC     - UC‑governed tools run via Databricks compute; agent tool execution uses serverless generic compute (Spark Connect serverless). Some integrations can execute UC functions via SQL Warehouses (uc_function).
# MAGIC     - Scaling and concurrency controls on SQL Warehouses; autoscaling on clusters to match workload demand.
# MAGIC 1. **External Tool Support**
# MAGIC     -  When connecting [external tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/external-connection-tools) (such as Slack, Google Calendar, or any API service) via Unity Catalog connections, the management of credentials and authentication is governed by Unity Catalog policies. This means you can ensure secure, auditable access and apply organization-wide governance for integrations with external services.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Tool Registration and Management
# MAGIC
# MAGIC Unity Catalog provides multiple approaches for registering and managing SQL-based agent tools. For tracing tool usage with your agent, Databricks leverages its managed MLflow agent tooling features like automatic signature and tracing and ResponseAgent interface. This course will concentrate on the fundamentals of tool calling by keeping the tool logic simple and direct (e.g. we will not go into an agent's ability to perform [vector search](https://www.databricks.com/product/machine-learning/vector-search)) so you can focus on how to use the Databrick platform for developing agents.
# MAGIC
# MAGIC #### **SQL-Based Registration**
# MAGIC Using `CREATE OR REPLACE FUNCTION` statements with comprehensive metadata that can be used with LLMs:
# MAGIC - Clear parameter definitions with types and descriptions
# MAGIC - Function-level documentation and usage guidance
# MAGIC - Deterministic behavior specifications
# MAGIC - Built-in validation and error handling
# MAGIC
# MAGIC #### **Programmatic Registration**
# MAGIC Using the `DatabricksFunctionClient()` for automated tool management:
# MAGIC - Programmatic creation and updates
# MAGIC - Integration with CI/CD pipelines
# MAGIC - Batch operations and bulk management
# MAGIC - Automated testing and validation workflows
# MAGIC
# MAGIC #### **Documentation Best Practices**
# MAGIC SQL functions should include rich metadata to help AI agents understand their purpose:
# MAGIC - Comprehensive function comments explaining business logic
# MAGIC - Parameter descriptions with expected data types and ranges
# MAGIC - Return value specifications and example outputs
# MAGIC - Usage examples and common patterns
# MAGIC - Mark functions `DETERMINISTIC` [where appropriate](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function#parameters)
# MAGIC
# MAGIC Both approaches ensure that SQL functions are properly documented, versioned, and accessible to AI agents while maintaining governance and security standards.
# MAGIC
# MAGIC
# MAGIC MLflow is foundational for building, monitoring, and deploying agent-based applications on Databricks, providing robust tracing, versioning, evaluation, and production deployment, especially when working with agent tooling
# MAGIC ![example-agent-framework-with-sql-function.png](../Includes/images/example-agent-framework-with-sql-function.png "example-agent-framework-with-sql-function.png")
# MAGIC
# MAGIC
# MAGIC <p align="center"><em>Example of agent framework and basic structure of UC SQL function.</em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ### C3. Other Tools and Common Patterns
# MAGIC While we will focus on agent tools in UC, it's important to point out that there are other tools that exist outside those discussed in this course. 
# MAGIC
# MAGIC #### Model Context Protocol (MCP)
# MAGIC The main benefit of MCP is standardization. You can create a tool once and use it with any agent—whether it's one you've built or a third-party agent. Similarly, you can use tools developed by others, either from your team or from outside your organization.
# MAGIC > You can read more about MCP on Databricks [here](https://docs.databricks.com/aws/en/generative-ai/mcp/). You can also read the official MCP documentation [here](https://modelcontextprotocol.io/docs/getting-started/intro). 
# MAGIC #### Mosaic AI Vector Search
# MAGIC Mosaic AI Vector Search is a vector search solution that is built into the Databricks Data Intelligence Platform and integrated with its governance and productivity tools. Vector search is a type of search optimized for retrieving embeddings.
# MAGIC > You can read more about vector search [here](https://docs.databricks.com/aws/en/vector-search/vector-search).  
# MAGIC #### Common Tool Patterns
# MAGIC Below is a summary of some common tool patterns, as well as additional links for reading, that exist on Databricks today. 
# MAGIC | Tool pattern| Description|
# MAGIC |-------------|------------|
# MAGIC | **[Structured data retrieval tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/structured-retrieval-tools)** | Query SQL tables, databases, and structured data sources.                                   |
# MAGIC | **[Unstructured data retrieval tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/unstructured-retrieval-tools)** | Search document collections and perform retrieval-augmented generation.                    |
# MAGIC | **[Code interpreter tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/code-interpreter-tools)**         | Allow agents to run Python code for calculations, data analysis, and dynamic processing.   |
# MAGIC | **[External connection tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/external-connection-tools)**      | Connect to external services and APIs such as Slack.                                        |
# MAGIC | **[AI Playground prototyping](https://docs.databricks.com/aws/en/generative-ai/agent-framework/ai-playground-agent)**      | Use the AI Playground to quickly add Unity Catalog tools to agents and prototype behavior. |
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC You now have a comprehensive foundation in the concepts and principles underlying AI agents and UC function tools on Databricks. This lecture has covered the evolution of AI agents from simple rule-based systems to today's sophisticated, tool-enabled systems that are transforming industries worldwide.
# MAGIC
# MAGIC Key takeaways from this lecture include:
# MAGIC
# MAGIC - **AI agents** are autonomous systems that combine perception, decision-making, and action capabilities to solve complex problems
# MAGIC - **Agent tools** extend AI capabilities by providing interfaces to external systems, data sources, and specialized functions
# MAGIC - **Unity Catalog** provides the governance, security, and management framework needed for enterprise-grade agent tool deployment
# MAGIC
# MAGIC Now that you have an understanding of what an agent is and how tools are a core component of agentic behavior, let's dive a little deeper into UC tools on Databricks. 
# MAGIC
# MAGIC ## Next Steps
# MAGIC - Continue to the next demonstration for building SQL functions and testing them in the AI Playground.
# MAGIC - For more training on agents, please see our other course offerings in the [Databricks course catalog](https://www.databricks.com/training/catalog?search=agent). 

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>