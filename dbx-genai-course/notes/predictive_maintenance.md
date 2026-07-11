# Predictive Maintenance Write-Up: FSR RAG + Current Condition Signals + PyFunc Serving

## 1. Big Idea

A Field Service Report (FSR) RAG pipeline by itself is **not automatically predictive maintenance**.

A basic FSR RAG system answers questions such as:

```text
What happened before?
What repairs were performed?
What failure modes were seen historically?
What did the report say?
```

That is best described as:

```text
Historical engineering intelligence
```

It becomes connected to **predictive maintenance** when historical FSR evidence is combined with current asset condition signals, rule-based logic, or an ML risk model to estimate future risk.

A strong framing is:

```text
The FSR RAG pipeline is a historical engineering intelligence layer that supports predictive maintenance by surfacing prior failures, symptoms, root causes, corrective actions, and similar asset histories from unstructured field service reports.
```

If current operational signals and risk scoring are added, then it becomes closer to a predictive maintenance workflow:

```text
The workflow combines current asset condition signals, historical FSR retrieval, and rule-based or ML risk scoring to identify components at elevated failure risk.
```

---

## 2. Historical RAG vs Predictive Maintenance

### Historical FSR RAG

Historical RAG answers:

```text
What happened before?
What repairs were done?
What symptoms were reported?
What root causes were documented?
What similar incidents exist?
```

Example questions:

```text
What repairs were performed on GT-123?
```

```text
Which FSRs mention compressor blade cracking?
```

```text
What root cause was documented for the 2021 outage?
```

This is useful, but it is not directly predicting future failure.

### Predictive Maintenance

Predictive maintenance answers:

```text
What is likely to fail?
When might it fail?
What components are at elevated risk?
What warning signs indicate future failure?
What maintenance action should be considered before failure occurs?
```

Example predictive-maintenance-style question:

```text
Given GT-123’s past FSR history, inspection findings, operating hours, and recent vibration readings, what components are at elevated risk of failure in the next outage cycle?
```

This question requires more than historical document retrieval. It needs current asset signals and risk logic.

---

## 3. Correct Architecture

The current condition signals do **not simply flow into the historical FSR RAG system**.

A better implementation view is:

```text
Current condition signals
        +
Historical FSR evidence
        +
Rules / ML risk logic
        ↓
MLflow PyFunc predict()
        ↓
Risk assessment / recommendation / cited explanation
```

### Diagram

```text
                             ┌──────────────────────────┐
                             │ Current Condition Signals │
                             │ vibration, temp, hours    │
                             └─────────────┬────────────┘
                                           │
                                           │
┌──────────────────────┐                   │
│ Historical FSR RAG    │                   │
│ similar incidents,    │                   │
│ prior repairs, causes │                   │
└──────────┬───────────┘                   │
           │                               │
           │                               │
           ▼                               ▼
        ┌──────────────────────────────────────┐
        │ MLflow PyFunc predict()               │
        │ - retrieve evidence                   │
        │ - apply rules / ML score              │
        │ - build final prompt                  │
        │ - call LLM                            │
        │ - return structured answer            │
        └──────────────────────────────────────┘
                         ▲
                         │
        ┌────────────────┴───────────────┐
        │ Rules / ML Risk Logic           │
        │ thresholds, risk scores, model  │
        └────────────────────────────────┘
```

---

## 4. What Goes Into the PyFunc `predict()` Method?

An MLflow PyFunc model exposes a standard method:

```python
def predict(self, context, model_input):
    ...
```

The name `predict()` does not automatically mean the method is doing predictive maintenance. It simply means:

```text
When input comes in, run this function and return an output.
```

The method becomes predictive only if the logic inside it combines:

```text
historical FSR retrieval
+ current asset condition signals
+ rules or ML risk scoring
+ LLM explanation / formatting
```

### Conceptual flow inside `predict()`

```text
Input request
- asset_id
- question
- current condition signals
- optional filters

        ↓

PyFunc predict()

        ↓

Inside predict():

1. Use asset_id / symptoms / equipment type to retrieve historical FSR chunks
2. Read current condition signals
3. Apply rules or ML risk scoring
4. Combine risk score + retrieved evidence
5. Generate final explanation with citations
6. Return structured output
```

---

## 5. Example Input to `predict()`

A predictive-maintenance-style endpoint should receive more than a plain question.

Example input:

