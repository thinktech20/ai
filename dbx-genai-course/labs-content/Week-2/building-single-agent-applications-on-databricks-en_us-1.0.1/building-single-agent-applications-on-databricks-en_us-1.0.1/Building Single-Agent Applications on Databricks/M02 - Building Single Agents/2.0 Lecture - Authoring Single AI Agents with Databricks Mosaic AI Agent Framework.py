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
# MAGIC # Lecture - Authoring Single AI Agents with Databricks Mosaic AI Agent Framework
# MAGIC
# MAGIC This lecture notebook explores how Databricks supports the development of single AI agents through its comprehensive Mosaic AI Agent Framework. We'll examine the tools, frameworks, and best practices for creating production-ready AI agents on the Databricks platform.
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC The Databricks Mosaic AI Agent Framework provides a unified platform for authoring, deploying, and monitoring AI agents. This framework supports multiple popular agent development libraries including LangChain, LangGraph, DSPy, and OpenAI, while providing native integration with Databricks services like Vector Search, Model Serving, and MLflow.
# MAGIC
# MAGIC The framework emphasizes production readiness through features like automatic tracing, comprehensive evaluation capabilities, and seamless deployment to Mosaic AI Model Serving. Whether you're building simple chat agents or complex multi-agent systems, Databricks provides the tools and infrastructure needed for enterprise-scale AI applications.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC
# MAGIC _By the end of this lecture, you will be able to:_
# MAGIC - Understand the architecture and components of Databricks Mosaic AI Agent Framework
# MAGIC - Explain the benefits of using ResponsesAgent for production-grade agent development
# MAGIC - Identify the supported agent authoring frameworks and their integration patterns
# MAGIC - Describe the deployment considerations for agents
# MAGIC - Recognize advanced features like streaming, custom inputs/outputs, and retriever integration

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Introduction to Mosaic AI Agent Framework
# MAGIC
# MAGIC The Databricks Mosaic AI Agent Framework represents a comprehensive solution for building, deploying, and managing AI agents at enterprise scale. This framework addresses the complete _agent lifecycle_ from development to production monitoring.
# MAGIC
# MAGIC ### An Agent's Lifecycle
# MAGIC An agent's lifecycle can be summarized as follows:
# MAGIC 1. **Prepare data and create tools**:  
# MAGIC     - This phase includes AI-related ETL using Notebooks, SQL queries, and the Lakeflow suite. Typically, this is where the AI engineer embeds and indexes unstructured data with Vector Search. 
# MAGIC     - Once the data is prepared, the engineer moves on to creating tools in either SQL or Python syntax and registers those tools in [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) for comprehensive governance. 
# MAGIC 1. **Rapid prototyping with quality checks**
# MAGIC     - In this phase, typically rapid tests are performed with AI Playground's no-code interface for rapid prototyping agents. Here you can specify a system prompt, select different models and compare them side-by-side and vibe check the results. 
# MAGIC     - The AI engineer then evaluates the content with [evaluation tools with MLflow 3](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/), which is designed to help you identify quality issues and the root cause of those issues. 
# MAGIC     - Once rapid prototyping has been completed, you can export the code from the playground and leverage `mlflow.genai.evaluate()` (read more [here](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/concepts/eval-harness)).  
# MAGIC 1. **Evaluate and collect feedback**
# MAGIC     - Test the agent against evaluation datasets using methods such as LLM judges, stakeholder labeling, and synthetic data. Stakeholder/domain expert feedback is gathered, typically through review apps or direct tracing of interactions. 
# MAGIC 1. **Label data and feedback**
# MAGIC     - Interactions and outputs are labeled to create high-quality benchmarks for testing future agent iterations. This creates an evaluation set that serves as ground truth for quality assessment.
# MAGIC     - Labeling sessions provide a structured way to gather feedback from domain experts on the behavior of your GenAI applications.  You can read more about labeling sessions [here](https://docs.databricks.com/aws/en/mlflow3/genai/human-feedback/concepts/labeling-sessions).
# MAGIC 1. **Iterative improvement**
# MAGIC     - Use feedback and benchmark results to identify and fix root causes of quality issues. 
# MAGIC     - Evaluate multiple versions/configurations to achieve the desired balance of accuracy, safety, cost, and latency.
# MAGIC 1. **Deploy to production**
# MAGIC     - The agent moves from development to a scalable, production-ready environment (often REST API via Model Serving). Here, agents are governed for access and compliance, leveraging components such as Unity Catalog for unified governance.
# MAGIC 1. **Monitor quality and performance**
# MAGIC     - Post-deployment, agents are continuously monitored using the same evaluation and tracing tools as in development. Logs, traces, user feedback, and automated judges provide ongoing quality signals; new data from production interactions is incorporated into evaluation sets for future improvements.
# MAGIC     - [AI Gateway-enhanced](https://docs.databricks.com/aws/en/ai-gateway/) inference tables are automatically enabled for deployed agents, which provides access to detailed request log metadata when using the Mosaic AI Agent Framework with popular agent authoring libraries like DSPy and LangChain. 
# MAGIC     - [MLflow tracing](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/) can be leveraged for end-to-end observability. 
# MAGIC     - [Production monitoring for GenAI lets you automatically run MLflow scorers on traces from production GenAI apps](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/production-monitoring)
# MAGIC
# MAGIC > The demo that follows this lecture will focus on prototyping agents with supported frameworks.  
# MAGIC
# MAGIC ![single-agents-course.png](../Includes/images/single-agents-course.png "single-agents-course.png")
# MAGIC <p>
# MAGIC <em>
# MAGIC This lecture will be concerned with agent framework. 
# MAGIC </em>
# MAGIC </p>

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Framework Architecture
# MAGIC
# MAGIC Assuming you have completed initial testing of your UC/external tools both in Notebooks/SQL Editor and the AI Playground, you are now ready to take a look at agent frameworks. To aid with this, Databricks offers a suite of tooling to author, deploy, and monitor high-quality agentic and RAG applications with the Mosaic AI Agent Framework. This framework is built around several key components:
# MAGIC
# MAGIC - **MLflow 3 Integration**: Provides experiment tracking, model logging, and lifecycle management
# MAGIC - **ResponsesAgent Interface**: A production-ready interface compatible with OpenAI Responses schema
# MAGIC - **Agent Authoring Libraries**: Support for LangChain, LangGraph, DSPy, and OpenAI
# MAGIC - **Databricks AI Bridge**: Integration packages that connect agents to Databricks AI features
# MAGIC - **Agent Governance**: Tools and agents are registered and governed in UC; inference logs/traces via AI Gateway and MLflow tracing. 
# MAGIC - **Mosaic AI Model Serving**: Scalable deployment infrastructure for production agents
# MAGIC - **Evaluation & Monitoring**: Built-in tools for agent quality assessment and performance tracking

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Requirements and Setup
# MAGIC
# MAGIC To develop agents using the Databricks framework, you will need to be aware of some technical platform requirements and packages. 
# MAGIC
# MAGIC **Core Requirements:**
# MAGIC - `databricks-agents` 1.2.0 or above
# MAGIC - `mlflow` 3.1.3 or above
# MAGIC - Python 3.10 or above
# MAGIC - Serverless compute or Databricks Runtime 13.3 LTS or above
# MAGIC
# MAGIC **Installation Command:**
# MAGIC ```python
# MAGIC %pip install -U -qqqq databricks-agents mlflow
# MAGIC ```
# MAGIC
# MAGIC **AI Bridge Integration Packages:**
# MAGIC The Databricks AI Bridge library provides a shared layer of APIs to interact with Databricks AI features, such as Databricks AI/BI Genie and Vector Search. You can see the latest release notes and versions on [PyPi](https://pypi.org/project/databricks-ai-bridge/).
# MAGIC - `databricks-openai` for OpenAI integration
# MAGIC - `databricks-langchain` for LangChain/LangGraph integration
# MAGIC - `databricks-dspy` for DSPy integration
# MAGIC - `databricks-ai-bridge` for pure Python agents (without dedicated integration packages)

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. ResponsesAgent: The Production Interface
# MAGIC
# MAGIC Databricks recommends the MLflow `ResponsesAgent` interface as the primary method for creating production-grade agents. This interface provides compatibility with the OpenAI Responses schema while adding Databricks-specific enhancements.
# MAGIC
# MAGIC > If you are familiar with [`ChatAgent`](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-legacy-schema), `ResponsesAgent` is meant to replace this interface for new agents.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. ResponsesAgent Benefits
# MAGIC
# MAGIC The `ResponsesAgent` interface offers significant advantages over traditional agent interfaces, [while also supporting wrapping existing agents in supporting frameworks](https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent?language=Streaming+with+code+re-use#what-if-i-already-have-an-agent). 
# MAGIC
# MAGIC **Advanced Agent Capabilities:**
# MAGIC - Multi-agent support for complex workflows
# MAGIC - Streaming output with real-time response chunks
# MAGIC - Comprehensive tool-calling message history
# MAGIC - Tool-calling confirmation support
# MAGIC - Long-running tool execution support
# MAGIC
# MAGIC **Streamlined Development & Deployment:**
# MAGIC - Framework-agnostic: Wrap any existing agent for Databricks compatibility
# MAGIC - Typed authoring interfaces with IDE autocomplete support
# MAGIC - Automatic signature inference during model logging
# MAGIC     > If you are not use the recommended `ResponsesAgent` interface, you must either manually define your signature or use MLflow's Model Signature inferencing capabilities to automatically generate the agent's signature based on input examples. Read more [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/log-agent#infer-model-signature-during-logging). 
# MAGIC - Automatic tracing with aggregated streamed responses via `predict` and `predict_stream`
# MAGIC     > `ResponsesAgent` requires implementing a `predict` method that returns `ResponsesAgentResponse` to handle non-streaming requests. On the other hand, for streaming agents, you can implement a `predict_stream` method. This goes beyond the scope of this lecture, but you can read more [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent?language=Streaming+with+code+re-use).  
# MAGIC - AI Gateway-enhanced inference tables for detailed logging

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. `ResponsesAgent` Schema Structure
# MAGIC
# MAGIC The `ResponsesAgent` uses a structured schema for inputs and outputs:
# MAGIC
# MAGIC **Input Format (`ResponsesAgentRequest`):**
# MAGIC ```python
# MAGIC {
# MAGIC "input": [
# MAGIC {
# MAGIC "role": "user",
# MAGIC "content": "What did the data scientist say when their Spark job finally completed?"
# MAGIC }
# MAGIC ]
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC **Output Format (`ResponsesAgentResponse`):**
# MAGIC ```python
# MAGIC ResponsesAgentResponse(
# MAGIC output=[
# MAGIC {
# MAGIC "type": "message",
# MAGIC "id": str(uuid.uuid4()),
# MAGIC "content": [{"type": "output_text", "text": "Well, that really sparked joy!"}],
# MAGIC "role": "assistant",
# MAGIC }
# MAGIC ]
# MAGIC )
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### B3. Wrapping Existing Agents
# MAGIC
# MAGIC If you already have an agent built with LangChain, LangGraph, or similar frameworks, you don't need to rewrite it. Instead, create a wrapper class that inherits from `mlflow.pyfunc.ResponsesAgent`:
# MAGIC
# MAGIC **Basic Wrapper Pattern:**
# MAGIC ```python
# MAGIC from uuid import uuid4
# MAGIC from mlflow.pyfunc import ResponsesAgent
# MAGIC from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
# MAGIC
# MAGIC class MyWrappedAgent(ResponsesAgent):
# MAGIC     def __init__(self, agent):
# MAGIC         # Reference your existing agent (LangChain/LangGraph/OpenAI, etc.)
# MAGIC         self.agent = agent
# MAGIC
# MAGIC     def prep_msgs_for_llm(self, messages: list[dict]) -> list[dict]:
# MAGIC         # Implement conversion from ResponsesAgentRequest messages to your agent's expected format
# MAGIC         return messages
# MAGIC
# MAGIC     def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
# MAGIC         # Convert incoming messages to your agent's format
# MAGIC         messages = self.prep_msgs_for_llm([i.model_dump() for i in request.input])
# MAGIC
# MAGIC         # Call your existing agent (non-streaming)
# MAGIC         agent_response = self.agent.invoke(messages)
# MAGIC
# MAGIC         # Ensure string output; convert if necessary
# MAGIC         if not isinstance(agent_response, str):
# MAGIC             agent_response = str(agent_response)
# MAGIC
# MAGIC         # Convert to ResponsesAgent format
# MAGIC         output_item = self.create_text_output_item(text=agent_response, id=str(uuid4()))
# MAGIC         return ResponsesAgentResponse(output=[output_item])
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Supported Agent Authoring Frameworks
# MAGIC
# MAGIC Databricks supports multiple popular frameworks for agent development, each with specific strengths and use cases.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. LangChain Integration
# MAGIC
# MAGIC LangChain is a comprehensive framework for building LLM applications with extensive integrations and capabilities.
# MAGIC
# MAGIC **Key Features on Databricks:**
# MAGIC - Use Databricks-served models as LLMs or embeddings
# MAGIC - Integration with Mosaic AI Vector Search for vector storage
# MAGIC - MLflow experiment tracking and performance monitoring
# MAGIC - MLflow Tracing for development and production observability
# MAGIC - PySpark DataFrame loader for seamless data integration
# MAGIC - Spark DataFrame Agent and Databricks SQL Agent for natural language querying
# MAGIC
# MAGIC **Example Usage:**
# MAGIC ```python
# MAGIC from databricks_langchain import ChatDatabricks
# MAGIC
# MAGIC chat_model = ChatDatabricks(
# MAGIC endpoint="databricks-gpt-5-1",
# MAGIC temperature=0.1,
# MAGIC max_tokens=250,
# MAGIC )
# MAGIC chat_model.invoke("How to use Databricks?")
# MAGIC ```
# MAGIC > Keep in mind that [LangChain on Databricks](https://docs.databricks.com/aws/en/large-language-models/langchain) for LLM development are experimental features and the API definitions might change over time.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. DSPy Framework
# MAGIC
# MAGIC [DSPy](https://docs.databricks.com/aws/en/generative-ai/dspy#what-is-dspy) is a framework for programmatically defining and optimizing generative AI agents with automated prompt engineering capabilities.
# MAGIC
# MAGIC **Core DSPy Components:**
# MAGIC - **Modules**: Components handling specific text transformations (replacing hand-written prompts)
# MAGIC - **Signatures**: Natural language descriptions of input/output behavior ("question -> answer")
# MAGIC - **Compiler**: Optimization tool that improves pipelines by adjusting modules for performance metrics
# MAGIC - **Program**: Connected modules forming a pipeline for complex tasks
# MAGIC
# MAGIC **DSPy Advantages:**
# MAGIC - Automated prompt optimization
# MAGIC - Systematic approach to agent improvement
# MAGIC - Built-in performance optimization capabilities
# MAGIC - Programmatic rather than manual prompt engineering

