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
# MAGIC # Lab - Building a Single Agent with Agent Bricks: Supervisor Agent
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC Agent Bricks Supervisor Agent creates a coordinated multi-agent system that orchestrates AI agents and tools to work together on complex tasks. This system can coordinate Genie Spaces, agent endpoints, Unity Catalog functions, and MCP servers to deliver comprehensive solutions across specialized domains.
# MAGIC
# MAGIC The supervisor system uses advanced AI orchestration patterns to manage agent interactions, task delegation, and result synthesis. You can improve coordination quality over time with natural language feedback from subject matter experts.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC _By the end of this lab, you will be able to:_
# MAGIC
# MAGIC - Configure and deploy a supervisor agent system using Agent Bricks
# MAGIC - Integrate Unity Catalog functions as tools within the supervisor framework
# MAGIC - Test supervisor coordination capabilities through AI Playground
# MAGIC - Implement feedback mechanisms to improve agent performance over time
# MAGIC - Clean up deployed Agent Bricks resources

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Classroom Setup
# MAGIC
# MAGIC Run the following cell to configure your working environment for this notebook. Some preview features may have been turned on for this demonstration. You can read more about enabling preview features [here](https://docs.databricks.com/aws/en/release-notes/release-types).

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
# MAGIC As part of the workspace setup, several Python libraries have been installed. To see the list of notebook-scoped libraries, please read [this documentation](https://docs.databricks.com/aws/en/compute/serverless/dependencies#configure-environment-for-job-tasks).

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-4.1

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Inspecting AI Agent Tools
# MAGIC
# MAGIC As a part of the classroom setup, UC functions have already been configured with the proper permissions. Navigate to the Catalog Explorer and search for `avg_neigh_price` and `airbnb_posting_info`. Inspect the tools and read their descriptions before moving to the next section.

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Configuring the Supervisor Agent
# MAGIC
# MAGIC Now that you have Unity Catalog functions ready, you can create and configure the supervisor agent system.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C1. Access Agent Bricks Interface
# MAGIC
# MAGIC 1. Navigate to **Agents** in the left navigation pane of your workspace
# MAGIC 2. From the **Supervisor Agent** tile, click **Build**
# MAGIC 3. You'll be directed to the configuration interface

# COMMAND ----------

# MAGIC %md
# MAGIC ### C2. Configure Supervisor Settings
# MAGIC
# MAGIC On the **Configure** tab, set up your supervisor with the following information:
# MAGIC
# MAGIC - **Name**: Name your agent your lab username + MAS_single_agent. For example, `labuser_123_abc_MAS_single_agent`
# MAGIC - **Description**: Copy and paste the following description: _This is an agent that uses tool calling to answer questions about the Airbnb sample dataset._

# COMMAND ----------

# MAGIC %md
# MAGIC ### C3. Add Unity Catalog Functions as Tools
# MAGIC
# MAGIC Under **Configure Agents**, add your Unity Catalog functions:
# MAGIC
# MAGIC 1. Click **+ Add** to add a new agent/tool
# MAGIC 1. In the **Type** field, select **Unity Catalog Function**
# MAGIC 1. Select the following functions from the **Unity Catalog Function** drop-down menu (you can use the search box)
# MAGIC    - `avg_neigh_price`
# MAGIC 1. Click **Confirm** and repeat the same instructions to add the UC function `airbnb_posting_info`
# MAGIC 1. Provide an **Agent Name** for this tool or you can use the automatically generated Agent Name provided after selecting the tool.
# MAGIC 1. Typically, under **Describe the content**, you should provide a detailed description of what this function does and when it should be used. However, because we have already pre-configured our function with a description, that has been brought in from UC.
# MAGIC
# MAGIC **NOTE:** You can add up to 10 agents/tools to a single supervisor system.

# COMMAND ----------