```json
{
  "asset_id": "GT-123",
  "question": "What components are at elevated risk in the next outage cycle?",
  "equipment_type": "gas_turbine",
  "current_condition_signals": {
    "vibration_trend": "increasing",
    "latest_vibration": 4.2,
    "bearing_temperature_trend": "stable",
    "operating_hours": 58200,
    "starts_last_12_months": 47
  },
  "filters": {
    "start_year": 2018,
    "end_year": 2024
  },
  "top_k": 5
}
```

---

## 6. Where Do Current Condition Signals Come From?

Signals like this:

```text
IF vibration trend is increasing
```

usually do **not** come from FSR PDFs alone.

They usually come from structured operational systems such as:

```text
1. Sensor / telemetry systems
   - vibration sensors
   - bearing temperature sensors
   - exhaust temperature sensors
   - pressure sensors
   - speed/load sensors

2. Historian systems
   - OSIsoft PI / AVEVA PI
   - GE historian platforms
   - SCADA data stores
   - plant operational databases

3. Maintenance / inspection systems
   - inspection findings
   - work orders
   - condition monitoring reports
   - outage reports

4. Asset management systems
   - equipment master data
   - operating hours
   - starts/stops
   - maintenance history
   - component replacement history
```

Example raw vibration readings:

```text
Date        Vibration mm/s
Jan 1       2.1
Feb 1       2.4
Mar 1       2.9
Apr 1       3.6
May 1       4.2
```

A feature engineering step could convert those readings into:

```json
{
  "vibration_trend": "increasing",
  "vibration_slope": 0.52,
  "latest_vibration": 4.2,
  "threshold_status": "warning"
}
```



---

## 6.1 Can Current Condition Signals Come Through Feature Serving?

Yes. Current condition signals can come through **Feature Serving**.

This is a clean Databricks-native pattern when the predictive-maintenance workflow needs structured, low-latency asset features at inference time.

Instead of requiring the client to pass every signal manually, the client can pass an `asset_id`, and the PyFunc `predict()` method can fetch the latest engineered features through Feature Serving or an Online Feature Store.

### Feature Serving Role

```text
Feature Serving
= serves structured feature values at inference time
```

Examples of features for a predictive-maintenance workflow:

```text
- asset_id
- equipment_type
- operating_hours
- starts_last_12_months
- latest_vibration
- vibration_trend
- vibration_slope
- bearing_temperature_trend
- exhaust_temperature_spread
- last_inspection_date
- days_since_last_outage
- component_replacement_count
- prior_failure_count
- maintenance_frequency
```

These are different from FSR chunks. They are structured signals computed from operational systems, historian data, inspection systems, or maintenance systems.

### Updated Architecture With Feature Serving

```text
                         ┌────────────────────────────┐
                         │ Sensor / Historian Systems  │
                         │ vibration, temp, load, etc. │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────┐
                         │ Feature Engineering         │
                         │ compute trends/slope/stats  │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────┐
                         │ Feature Store / Online Store│
                         │ current condition features  │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
┌──────────────────────┐        ┌──────────────────────┐
│ Historical FSR RAG    │        │ Feature Serving       │
│ Vector Search chunks  │        │ latest asset features │
└──────────┬───────────┘        └──────────┬───────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
              ┌─────────────────────────┐
              │ MLflow PyFunc predict()  │
              │ - fetch features         │
              │ - retrieve FSR evidence  │
              │ - apply rules / ML score │
              │ - build final response   │
              └─────────────────────────┘
                           ▼
              Predictive maintenance assessment
```

### Two Implementation Options

#### Option 1: Client Sends Current Signals Directly

The client sends the asset ID plus the current condition signals.

```json
{
  "asset_id": "GT-123",
  "question": "What components are at elevated risk?",
  "current_condition_signals": {
    "vibration_trend": "increasing",
    "latest_vibration": 4.2,
    "operating_hours": 58200,
    "bearing_temperature_trend": "stable"
  }
}
```

This is simple, but it requires the calling application to already know and supply the correct features.

#### Option 2: PyFunc Looks Up Features Through Feature Serving

The client sends only the asset ID and question.

```json
{
  "asset_id": "GT-123",
  "question": "What components are at elevated risk in the next outage cycle?"
}
```

Inside `predict()`:

```text
asset_id → Feature Serving → current condition features
```

Then `predict()` combines:

```text
current condition features
+ historical FSR evidence
+ rules / ML risk logic
+ LLM explanation
```

This is cleaner because the served workflow owns the feature lookup and can consistently use the latest approved feature definitions.

### PyFunc Sketch With Feature Serving