# COMMAND ----------

# MAGIC %md
# MAGIC ### C3. OpenAI Integration
# MAGIC
# MAGIC Databricks provides native support for OpenAI-style agents while leveraging Databricks-hosted models.
# MAGIC
# MAGIC **Integration Benefits:**
# MAGIC - Use familiar OpenAI API patterns
# MAGIC - Leverage Databricks Foundation Model APIs
# MAGIC - Seamless migration from OpenAI to Databricks models
# MAGIC - Support for both streaming and non-streaming responses
# MAGIC - Tool-calling capabilities with Databricks models

# COMMAND ----------

# MAGIC %md
# MAGIC ### C4. LangGraph for Complex Workflows
# MAGIC
# MAGIC LangGraph extends LangChain with graph-based agent orchestration for more complex, stateful workflows.
# MAGIC
# MAGIC **LangGraph Capabilities:**
# MAGIC - Graph-based agent workflows
# MAGIC - State management across agent interactions
# MAGIC - Complex decision trees and conditional logic
# MAGIC - Multi-step reasoning and tool coordination

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Streaming and Real-Time Responses
# MAGIC
# MAGIC Streaming capabilities allow agents to provide real-time responses in chunks, improving user experience and enabling interactive applications. The idea is to wait for a complete response before sending the result to a user. With MLflow, you can not only view the agent's response, but also these chunks and thought processes, which can lead to insight as to why it chose or did not choose to use a particular tool.
# MAGIC
# MAGIC > [The Knowledge Assistant with Agent Bricks](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/knowledge-assistant) has full streaming support, as seen in the screenshot below showing the trace of a KA response. 
# MAGIC
# MAGIC ![mlflow-ui.png](../Includes/images/mlflow-ui.png "mlflow-ui.png")
# MAGIC <p><em>Example of chunked tracing with MLflow via the Knowledge Assistant with Agent Bricks.</em></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. Streaming Implementation
# MAGIC
# MAGIC To implement streaming with `ResponsesAgent`, follow this pattern:
# MAGIC
# MAGIC 1. **Emit Delta Events**: Send multiple `output_text.delta` events with the same `item_id`
# MAGIC 2. **Finish with Done Event**: Send a final `response.output_item.done` event containing complete output
# MAGIC
# MAGIC **Streaming Benefits:**
# MAGIC - Real-time user feedback
# MAGIC - Improved perceived performance
# MAGIC - Better user engagement for long-running operations
# MAGIC - Automatic MLflow tracing integration
# MAGIC - Aggregated responses in AI Gateway inference tables
# MAGIC
# MAGIC ![mlflow-chunking.png](../Includes/images/mlflow-chunking.png "mlflow-chunking.png")
# MAGIC <p><em>
# MAGIC Streaming responses with MLflow via chunks of outputs that are rendered as a complete thought. 
# MAGIC </em>
# MAGIC </p>
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### D2. Error Handling in Streaming
# MAGIC
# MAGIC Mosaic AI propagates streaming errors through the last token under `databricks_output.error`:
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "delta": "...",
# MAGIC   "databricks_output": {
# MAGIC     "trace": {...},
# MAGIC     "error": {
# MAGIC       "error_code": "BAD_REQUEST",
# MAGIC       "message": "TimeoutException: Tool XYZ failed to execute."
# MAGIC     }
# MAGIC   }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC **Note:** Client applications must handle and surface these errors appropriately.

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. (Optional) Advanced Features and Customization
# MAGIC
# MAGIC The Databricks Agent Framework provides several advanced features for sophisticated agent implementations. The topics given below go beyond the scope of this course.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E1. Custom Inputs and Outputs
# MAGIC
# MAGIC Some scenarios require additional agent inputs (like `client_type`, `session_id`) or outputs (like retrieval source links) that shouldn't be included in chat history.
# MAGIC
# MAGIC **Custom Fields Support:**
# MAGIC - `custom_inputs`: Additional input parameters beyond standard messages. You can read more about custom inputs and output [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent#custom-inputs-and-outputs).
# MAGIC - `custom_outputs`: Additional output data not part of conversation flow
# MAGIC - Access via `request.custom_inputs` in agent code
# MAGIC - JSON configuration in AI Playground and review apps
# MAGIC
# MAGIC **Important Limitation:**
# MAGIC The Agent Evaluation review app does not support rendering traces for agents with additional input fields.
# MAGIC
# MAGIC > You can read more about advanced features in this regard [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent#advanced-features). This goes beyond the scope of this course.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E2. Retriever Integration and Schema
# MAGIC
# MAGIC AI agents commonly use retrievers for unstructured data from vector search indices. Databricks provides specialized support for retriever tracing and evaluation. You can read more about retriever integration [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/unstructured-retrieval-tools#set-retriever-schema-to-ensure-mlflow-compatibility). 
# MAGIC
# MAGIC **Retriever Benefits:**
# MAGIC - Automatic source document links in AI Playground UI
# MAGIC - Automatic retrieval groundedness and relevance evaluation
# MAGIC - Integration with Databricks AI Bridge retriever tools
# MAGIC
# MAGIC **Custom Retriever Schema:**
# MAGIC ```python
# MAGIC import mlflow
# MAGIC
# MAGIC mlflow.models.set_retriever_schema(
# MAGIC name="mlflow_docs_vector_search",
# MAGIC primary_key="document_id",      # Document ID field
# MAGIC text_column="chunk_text",       # Content field
# MAGIC doc_uri="doc_uri",             # Document URI field
# MAGIC other_columns=["title"],        # Additional metadata
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC > This goes beyond the scope of this course. You can read more about retriever tools [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/unstructured-retrieval-tools).

