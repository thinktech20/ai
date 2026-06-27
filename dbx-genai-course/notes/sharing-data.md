# Securely Sharing Data Between Databricks Production and Development Workspaces

## Summary

To securely share data between Databricks production and development workspaces, especially when using **Unity Catalog**, the goal is to provide development teams access to the data they need without exposing sensitive production data unnecessarily.

The main strategies are:

1. Use **Delta Sharing** for secure, governed sharing.
2. Replicate data with masking or sanitization.
3. Use a centralized data lake with governance controls.
4. Automate access policies and refresh processes.

---

# 1. Use Delta Sharing for Secure Data Sharing

## What It Does

**Delta Sharing** enables secure and governed sharing of live data across workspaces, organizations, or external partners.

It allows data to be shared without copying or duplicating the underlying data.

## How It Works

You can set up a Delta Share provider in the production environment and grant specific access to users or groups in the development workspace.

## Benefits

* Secure data sharing
* Governed access
* No unnecessary data duplication
* Access to live or near-live data
* Works well with Unity Catalog governance

## Best Use Case

Use **Delta Sharing** when:

* Development users need access to shared production data.
* Data should not be copied manually.
* Governance and access control are important.
* Live or current data is needed.

## Exam Shortcut

> Use **Delta Sharing** when the question asks for secure, governed data sharing across Databricks workspaces or external recipients.

---

# 2. Replicate Data with Controlled Access

## What It Does

Another option is to create a replicated version of the production dataset in a dedicated development environment.

This copy should usually be:

* Masked
* Sanitized
* Filtered
* Reduced in scope
* Refreshed on a schedule

## Benefits

* Reduces risk of exposing sensitive production data
* Allows developers to test safely
* Keeps production isolated from development
* Supports realistic development workflows

## Best Use Case

Use replicated data when:

* Developers do not need direct access to live production data.
* Sensitive fields should be masked.
* A stable test dataset is enough.
* Development workloads should not impact production systems.

## Exam Shortcut

> For internal development, use a masked or sanitized copy of production data when live access is not required.

---

# 3. Use a Centralized Data Lake and Governance Layer

## What It Does

Core datasets can be stored in a centralized data lake, such as:

* S3
* ADLS
* GCS

Access can then be managed through governance controls, Unity Catalog, or secure views.

## How It Works

Each workspace can connect to governed datasets or views rather than maintaining separate unmanaged copies.

## Benefits

* Centralized data management
* Consistent governance
* Easier access control
* Reduced duplication
* Better lineage and auditing

## Best Use Case

Use a centralized governance layer when:

* Multiple workspaces need access to the same data.
* Access should be controlled consistently.
* Data should remain in one governed location.
* Unity Catalog is used to manage permissions.

## Exam Shortcut

> Use Unity Catalog and governed views to enforce fine-grained access controls across workspaces.

---

# 4. Automate Policy Enforcement and Data Refresh

## What It Does

Automate the process of maintaining:

* Access controls
* Masking rules
* Dataset refreshes
* Environment setup
* Permission consistency

## Tools and Approaches

You can use:

* Infrastructure as Code
* Databricks workflows
* Jobs
* Unity Catalog permissions
* CI/CD pipelines
* Automated refresh pipelines

## Benefits

* Reduces manual errors
* Keeps environments consistent
* Makes governance repeatable
* Helps ensure development data stays up to date
* Supports auditability

## Best Use Case

Use automation when:

* Multiple environments must stay aligned.
* Data refreshes happen regularly.
* Access policies must be consistently enforced.
* Governance rules should not rely on manual setup.

## Exam Shortcut

> Automate data refresh and access policy enforcement to keep production and development environments consistent and secure.

---

# 5. Comparison Table

| Strategy                           | Best For                                   | Main Benefit                               | Tradeoff                          |
| ---------------------------------- | ------------------------------------------ | ------------------------------------------ | --------------------------------- |
| Delta Sharing                      | Secure cross-workspace or external sharing | Governed live data sharing without copying | Requires setup and permissions    |
| Replicated masked data             | Internal development and testing           | Reduces production data exposure           | Data may not be fully current     |
| Centralized data lake + governance | Shared enterprise data access              | Consistent access control and governance   | Requires strong governance design |
| Automation                         | Repeatable setup and refresh               | Consistency and reduced manual errors      | Requires upfront implementation   |

---

# 6. Common Exam Keywords

| If the question says...                         | Think...                   |
| ----------------------------------------------- | -------------------------- |
| Securely share live data                        | Delta Sharing              |
| Share data across workspaces                    | Delta Sharing              |
| Avoid copying data                              | Delta Sharing              |
| Development access to sensitive production data | Masked/sanitized replica   |
| Fine-grained permissions                        | Unity Catalog              |
| Consistent access policies                      | Unity Catalog + automation |
| Refresh dev data safely                         | Controlled replication     |
| External data sharing                           | Delta Sharing              |

---

# 7. Common Exam Traps

## Trap 1: Do Not Give Direct Production Access by Default

Development users usually should not get broad direct access to production data.

Safer options include:

* Delta Sharing with limited permissions
* Masked views
* Sanitized replicas
* Row-level or column-level access controls

---

## Trap 2: Copying Data Is Not Always Best

Copying production data into development can create security and governance risks.

If live, governed access is needed, Delta Sharing may be better.

---

## Trap 3: Unity Catalog Is for Governance, Not Data Movement

Unity Catalog helps manage:

* Permissions
* Access controls
* Lineage
* Governance
* Data discovery

It does not automatically solve every sharing or replication requirement by itself.

---

## Trap 4: Masking Matters for Development

If development users do not need sensitive production values, use:

* Masked columns
* Sanitized datasets
* Filtered views
* Synthetic or sampled data

---

# 8. Final Summary

To securely share data between Databricks production and development workspaces:

* Use **Delta Sharing** when secure, governed, live sharing is needed.
* Use **masked or sanitized replicas** for safer development access.
* Use **Unity Catalog** to enforce fine-grained access controls.
* Use **automation** to keep policies and data refreshes consistent.

The key exam idea is:

> Secure data sharing should minimize unnecessary data copying, enforce governance, and expose only the data each environment or user needs.