```python
class PredictiveMaintenanceRAGModel(mlflow.pyfunc.PythonModel):

    def predict(self, context, model_input):
        asset_id = model_input["asset_id"][0]
        question = model_input["question"][0]

        # 1. Fetch structured current condition features
        current_signals = feature_serving_lookup(
            entity_key={"asset_id": asset_id},
            features=[
                "equipment_type",
                "operating_hours",
                "latest_vibration",
                "vibration_trend",
                "bearing_temperature_trend",
                "starts_last_12_months"
            ]
        )

        # 2. Retrieve historical FSR evidence from Vector Search
        fsr_chunks = vector_search(
            query=build_query(question, current_signals),
            filters={
                "asset_id": asset_id,
                "equipment_type": current_signals["equipment_type"]
            },
            top_k=5
        )

        # 3. Apply risk scoring logic
        risk_scores = apply_rules_or_ml_model(
            current_signals=current_signals,
            historical_evidence=fsr_chunks
        )

        # 4. Derive grounded recommended actions
        recommended_actions = derive_recommended_actions(
            risk_scores=risk_scores,
            current_signals=current_signals,
            historical_evidence=fsr_chunks
        )

        # 5. Use LLM to explain and format, not invent unsupported actions
        explanation = call_llm_for_grounded_explanation(
            question=question,
            current_signals=current_signals,
            risk_scores=risk_scores,
            recommended_actions=recommended_actions,
            evidence=fsr_chunks
        )

        return {
            "asset_id": asset_id,
            "current_signals": current_signals,
            "risk_scores": risk_scores,
            "recommended_actions": recommended_actions,
            "explanation": explanation,
            "sources": extract_sources(fsr_chunks)
        }
```

### Important Distinction

```text
Feature Serving
→ structured current asset signals
→ operating hours, vibration trend, temperature trend, starts/stops

Vector Search / FSR RAG
→ unstructured historical evidence
→ similar incidents, repair notes, root causes, prior inspection findings

MLflow PyFunc predict()
→ orchestrates feature lookup + retrieval + risk scoring + LLM explanation
```

### Exam / Interview Shortcut

```text
Current structured signals at inference time
→ Feature Serving / Online Feature Store

Historical unstructured document evidence
→ Vector Search / RAG

Deployable custom workflow
→ MLflow PyFunc + Model Serving
```


---

## 7. What Are Rules / ML Models?

In this context, **rules** or **ML models** are the parts of the workflow that estimate risk.

```text
RAG = finds historical evidence from documents
Rules / ML model = estimates risk from structured and historical signals
LLM = explains and formats the result
```

### 7.1 Rule-Based Logic

A rule is human-defined logic, usually created with SMEs or engineering experts.

Example rule:

```text
IF vibration_trend = increasing
AND operating_hours > 50,000
AND prior FSRs mention compressor blade wear
THEN compressor blade risk = high
```

Example pseudo-code:

```python
def score_compressor_blade_risk(operating_hours, vibration_trend, prior_blade_wear):
    risk = "low"

    if operating_hours > 50000:
        risk = "medium"

    if vibration_trend == "increasing" and prior_blade_wear:
        risk = "high"

    return risk
```

Rule-based scoring is useful when:

```text
- there is limited labeled failure data
- SMEs know the risk patterns
- explainability is important
- the system needs deterministic behavior
```

### 7.2 ML Risk Model

An ML model learns from historical examples.

It might use features such as:

```text
- operating hours
- starts/stops
- vibration trends
- temperature trends
- inspection findings
- maintenance history
- component replacement history
- prior failure / no-failure outcomes
```

Example output from an ML model:

```json
{
  "asset_id": "GT-123",
  "component": "compressor_blades",
  "failure_probability_next_90_days": 0.72,
  "risk_level": "high"
}
```

This is more predictive than simple RAG because it estimates future failure probability.

---

## 8. How Historical FSR RAG Supports Predictive Maintenance

Historical FSR RAG can retrieve:

```text
- similar past incidents
- symptoms that preceded failures
- root causes
- corrective actions
- inspection findings
- recurring component issues
- prior maintenance actions
```

Example RAG-supported predictive question:

```text
Based on historical FSRs, what early warning signs preceded compressor blade cracking in similar units?
```

Another example:

```text
Which prior incidents look similar to the current vibration pattern on GT-123, and what failures followed?
```

This does not replace a risk model, but it provides explainable historical evidence.

---

## 9. How Are `recommended_actions` Derived?

The safest design principle is:

```text
recommended_actions should not be invented by the LLM.
They should come from rules, historical FSR evidence, maintenance playbooks, SME logic, or a trained model.
```

