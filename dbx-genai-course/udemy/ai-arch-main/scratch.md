Given GT-123’s past FSR history, inspection findings, operating hours, and recent vibration readings, what components are at elevated risk of failure in the next outage cycle?

Based on historical FSRs, what early warning signs preceded compressor blade cracking in similar units?

Which prior incidents look similar to the current vibration pattern on GT-123, and what failures followed?

Built a RAG-based engineering intelligence layer over historical Field Service Reports to support predictive maintenance workflows by retrieving similar failure patterns, prior repair actions, and citation-grounded evidence for asset risk assessment.

The system helped engineers move from manually searching historical service reports to evidence-based risk assessment for maintenance planning.

IF vibration trend is increasing
AND operating hours > 50,000
AND prior FSRs mention compressor blade wear
THEN compressor blade risk = high

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