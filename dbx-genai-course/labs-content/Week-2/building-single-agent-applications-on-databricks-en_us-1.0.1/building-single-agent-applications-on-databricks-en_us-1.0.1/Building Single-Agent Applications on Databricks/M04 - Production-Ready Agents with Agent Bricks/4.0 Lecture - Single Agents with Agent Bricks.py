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
# MAGIC # Lecture - Single Agents with Agent Bricks
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC Agent Bricks provides a high-level abstraction designed to help technical users quickly build and optimize production-ready, domain-specific AI agents, focusing on automatic evaluation and optimization, including Agent Learning on Human Feedback (ALHF), to maximize quality while balancing cost considerations.
# MAGIC
# MAGIC Unlike traditional agent development approaches that require extensive manual configuration and optimization, **Agent Bricks streamlines the implementation process** so users can focus on the problem, data, and metrics instead of low-level technical details. The platform supports four distinct agent types, each optimized for specific use cases and deployment patterns.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC _By the end of this lecture, you will be able to:_
# MAGIC
# MAGIC - Understand the Agent Bricks development lifecycle and iterative optimization process
# MAGIC - Identify the four supported agent types and their specific use cases
# MAGIC - Explain the differences between automated and interactive agent categories
# MAGIC - Describe the optimization strategies for cost-performance balance
# MAGIC - Recognize the evaluation and monitoring capabilities built into Agent Bricks

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Introduction to Agent Bricks
# MAGIC
# MAGIC ![agent-bricks-cost.png](../Includes/images/agent-bricks-cost.png "agent-bricks-cost.png")
# MAGIC
# MAGIC Agent Bricks provides a simple, powerful approach to building domain-specific agent systems. The platform abstracts away much of the complexity traditionally associated with agent development while maintaining the flexibility needed for enterprise applications.
# MAGIC
# MAGIC The core philosophy of Agent Bricks is to enable users to focus on defining their business problems and providing relevant data, while the platform handles the technical complexities of agent optimization, evaluation, and deployment. This approach significantly reduces the time-to-value for AI agent implementations in enterprise environments.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Supported Agent Types and Use Cases
# MAGIC
# MAGIC Agent Bricks supports four primary agent types, each designed for specific enterprise use cases and operational patterns. Understanding these distinctions is crucial for selecting the appropriate agent type for your specific requirements.
# MAGIC
# MAGIC **The Four Agent Types:**
# MAGIC
# MAGIC 1. **Information Extraction (IE)**: Automated extraction of structured data from unstructured sources such as documents, PDFs, emails, and images
# MAGIC 2. **Custom LLM (CLLM)**: Domain-specific language models fine-tuned and optimized for particular tasks and datasets
# MAGIC 3. **Knowledge Assistant (KA)**: Interactive agents that provide question-answering capabilities over knowledge bases using retrieval-augmented generation. That is, KA is a single agent where tool-calling capabilities are restricted to RAG applications. 
# MAGIC 4. **Multi-Agent Supervisor (MAS)**: Coordination systems that manage and orchestrate multiple specialized agents to complete complex, multi-step tasks. For example, we can equip an MAS with a set of tools and no additional agents and have it act as a single agent with a toolkit. 
# MAGIC
# MAGIC ### Genie Agent
# MAGIC Users can create and use a Genie Agent to use natural language to query databases or other structured data, making data analysis more accessible. Genie agents can be orchestrated with an MAS or can be standalone single agents.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Operational Categories
# MAGIC
# MAGIC
# MAGIC ![automated-interactive-agents.png](../Includes/images/automated-interactive-agents.png "automated-interactive-agents.png")
# MAGIC
# MAGIC Agents are organized into two operational models based on their intended use patterns:
# MAGIC
# MAGIC - **Automated Bricks** (Information Extraction and Custom LLM): Optimized for high-scale, batch processing scenarios with minimal human intervention. These agents prioritize cost-performance optimization and throughput.
# MAGIC
# MAGIC - **Interactive Bricks** (Knowledge Assistant, Multi-Agent Supervisor, and Genie): Designed for human-in-the-loop experiences and real-time interaction scenarios. These agents focus on conversational interfaces and dynamic response generation.

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Agent Bricks Development Lifecycle
# MAGIC
# MAGIC The Agent Bricks development process follows a structured, iterative approach designed to optimize agent performance through continuous improvement and feedback incorporation. This lifecycle ensures that agents not only meet initial requirements but continue to improve through real-world usage and feedback.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Core Three-Step Development Cycle
# MAGIC
# MAGIC
# MAGIC
# MAGIC The Agent Bricks development lifecycle consists of three primary phases that form the foundation of agent development, followed by continuous iteration for ongoing improvement.
# MAGIC
# MAGIC **Step 1: Specify Your Problem**
# MAGIC ![agent-bricks-high-level-architecture.png](../Includes/images/agent-bricks-high-level-architecture.png "agent-bricks-high-level-architecture.png")
# MAGIC
# MAGIC At a high level, the user begins by building an agent that is specific to their use case. For example, with the MAS, you might want a managed agent that allows for only tool calling with a Genie Agent. After setting up proper permissions, MLflow is leveraged for tracking metrics and logging.
# MAGIC
# MAGIC In this initial phase, you define the scope and requirements of your AI agent:
# MAGIC - Clearly define the required task and expected outcomes with your team 
# MAGIC - Select the appropriate agent type from the four available options: Information Extraction, Custom LLM, Knowledge Assistant, or Multi-Agent Supervisor
# MAGIC - Depending on your use case, you next need to provide your UC-managed datasets (Delta tables, UC Volumes), equip tools, and attach other agents 
# MAGIC - Establish success criteria and quality metrics for evaluation
# MAGIC
# MAGIC **Step 2: Optimize on Your Enterprise Data**
# MAGIC
# MAGIC Agent Bricks automatically builds and optimizes the best agent system based on quality versus cost tradeoffs:
# MAGIC - The system automatically creates evaluation benchmarks related to your specific task (such as Accuracy, Product Relevance, Customer Churn prediction, etc.)
# MAGIC - Optimization involves intelligent selection and composition of multiple techniques:
# MAGIC   - Advanced prompt optimization using proven methodologies
# MAGIC   - Selective fine-tuning based on task requirements and data availability
# MAGIC   - Optimal tool selection and configuration
# MAGIC   - Implementation of Custom LLM Judges for quality assessment
# MAGIC   - Reward Model filtering for response quality improvement
# MAGIC   - Reinforcement Learning from Human Feedback (RLHF) when beneficial
# MAGIC
# MAGIC
# MAGIC ![setup-architecture-1.png](../Includes/images/setup-architecture-1.png "setup-architecture-1.png")
# MAGIC
# MAGIC
# MAGIC **Step 3: Continuous Improvement**
# MAGIC
# MAGIC The final step establishes a feedback loop for ongoing optimization:
# MAGIC - Deploy the optimized agent to production environment
# MAGIC - Continuously measure agent quality through automated and human evaluation
# MAGIC - Systematically identify issues and improvement opportunities through monitoring
# MAGIC - Apply natural language feedback to improve system performance
# MAGIC - Leverage Agent Learning on Human Feedback (ALHF) for iterative enhancement

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Evaluation and Monitoring Framework
# MAGIC
# MAGIC Agent Bricks provides comprehensive evaluation and monitoring capabilities built directly into the platform, ensuring continuous visibility into agent performance and quality metrics.
# MAGIC
# MAGIC **Automatic MLflow Integration:**
# MAGIC
# MAGIC Every agent deployed through Agent Bricks automatically includes comprehensive tracking capabilities:
# MAGIC - **Request Tracking**: Complete logging of all incoming requests with timestamps and user context
# MAGIC - **Response Monitoring**: Detailed capture of outgoing responses including confidence scores and reasoning paths
# MAGIC - **Inter-Agent Communication**: Full tracing of communication between agents in multi-agent systems
# MAGIC - **Performance Metrics**: Automatic collection of latency, throughput, and resource utilization data
# MAGIC
# MAGIC **Quality Assessment Mechanisms:**
# MAGIC
# MAGIC The platform implements multiple layers of quality evaluation:
# MAGIC - **Automatic Benchmark Creation**: Task-specific metrics tailored to your use case requirements
# MAGIC - **LLM Judge Evaluation**: Automated quality scoring using specialized language models trained for evaluation tasks
# MAGIC - **Human Feedback Integration**: Structured collection and integration of expert feedback through review applications
# MAGIC - **Production Performance Monitoring**: Real-time tracking of agent performance in live environments
# MAGIC - **Comparative Analysis**: Benchmarking against baseline models and previous agent versions

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Integration with Other Services
# MAGIC ![agent-bricks-integration.png](../Includes/images/agent-bricks-integration.png "agent-bricks-integration.png")
# MAGIC
# MAGIC Agent Bricks is tightly integrated with Mosaic AI Model Serving, Vector Search, Unity Catalog, Genie, MLflow 3, and Databricks Apps, **creating a unified platform for building, governing, evaluating, and deploying AI agents end-to-end**. This integration means users can rapidly prototype, iterate, and deploy agent systems using their own enterprise data, while maintaining best-in-class governance, security, and scalability.
# MAGIC
# MAGIC #### How Agent Bricks Works Alongside the Databricks Stack
# MAGIC
# MAGIC - **Mosaic AI Model Serving**: Agents can be deployed as scalable REST APIs with automatic load balancing and monitoring. This serving platform also provides secure authentication and natively integrates with MLflow 3, enabling real-time tracing and quality evaluation.
# MAGIC - **Vector Search**: Agents tap into Databricks Vector Search to efficiently retrieve relevant unstructured information, supporting both retrieval-augmented generation (RAG) and advanced use cases like semantic search across documents and tables.
# MAGIC - **Unity Catalog**: Ensures unified governance across all data, models, agents, and tools. Agent logic, data lineage, and tool access are controlled to meet regulatory and compliance needs, while supporting integration with enterprise security requirements.
# MAGIC - **Genie & Genie Spaces**: Enable agents to interact directly with structured data (e.g., text-to-SQL queries) and orchestrate multiple tools, expanding agent capabilities (e.g. multi-agent or tool-calling architectures).
# MAGIC - **MLflow 3**: Provides robust experiment tracking, versioning, tracing, and evaluation for agents. Real-time traces and automated quality measurement (with research-backed LLM judges) allow rapid debugging and improvement cycles.
# MAGIC - **Databricks Apps**: Offer user interfaces such as built-in chat apps, feedback collection portals, and production dashboards. These UIs allow stakeholders to interact with agents, submit feedback, and ensure agents meet business needs.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>