The LLM should mostly:

```text
- summarize
- explain
- format
- cite evidence
- rank actions
```

It should not be the only source of maintenance recommendations.

### 9.1 Rule-Based Recommended Actions

Example rule:

```text
IF vibration_trend = increasing
AND component_risk = compressor_blades
AND prior FSR evidence mentions blade wear/cracking
THEN recommend targeted compressor blade inspection.
```

Example pseudo-code:

```python
def derive_recommended_actions(risk_factors):
    actions = []

    if (
        risk_factors["component"] == "compressor_blades"
        and risk_factors["vibration_trend"] == "increasing"
        and risk_factors["prior_blade_wear"] == True
    ):
        actions.append("Perform targeted compressor blade inspection during the next outage.")
        actions.append("Review vibration spectrum data for compressor-related frequencies.")

    if (
        risk_factors["component"] == "bearings"
        and risk_factors["bearing_temperature_trend"] == "increasing"
    ):
        actions.append("Inspect bearing lubrication and review bearing temperature history.")

    return actions
```

### 9.2 FSR Evidence-Based Recommended Actions

The system can retrieve similar historical cases and inspect what actions were taken before.

Example:

```text
Current issue:
GT-123 has increasing vibration.

Retrieved similar FSRs:
- FSR A: similar vibration issue → action taken: borescope inspection
- FSR B: vibration anomaly → action taken: bearing alignment check
- FSR C: compressor finding → action taken: blade inspection
```

Then the system can return:

```json
{
  "recommended_actions": [
    {
      "action": "Perform borescope inspection.",
      "basis": "This action appeared in similar historical FSRs involving vibration anomalies."
    },
    {
      "action": "Check bearing alignment.",
      "basis": "Similar prior cases included bearing alignment checks."
    }
  ]
}
```

### 9.3 Maintenance Playbook / TIL / SOP-Based Actions

In production, the safest recommendations should come from approved guidance such as:

```text
- maintenance playbooks
- TIL documents
- service bulletins
- inspection procedures
- engineering SOPs
- OEM recommendations
```

Example:

```json
{
  "recommended_actions": [
    {
      "action": "Perform compressor borescope inspection.",
      "source_type": "maintenance_playbook",
      "source_id": "GT_COMP_INSPECTION_SOP",
      "confidence": "high"
    }
  ]
}
```

---

## 10. Example Predictive Maintenance Output

A good output should be structured and evidence-grounded.

```json
{
  "asset_id": "GT-123",
  "risk_summary": "GT-123 shows elevated compressor-related risk based on increasing vibration, high operating hours, and similar historical FSR cases.",
  "components_at_risk": [
    {
      "component": "compressor blades",
      "risk_level": "high",
      "risk_method": "rules_plus_rag_evidence",
      "reason": "The current vibration trend is increasing, operating hours are above the configured threshold, and retrieved FSRs show similar cases where compressor blade wear or cracking followed vibration anomalies.",
      "supporting_evidence": [
        {
          "document_id": "FSR_2021_GT123",
          "page": 12,
          "finding": "Prior inspection noted compressor blade wear."
        },
        {
          "document_id": "FSR_2019_SIMILAR_UNIT_77",
          "page": 9,
          "finding": "Similar vibration pattern was associated with compressor blade cracking."
        }
      ]
    },
    {
      "component": "bearings",
      "risk_level": "medium",
      "risk_method": "rules_plus_condition_signals",
      "reason": "Bearing temperature is currently stable, but vibration trend may warrant inspection during the next outage.",
      "supporting_evidence": [
        {
          "document_id": "FSR_2020_GT123",
          "page": 6,
          "finding": "Prior report recommended bearing vibration monitoring."
        }
      ]
    }
  ],
  "recommended_actions": [
    {
      "action": "Perform targeted compressor blade inspection during the next outage.",
      "priority": "high",
      "derived_from": "rule + historical FSR evidence",
      "requires_engineer_review": true
    },
    {
      "action": "Review vibration spectrum data for compressor-related frequencies.",
      "priority": "medium",
      "derived_from": "condition signal + SME rule",
      "requires_engineer_review": true
    }
  ],
  "confidence": "medium",
  "limitations": [
    "Assessment depends on provided condition signals and retrieved historical reports.",
    "This is not a validated probability-of-failure model unless trained risk scoring is included.",
    "Recommendations should be reviewed by a qualified engineer and checked against approved OEM procedures."
  ]
}
```

---

## 11. Example PyFunc Implementation Sketch

