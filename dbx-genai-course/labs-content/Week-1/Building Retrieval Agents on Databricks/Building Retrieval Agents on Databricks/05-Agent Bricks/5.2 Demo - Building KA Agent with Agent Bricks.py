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
# MAGIC # Demo - Building a Knowledge Assistant (KA) Agent with Agent Bricks
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC In this demo, we’ll explore how to build a high-quality knowledge assistant agent using **Agent Bricks: Knowledge Assistant**. We’ll walk through creating a question-and-answer chatbot over your documents using Databricks’ declarative agent creation tool, and then improve its quality through expert feedback and labeling sessions.
# MAGIC
# MAGIC **Scenario:** The **Orion Knowledge Assistant (OKA)** empowers engineers and technicians working on the Orion A1 humanoid platform by delivering instant, context-grounded answers sourced from internal design manuals, compliance documents, and maintenance guides stored in Databricks. When a field engineer asks how to recalibrate a motion controller or verify a firmware checksum, OKA retrieves the exact procedure and references the correct section—or clearly states when the information isn't available. This approach maintains trust and accuracy in mission-critical environments.
# MAGIC
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC - **Identify** the key components and requirements for creating a knowledge assistant agent with Agent Bricks.
# MAGIC - **Configure** and create a knowledge assistant agent using Unity Catalog files as knowledge sources.
# MAGIC - **Implement** agent testing and evaluation using AI Playground, including citations and source verification.
# MAGIC - **Improve** agent quality through labeling sessions and expert feedback collection.
# MAGIC - **Apply** best practices for agent optimization and performance monitoring.
# MAGIC
# MAGIC ## Requirements
# MAGIC - A workspace with Mosaic AI Agent Bricks Preview (Beta) enabled.
# MAGIC - **Serverless Compute (environment version 4)**. Follow the instructions [here](https://docs.databricks.com/aws/en/compute/serverless/dependencies#-select-an-environment-version) to select the appropriate environment version. 
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Run the code below to install required libraries and configure your classroom environment.
# MAGIC
# MAGIC This step ensures all dependencies are available and your workspace is ready for the demo.
# MAGIC

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-05

# COMMAND ----------

# MAGIC %md
# MAGIC    
# MAGIC ## A. Creating the KA Agent
# MAGIC
# MAGIC **Agent Name:** **Orion Knowledge Assistant (OKA)**
# MAGIC
# MAGIC The documents are placed in a Unity Catalog (UC) volume. We'll create a KA agent using Agent Bricks.
# MAGIC
# MAGIC **Steps to create your agent:**
# MAGIC
# MAGIC 1. In your Databricks workspace, navigate to **Agents** in the left navigation pane
# MAGIC 1. Click **Build** in the **Knowledge Assistant** box to start creating a new KA agent
# MAGIC 1. Provide the following information:
# MAGIC    - **Name**: `Orion_Knowledge_Assistant`
# MAGIC    - **Description**: Enter a description such as:  
# MAGIC      `Orion Knowledge Assistant (OKA) helps engineers and technicians quickly find accurate answers from Orion's internal manuals, maintenance guides, and safety documents. It delivers clear, verified responses with source references, reducing search time and ensuring consistent, reliable information across teams.`
# MAGIC    - **Knowledge source type**: Select *UC Files*
# MAGIC    - **Source**: Select the Unity Catalog volume based on the catalog you used (see above for the volume name)
# MAGIC    - Click **Confirm**
# MAGIC    - **Knowledge source name**: `Company Documents`
# MAGIC    - **Content description**: Enter a content description such as:  
# MAGIC      `Contains Orion technical documentation, engineering notes, handbooks, and frequently asked questions.`
# MAGIC 1. *(Optional)* Add instructions for how the agent should respond. See example instructions below.
# MAGIC 1. Click **Create Agent** to start the creation process
# MAGIC
# MAGIC Sample instruction prompt:  
# MAGIC `You are the Orion Knowledge Assistant (OKA). Respond in a clear, professional, and factual tone appropriate for engineers and technical staff. Use only verified information from Orion's internal documents, and include source references when available. If the answer cannot be found, clearly state that and suggest related sections or next steps. Do not speculate, make assumptions, or provide information outside the provided context.`
# MAGIC
# MAGIC **⏳ Note:** It can take up to 10 minutes to create your agent and sync the knowledge sources.

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Testing Your Agent
# MAGIC
# MAGIC After your agent has finished building, you can test its functionality using the built-in chat interface. The chat area appears on the right side of the Agent Bricks interface.
# MAGIC
# MAGIC **Sample questions to test:**
# MAGIC
# MAGIC Try asking your agent these questions based on the sample documents:
# MAGIC
# MAGIC 1. "How does Orion verify compliance with ISO 13849-1?"
# MAGIC 1. "How does the Orion motion controller maintain stability during high-speed movement?"
# MAGIC 1. **"What does the red blinking light on Orion mean?"** 
# MAGIC *Note: There is no red blinking light in Orion documentation.* 
# MAGIC
# MAGIC **What to look for:**
# MAGIC - Accurate answers based on your documents
# MAGIC - Proper citations and source references
# MAGIC - Appropriate handling of questions outside the knowledge base
# MAGIC - Professional and helpful tone
# MAGIC
# MAGIC **💡 If you want the agent to provide a better answer for the last question, you will need to improve agent quality. Let's move to that next!**