# MAGIC %md
# MAGIC ### C4. Complete Supervisor Creation
# MAGIC
# MAGIC After configuring all settings and adding your tools:
# MAGIC
# MAGIC 1. Review your configuration for accuracy
# MAGIC 2. Click **Create Agent**
# MAGIC 3. Wait for the system to build your supervisor agent (this will take a few minutes)

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Testing and Validation
# MAGIC
# MAGIC Once your supervisor is built, we are ready to test it either in the Agent Bricks menu or open the agent in AI Playground (see screenshot). Let's use the AI Playground.
# MAGIC
# MAGIC ![mas-creation.png](../Includes/images/mas-creation.png "mas-creation.png")

# COMMAND ----------

# MAGIC %md
# MAGIC ### D1. AI Playground Test
# MAGIC After clicking on **Open in Playground**, you will see the following button that to **Review Capabilities**: 
# MAGIC ![review-capabilities.png](../Includes/images/review-capabilities.png)
# MAGIC and next click **Authorize** on the **Permission Requested** screen. 
# MAGIC ![permission-requested.png](../Includes/images/permission-requested.png)
# MAGIC pass the following query to test the agent used the appropriate tools:
# MAGIC - _What is the average price in Mission, and what are the details for listing 958?_
# MAGIC
# MAGIC **Note:** You may need to wait 4-5 minutes for the endpoint to be ready to pass your query. 

# COMMAND ----------

# MAGIC %md
# MAGIC ![mas-ai-playground-results.png](../Includes/images/mas-ai-playground-results.png "mas-ai-playground-results.png")

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. (Optional) Implementing Feedback and Improvement
# MAGIC
# MAGIC Agent Bricks Supervisor Agent can improve coordination quality based on natural language feedback from subject matter experts.

# COMMAND ----------

# MAGIC %md
# MAGIC ### E1. Create Labeling Sessions
# MAGIC _It usually takes approximately 15 minutes for the agent to be ready for a SME session starting from the moment its endpoint has been created._
# MAGIC
# MAGIC To gather feedback for supervisor improvement:
# MAGIC
# MAGIC 1. Navigate to the **Examples** tab back in your Agent's configuration menu
# MAGIC 2. Click **+ Add** to add task scenarios for evaluation
# MAGIC 3. Enter questions or tasks that test supervisor coordination, e.g. _What is the average price for Upper Market?_
# MAGIC 4. Click **Add**

# COMMAND ----------

# MAGIC %md
# MAGIC ### E2. Mock Expert Feedback
# MAGIC
# MAGIC Set up a labeling session for subject matter experts:
# MAGIC
# MAGIC 1. After clicking on the question, you will see  **Input** and **Guidlines**. Click on **Guidelines**.
# MAGIC 2. Add in the guideline: _Upper Market is also called "Castro/Upper Market" so you should use that in your query._
# MAGIC 3. Click **Save**

# COMMAND ----------

# MAGIC %md
# MAGIC ### E3. Apply Feedback and Retrain
# MAGIC
# MAGIC After experts complete their reviews:
# MAGIC
# MAGIC 1. Return to the **Build** tab
# MAGIC 2. Test the supervisor again to validate improvements with the same question that you passed earlier: _What is the average price for Upper Market?_

# COMMAND ----------

# MAGIC %md
# MAGIC ## F. Clean Up
# MAGIC Please clean up your resources deployed during the setup of your MAS.
# MAGIC 1. Navigate to **Agents** and select the agent you deployed earlier.
# MAGIC 1. Select the three vertical dots at the top right and click delete (see screenshot). You will receive a message that details the deletion cannot be undone. Click **Delete** once more.
# MAGIC
# MAGIC ![delete-mas.png](../Includes/images/delete-mas.png "delete-mas.png")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this lab, you successfully built and deployed a supervisor agent system using Agent Bricks, integrating Unity Catalog functions as specialized tools for querying Airbnb data. You tested the supervisor's coordination capabilities through AI Playground and explored how to implement feedback mechanisms to improve agent performance over time. Finally, you learned proper resource cleanup procedures to maintain a clean workspace environment.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>