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
# MAGIC # Lecture - Building Agents on Databricks with MLflow
# MAGIC
# MAGIC MLflow enhances GenAI applications with end-to-end tracking, observability and evaluations, all within one integrated platform. Therefore, it supports the whole lifecycle of AI agents: from development, evaluation, deployment and all the way up to production monitoring. This lecture explores how MLflow's comprehensive capabilities make it an essential component in the agent development lifecycle, from initial prototyping through production deployment and ongoing observability.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC _By the end of this lecture, you will be able to:_
# MAGIC
# MAGIC - Explain how MLflow's experiment tracking capabilities support iterative agent development
# MAGIC - Describe the role of MLflow tracing and tagging in providing comprehensive agent observability
# MAGIC - Identify how MLflow's model registry enables reproducible and governed agent deployments
# MAGIC - Analyze the benefits of MLflow's integration with Unity Catalog for enterprise agent management
# MAGIC
# MAGIC > This lecture is meant to serve as an introduction to basic MLflow concepts for agents. This is not meant to be an exhaustive explanation of all the components of MLflow. This lecture focuses on [Databricks managed MLflow](https://www.databricks.com/product/managed-mlflow). For documentation on OSS MLflow, you can read more [here](https://mlflow.org/).

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. The Agent Development Challenge
# MAGIC
# MAGIC Building production-ready AI agents presents unique challenges that traditional machine learning workflows don't fully address. Understanding these challenges helps us appreciate why MLflow on Databricks has made Databricks a comprehensive platform for the whole agent lifecycle.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Complexity of Agent Systems
# MAGIC
# MAGIC AI agents are fundamentally different from traditional ML models in several key ways:
# MAGIC
# MAGIC - **Multi-step reasoning**: Agents perform complex, multi-turn interactions that involve planning, tool usage, and decision-making across multiple steps
# MAGIC - **Dynamic behavior**: Unlike static models, agents can exhibit different behaviors based on context, available tools, and conversation history
# MAGIC - **Tool integration**: Agents must seamlessly integrate with external systems, APIs, and data sources to accomplish tasks
# MAGIC - **Conversational context**: Maintaining state and context across multi-turn conversations adds complexity to deployment and monitoring
# MAGIC
# MAGIC These characteristics create unique requirements for development, testing, and production monitoring that traditional ML platforms weren't originally designed to handle.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Observability Requirements
# MAGIC
# MAGIC Agent observability goes far beyond traditional model monitoring:
# MAGIC
# MAGIC - **Execution tracing**: Understanding the step-by-step reasoning process, including which tools were called and why
# MAGIC - **Performance analysis**: Tracking latency, token usage, and costs across complex multi-step workflows
# MAGIC - **Quality assessment**: Evaluating not just final outputs but intermediate reasoning steps and tool usage patterns
# MAGIC - **Error diagnosis**: Identifying where failures occur in multi-step processes and understanding their root causes
# MAGIC
# MAGIC Without proper observability, debugging agent behavior becomes nearly impossible, especially in production environments.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Governance and Reproducibility Challenges
# MAGIC
# MAGIC Enterprise deployment of agents requires robust governance capabilities:
# MAGIC
# MAGIC - **Version management**: Tracking changes to agent logic, prompts, tools, and configurations
# MAGIC - **Reproducibility**: Ensuring consistent behavior across development, staging, and production environments
# MAGIC - **Access control**: Managing who can deploy, modify, or access different agent versions
# MAGIC - **Audit trails**: Maintaining complete records of agent behavior for compliance and debugging
# MAGIC - **AI Guardrails**: Allows users to configure and enforce data compliance at the model-serving-endpoint level (read more [here](https://docs.databricks.com/aws/en/ai-gateway/#ai-guardrails).)
# MAGIC
# MAGIC These requirements necessitate a platform that can handle the full agent lifecycle with enterprise-grade governance features.

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. MLflow on Databricks
# MAGIC Here we will break down MLflow a little more to help understand how it addresses the issues raised in the previous section.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Why is Tracing Needed?
# MAGIC
# MAGIC To understand why we need tracing (and what it actually is), we need to understand traditional machine learning inference.
# MAGIC
# MAGIC ### Traditional ML inference (request/response)
# MAGIC A typical inference flow for machine learning is given by the following high-level steps:
# MAGIC 1. The client sends an input request to a request handler on the serving endpoint.
# MAGIC 1. The handler forwards the request to the model for inference.
# MAGIC 1. The model's output is returned through the handler to the client.
# MAGIC
# MAGIC In this basic scenario, the transparent components are often just the _input_ and _output_.
# MAGIC
# MAGIC For robust operations in the era of agents, we may also want insight into processes like **server-side transparency**, **latency/cost metrics**, and **API logging** (even though these may not be needed for ML workloads). These capabilities are standard with **Databricks Model Serving** and **AI Gateway** for production telemetry and governance. Databricks hosts **managed MLflow**, where setting your tracking URI to `databricks` logs **traces** to your workspace with built-in security, reliability, search, and UI. Additionally, [deploying with **Mosaic AI Agent Framework**](https://docs.databricks.com/aws/en/generative-ai/agent-framework/deploy-agent) automatically integrates real-time tracing and can enable the Review App and monitoring for production traffic.
# MAGIC
# MAGIC ### Agents need more insight
# MAGIC - Agents perform multiple intermediate steps (for example: retrieval, tool use, LLM calls), and you need to see each step, its inputs/outputs, and per-step latency/token usage to debug and improve quality.
# MAGIC - **MLflow Tracing** captures these as **traces** and **spans** automatically for supported libraries (OpenAI SDK, LangChain/LangGraph, DSPy, etc.) and provides a UI and APIs to analyze them across development and production.
# MAGIC - A single operation in a **tracing system** is called a **span**. It records when the operation started and ended, along with the metadata, inputs, and outputs per unit of work.
# MAGIC > MLflow spans follow the [OpenTelemetry standard](https://opentelemetry.io/docs/concepts/signals/traces/), which requires any extra information (like token counts) to be stored in key-value attributes on the span, not as custom fields.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Tracing for Agents
# MAGIC Now that we understand the struggle with developing agentic systems and why agents need more insights per unit of work, we're ready to define what a **trace** is. A **Trace** in the context of GenAI applications is a collection of spans arranged in a DAG-like structure, where each span represents a single operation. These single operations can be something like a function call or a database query.
# MAGIC
# MAGIC As an example, suppose you are working on developing an agent that is exposed to 3 UC tools. Suppose also that you are noticing slow execution times, but you're not sure what the issue is. The MLflow interface in Databricks can help you troubleshoot this scenario. For example, you can:
# MAGIC - View the specific Foundation Model API that was used for each reasoning step.
# MAGIC - View the system prompts (if any) used for the agent.
# MAGIC - Identify if tools have been called, the order they were called in, and their inputs/outputs.
# MAGIC - The agent's reasoning at each step.
# MAGIC - The latency to identify which tool took the longest to run. This can be useful to, for example, help build optimized SQL queries.
# MAGIC - Token usage is exposed per span and trace (aggregated).