# COMMAND ----------

# MAGIC %md
# MAGIC    
# MAGIC ## C. Improving Agent Quality
# MAGIC
# MAGIC Agent Bricks: Knowledge Assistant enables you to enhance your agent's quality through expert feedback and labeling sessions. These features allow you to collect natural language feedback from subject matter experts and use it to retrain and optimize your agent's performance.
# MAGIC
# MAGIC **When to use quality improvement:**
# MAGIC - When your agent provides inaccurate or incomplete responses
# MAGIC - To fine-tune the agent's tone and communication style
# MAGIC - When expanding to new knowledge domains or use cases
# MAGIC - For ongoing optimization based on user feedback
# MAGIC - To ensure consistent performance across different question types
# MAGIC
# MAGIC
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Using Labeled Data for Quality Improvement
# MAGIC
# MAGIC In this step, we will provide labeled data to improve the agent's response to the question above.
# MAGIC
# MAGIC **Quality improvement process:**
# MAGIC 1. Navigate to the **Examples** tab in your agent's interface.
# MAGIC 1. Click the **Add** button.
# MAGIC 1. Enter the question (`What does the red blinking light on Orion mean?`) and press **Add** to add the question.
# MAGIC 1. Click the question to open its details.
# MAGIC 1. Add **Guidelines** such as:
# MAGIC   
# MAGIC     >Inform the user that there isn't a blinking red light on Orion
# MAGIC
# MAGIC     >Ask the user to restart Orion by removing and reinserting the battery
# MAGIC       
# MAGIC     >Check the light color
# MAGIC       
# MAGIC     >Check the light again to see if it blinks
# MAGIC   
# MAGIC 1. Click on **Save**.
# MAGIC
# MAGIC Add evaluation questions that test different aspects of your agent's knowledge.
# MAGIC
# MAGIC **Test the Agent:**
# MAGIC 1. Return to the agent and ask the same question to **verify if the response has improved**. You can also change your question to **ask about another color to see how the answer adapts**. 

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Using Expert Review for Quality Improvement
# MAGIC
# MAGIC **Labeling sessions and expert review:**
# MAGIC
# MAGIC The labeling session feature allows experts to:
# MAGIC - Review agent responses to evaluation questions
# MAGIC - Provide natural language feedback on response quality
# MAGIC - Add guidelines and expectations for agent behavior
# MAGIC - Evaluate responses for accuracy, completeness, and tone
# MAGIC
# MAGIC For step-by-step instructions on the expert review process, see the [Agent Bricks: Knowledge Assistant documentation – Step 3: Improve quality](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/knowledge-assistant#step-3-improve-quality).
# MAGIC
# MAGIC **Best Practice:** Quality improvement is an iterative process. Plan for multiple rounds of feedback collection and refinement to achieve optimal agent performance.
# MAGIC
# MAGIC **💡 Question:** How are guidelines used for quality improvement? What do you observe in agent traces regarding this?

# COMMAND ----------

# MAGIC %md
# MAGIC    
# MAGIC ## D. Cleanup Resources
# MAGIC
# MAGIC After completing this demo, it's important to clean up the resources you created to avoid incurring unnecessary costs. **The KA agent creates a vector search endpoint and a serving endpoint in the background** to enable semantic search over your documents. These endpoints will continue to incur charges even when not actively in use.
# MAGIC
# MAGIC **To delete your agent:**
# MAGIC 1. Navigate to **Agents** in the left navigation pane
# MAGIC 1. Locate your **Orion_Knowledge_Assistant** agent
# MAGIC 1. Click on the agent to open its details
# MAGIC 1. Select **Delete** from the agent options menu (top right)
# MAGIC 1. Confirm the deletion when prompted
# MAGIC
# MAGIC Deleting the agent will also remove the associated vector search endpoint and serving endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC    
# MAGIC ## Summary
# MAGIC
# MAGIC You have successfully built and improved a KA agent using Agent Bricks: Knowledge Assistant. Here's a concise recap of what we accomplished:
# MAGIC
# MAGIC **What We Built:**
# MAGIC - Created a KA agent using the declarative Agent Bricks interface
# MAGIC - Configured the agent with Unity Catalog files as knowledge sources
# MAGIC - Tested the agent using the built-in chat interface
# MAGIC - Enhanced agent quality through expert feedback and labeling sessions
# MAGIC
# MAGIC **Next Steps (Optional):**
# MAGIC
# MAGIC Now that your KA agent is working, consider these next steps:
# MAGIC
# MAGIC 1. **Expand knowledge sources**: Add additional document types and data sources to broaden your agent's coverage
# MAGIC 1. **Quality optimization**: Use labeling sessions and expert review to continuously improve agent performance
# MAGIC 1. **Production deployment**: Deploy your agent in a production environment with proper governance and monitoring
# MAGIC
# MAGIC **Additional Resources:**
# MAGIC - [Agent Bricks Documentation](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/knowledge-assistant)
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>