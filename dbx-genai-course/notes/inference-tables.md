# Inference Tables

## What Are Inference Tables?

**Inference Tables** are a Databricks-native capability used to automatically capture and store inference data.

They can log information such as:

* Request payloads
* Model responses
* Endpoint inference traffic
* Inputs and outputs from production model calls

In simple terms:

> Inference Tables help you observe what is being sent to a model and what the model is returning.

They make it easier to analyze, audit, monitor, and troubleshoot production model behavior without building a custom logging solution.

---

# 1. Why Inference Tables Matter

In production GenAI and RAG applications, it is important to understand how the model is behaving.

Inference Tables help answer questions like:

* What requests are users sending?
* What responses is the model returning?
* Are there bad or low-quality responses?
* Are users asking unexpected questions?
* Is the model hallucinating?
* Is the RAG application retrieving and responding correctly?
* Are there performance or quality issues over time?

---

# 2. Example Exam Question

## Question Recap

A Generative AI Engineer is managing a provisioned throughput endpoint for a RAG-based application.

They want to automatically observe and analyze all inference traffic, including:

* Request payloads
* Model responses

They do not want to create a custom logging microservice.

## Choices

* Inference Tables
* MLflow Model Registry
* Unity Catalog Audit Logs

## Correct Answer

> **Inference Tables**

---

# 3. Why Inference Tables Are Correct

Inference Tables are specifically designed to automatically log inference data into structured Databricks tables.

They are useful because they:

* Capture inference requests.
* Capture model responses.
* Store inference traffic in structured tables.
* Enable analysis and auditing.
* Help monitor production model behavior.
* Avoid the need for custom logging infrastructure.

For this question, the key phrase is:

> Automatically observe and analyze all inference traffic without building a custom logging microservice.

That points directly to:

> **Inference Tables**

---

# 4. Why the Other Options Are Incorrect

## MLflow Model Registry

MLflow Model Registry is used to manage the model lifecycle.

It helps with:

* Model versions
* Model metadata
* Model registration
* Deployment lifecycle
* Stage transitions
* Model governance

It is **not** mainly used to automatically capture real-time inference request and response payloads.

### Exam Shortcut

> MLflow Model Registry = model version and lifecycle management, not inference traffic logging.

---

## Unity Catalog Audit Logs

Unity Catalog Audit Logs are used for governance and access auditing.

They help track things like:

* Who accessed data
* What table was queried
* What permissions were used
* API or catalog-level activity
* Governance-related events

They are **not** designed to capture full model inference request and response payloads.

### Exam Shortcut

> Unity Catalog Audit Logs = access and governance auditing, not model request/response logging.

---

# 5. Comparison Table

| Option                   | Main Purpose                   | Good For                                       | Not Best For                             |
| ------------------------ | ------------------------------ | ---------------------------------------------- | ---------------------------------------- |
| Inference Tables         | Log inference traffic          | Capturing request payloads and model responses | Model version management                 |
| MLflow Model Registry    | Manage model lifecycle         | Model versions, metadata, deployment stages    | Logging every inference request/response |
| Unity Catalog Audit Logs | Governance and access auditing | Tracking data access and permissions           | Capturing model payloads and responses   |

---

# 6. Common Exam Keywords

| If the question says...        | Think...                 |
| ------------------------------ | ------------------------ |
| Capture request payloads       | Inference Tables         |
| Capture model responses        | Inference Tables         |
| Observe inference traffic      | Inference Tables         |
| Analyze production model calls | Inference Tables         |
| No custom logging microservice | Inference Tables         |
| Manage model versions          | MLflow Model Registry    |
| Track data access              | Unity Catalog Audit Logs |
| Governance auditing            | Unity Catalog Audit Logs |

---

# 7. Common Exam Trap

## Trap: Audit Logs vs Inference Tables

Both sound like logging, but they log different things.

| Logging Type             | What It Logs                      |
| ------------------------ | --------------------------------- |
| Inference Tables         | Model inputs and outputs          |
| Unity Catalog Audit Logs | Data access and governance events |

So if the question asks about:

> Request payloads and model responses

Choose:

> **Inference Tables**

If the question asks about:

> Who accessed which table or data asset

Choose:

> **Unity Catalog Audit Logs**

---

# 8. Final Summary

Inference Tables provide an automated, integrated Databricks solution to capture, store, and analyze inference traffic.

They are ideal for monitoring RAG endpoint behavior because they capture:

* Requests
* Responses
* Production inference activity

The key exam idea is:

> Use **Inference Tables** when you need automatic logging of model inference inputs and outputs without building custom logging infrastructure.