# COMMAND ----------

# MAGIC %md
# MAGIC ### E3. Multi-Agent Systems
# MAGIC
# MAGIC Databricks supports complex multi-agent systems where multiple specialized agents collaborate to solve problems.
# MAGIC
# MAGIC > This goes beyond the scope of this course. To learn more about multi-agent systems managed by databricks, you can read documentation on [Genie](https://docs.databricks.com/aws/en/generative-ai/agent-framework/multi-agent-genie) and [Agent Bricks](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor). You can read more about Genie with multi-agent systems [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/multi-agent-genie).

# COMMAND ----------

# MAGIC %md
# MAGIC ### E4. Stateful Agents
# MAGIC
# MAGIC Stateful agents can maintain memory across conversation threads and provide conversation checkpointing capabilities.
# MAGIC
# MAGIC > This goes beyond the scope of this course. To learn more about stateful agents, please see [this](https://docs.databricks.com/aws/en/generative-ai/agent-framework/stateful-agents) documentation. You can read more about stateful AI agents [here](https://docs.databricks.com/aws/en/generative-ai/agent-framework/stateful-agents).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC The Databricks Mosaic AI Agent Framework provides a comprehensive platform for building production-ready AI agents. Key takeaways include understanding popular framework strengths (e.g. LangChain), develop and understanding for best practices when building an agent's lifecycle, and production considerations.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>