```python
import mlflow.pyfunc

class PredictiveMaintenanceRAGModel(mlflow.pyfunc.PythonModel):

    def predict(self, context, model_input):
        asset_id = model_input["asset_id"][0]
        question = model_input["question"][0]
        equipment_type = model_input["equipment_type"][0]
        current_signals = model_input["current_condition_signals"][0]

        # 1. Retrieve historical evidence for this asset
        asset_history_chunks = vector_search(
            query=question,
            filters={"asset_id": asset_id},
            top_k=5
        )

        # 2. Retrieve similar incidents across similar equipment
        similar_case_query = build_similar_case_query(
            question=question,
            equipment_type=equipment_type,
            current_signals=current_signals
        )

        similar_case_chunks = vector_search(
            query=similar_case_query,
            filters={"equipment_type": equipment_type},
            top_k=5
        )

        # 3. Apply rule-based risk scoring
        risk_scores = apply_rules(
            current_signals=current_signals,
            asset_history=asset_history_chunks,
            similar_cases=similar_case_chunks
        )

        # 4. Derive recommended actions from rules/playbooks/evidence
        recommended_actions = derive_recommended_actions(
            risk_scores=risk_scores,
            current_signals=current_signals,
            historical_evidence=similar_case_chunks
        )

        # 5. Build prompt for LLM explanation
        prompt = build_explanation_prompt(
            asset_id=asset_id,
            question=question,
            current_signals=current_signals,
            risk_scores=risk_scores,
            historical_evidence=asset_history_chunks + similar_case_chunks,
            recommended_actions=recommended_actions
        )

        # 6. Call LLM to summarize and format, not invent unsupported actions
        explanation = call_llm(prompt)

        # 7. Return structured output
        return {
            "asset_id": asset_id,
            "risk_scores": risk_scores,
            "recommended_actions": recommended_actions,
            "explanation": explanation,
            "sources": extract_sources(asset_history_chunks + similar_case_chunks),
            "limitations": [
                "Requires engineer review.",
                "Recommendations must be validated against approved procedures.",
                "Risk score depends on the quality and freshness of provided condition signals."
            ]
        }
```

---

## 12. What the LLM Should and Should Not Do

### The LLM should do:

```text
- summarize retrieved FSR evidence
- explain why a component is at risk
- format output clearly
- cite supporting documents
- clarify uncertainty and limitations
```

### The LLM should not do:

```text
- invent maintenance procedures
- invent failure probabilities
- override SME or OEM guidance
- make unsupported safety-critical recommendations
- act as the only source of predictive risk
```

---

## 13. Important Terminology

| Term | Meaning |
|---|---|
| FSR RAG | Retrieval-augmented generation over Field Service Reports |
| Current condition signals | Structured operational data such as vibration, temperature, operating hours, starts/stops |
| Rule-based logic | SME-defined thresholds or if/then logic |
| ML risk model | Trained model that estimates failure probability or component risk |
| PyFunc model | MLflow format that wraps Python logic behind a `predict()` method |
| Model Serving | Databricks endpoint that exposes the PyFunc model for real-time inference |
| Recommended actions | Actions grounded in rules, historical evidence, playbooks, SOPs, or ML outputs |

---

## 14. Best Interview / Resume Framing

### Accurate framing if only FSR RAG exists

```text
Built a RAG-based engineering intelligence layer over historical Field Service Reports to support predictive maintenance workflows by retrieving similar failure patterns, prior repair actions, and citation-grounded evidence for asset risk assessment.
```

### Stronger framing if current signals and risk logic are included

```text
Implemented a predictive maintenance support workflow combining current asset condition signals, historical FSR retrieval, and rule-based risk scoring to identify components at elevated failure risk with citation-grounded explanations and recommended engineering review actions.
```

### Avoid overstating

Do not say:

```text
The RAG system predicted failures by itself.
```

Better:

```text
The RAG system supported predictive maintenance by grounding risk assessments in historical service evidence and similar incident patterns.
```

---

## 15. Certification / Exam Shortcut

```text
PyFunc predict()
= serving wrapper / inference entry point

RAG
= retrieves historical evidence

Feature serving / structured data
= provides current condition signals

Rules / ML model
= estimates risk

LLM
= explains, summarizes, formats, and cites

Predictive maintenance
= combines current condition + historical evidence + risk scoring
```

Simple memory:

```text
Historical FSR RAG tells you what happened before.
Predictive maintenance tells you what might happen next.
A PyFunc model can orchestrate both if the predict() method combines retrieval, condition signals, and risk logic.
```