# COMMAND ----------

# MAGIC %md
# MAGIC ### B3. Hierarchical Span Structure
# MAGIC
# MAGIC MLflow organizes trace data using a hierarchical span structure that mirrors agent execution, starting with a single root span that represents the overall request or workflow, with nested child spans for each sub-step.
# MAGIC
# MAGIC - **Parent spans**: High-level operations like "process user request"
# MAGIC - **Child spans**: Detailed steps like "call retrieval tool" or "generate response"
# MAGIC - **Span relationships**: Clear parent-child relationships that show execution flow, which should mimic your application's execution plan.
# MAGIC - **Span types**: Categorization of spans (`TOOL`, `CHAT_MODEL`, `RETRIEVER`) for better organization
# MAGIC
# MAGIC ![tracing-example.png](../Includes/images/tracing-example.png "tracing-example.png")
# MAGIC <p>
# MAGIC <em>
# MAGIC Example trace showing parent-child spans, relationships, span types, and model used.
# MAGIC </em>
# MAGIC </p>

# COMMAND ----------

# MAGIC %md
# MAGIC ### B4. Custom Tracing and Tagging
# MAGIC
# MAGIC MLflow provides flexible APIs for custom tracing needs as well (which we will see in our demonstration).
# MAGIC
# MAGIC - **Custom Tracing**: The [`@mlflow.trace`](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/manual-tracing/fluent-apis#decorator) decorator lets you turn any function into a traced span with almost no added work. When applied, it provides a lightweight but powerful way to instrument your code:
# MAGIC - MLflow **automatically infers** parent-child relationships between traced functions, ensuring full compatibility with auto-tracing integrations.
# MAGIC - Any exceptions raised within the function are **captured and logged as span events**.
# MAGIC - The function's name, inputs, outputs, and execution duration are recorded without additional configuration.
# MAGIC - It works seamlessly alongside auto-tracing features like `mlflow.openai.autolog`.
# MAGIC - Accepts the following arguments:
# MAGIC - `name`: parameter to override the span name from the default (the name of decorated function).
# MAGIC - `span_type`: parameter to set the type of span. Set either one of built-in [Span Types](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/data-model#span-types) or a string.
# MAGIC - `attributes` parameter to add custom attributes to the span.
# MAGIC
# MAGIC > **Function Type Considerations**
# MAGIC To view a complete list of function types and supported dependencies when using the `@mlflow.trace` decorator, please see [this documentation](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/manual-tracing/fluent-apis#decorator).
# MAGIC
# MAGIC - **Tagging**: Tags are flexible key-value pairs that you can update throughout the trace's lifecycle, while metadata is immutable and set once at trace creation.
# MAGIC ![tagging-example.png](../Includes/images/tagging-example.png "tagging-example.png")
# MAGIC <p>
# MAGIC <em>
# MAGIC Example showing how tags appear in MLflow interface.
# MAGIC </em>
# MAGIC </p>
# MAGIC
# MAGIC > This course will only be concerned with a subset of the Span object schema. You can read more about the Span object schema [here](https://mlflow.org/docs/latest/genai/concepts/span/#span-object-schema).

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Models in Unity Catalog for Agent Governance
# MAGIC
# MAGIC MLflow's integration with **Unity Catalog** enables enterprise-grade governance for agent deployments by registering agents as **Unity Catalog models**, so they can be managed with the same rigor as other business-critical assets.
# MAGIC
# MAGIC
# MAGIC ![mlflow-with-uc-diagram.png](../Includes/images/mlflow-with-uc-diagram.png "mlflow-with-uc-diagram.png")
# MAGIC <p>
# MAGIC <em>
# MAGIC Once you have your data source and tools registered to Unity Catalog (or external tools), you can register your agent code to UC by first packaging the agent with MLflow and using the model's URI.
# MAGIC </em>
# MAGIC </p>
# MAGIC
# MAGIC
# MAGIC ### Centralized governance via the Model Registry in UC
# MAGIC
# MAGIC Registering agents as UC models provides a centralized, cross-workspace catalog of agent assets:
# MAGIC - **Version management**: MLflow logs a point-in-time snapshot of agent code, configuration, and declared resources; each UC model version is an immutable snapshot you can reference and deploy.
# MAGIC - **Lineage tracking**: When you log inputs (for example with `mlflow.log_input`), UC shows lineage between models and upstream datasets; lineage is also captured for feature store training flows.
# MAGIC - **Access control**: Fine-grained UC privileges govern who can create, read, or modify models and who can execute functions, query tables, use connections, and access other resources your agent depends on.
# MAGIC - **Cross-workspace sharing**: Models in UC are discoverable and governable across workspaces attached to the same metastore.
# MAGIC - **Governed tags**: Tags can be applied to registered models and model versions; governed tags (public preview) enforce standardized keys/values and assignment permissions for consistent classification and control. See the docs [here](https://docs.databricks.com/aws/en/database-objects/tags#supported-securable-objects).
# MAGIC
# MAGIC ### Reproducible deployments
# MAGIC
# MAGIC Using UC + MLflow ensures that agent deployments are reproducible and observable:
# MAGIC - **Immutable versions**: Registered model versions are immutable snapshots; update metadata if needed, but changing code/dependencies requires a new version.
# MAGIC - **Dependency capture**: MLflow captures environment dependencies (for example via pip/conda) to enable consistent loading and serving.
# MAGIC - **Managed serving**: Deploy UC-registered agents to Model Serving endpoints with built-in scaling, tracing, and review apps for feedback and monitoring.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC MLflow has evolved into a comprehensive platform that addresses all aspects of AI agent development, from initial experimentation through production deployment and monitoring. Its combination of experiment tracking, tracing, model registry, and evaluation capabilities makes it uniquely suited to handle the complexity of modern AI agents.
# MAGIC
# MAGIC The platform's integration with Unity Catalog and the broader Databricks ecosystem provides the governance, security, and scalability needed for enterprise agent deployments. As AI agents become increasingly important in business applications, MLflow's role as the foundational platform for agent development will continue to grow.
# MAGIC
# MAGIC ## Next Steps
# MAGIC Now that you have a basic understanding of MLflow for tracing, tagging, and building reproducible agents with Unity Catalog, you are ready to complete the next demo where we discuss tracing with MLflow.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>