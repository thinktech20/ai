# TIL Discovery — Architecture Overview
**As of:** June 5, 2026 | **Audience:** DS, Dev, ISM Integration Teams

---

## 1. Where TIL Fits in the 9-Step Scoping Agent

```mermaid
flowchart LR
    subgraph ISM["ISM / Leankor (Steps 1–5)"]
        S1[Step 1\nUnit & Labor Config]
        S2[Step 2\nSafety]
        S3[Step 3\nQuestionnaire\nDiv of Responsibilities]
        S4[Step 4\nShift Schedule]
        S5[Step 5\nTemplate Selection\nWBS Locked]
    end

    subgraph SDG["SDG Scoping Agent (Steps 6–9)"]
        S6[Step 6\n🔑 TIL Applicability\nAI Re-Validation]
        S7[Step 7\nOSA Recommendations\nAI Re-Validation]
        S8[Step 8\nAuxiliaries\nContract Classification]
        S9[Step 9\nGap Analysis\nScope Aggregation]
    end

    subgraph OUT["ISM Output"]
        WBS[WBS NON-STANDARD L5\nTILS / OSA / AUX / CUSTOM]
    end

    S1 --> S2 --> S3 --> S4 --> S5
    S5 -->|INT-SA-001\nPayload| S6
    S6 --> S7 --> S8 --> S9
    S9 -->|INT-SA-005\nVerdicts| WBS

    style S6 fill:#ffd966,stroke:#b45309,color:#000
    style ISM fill:#dbeafe,stroke:#3b82f6
    style SDG fill:#dcfce7,stroke:#16a34a
```

**TIL is Step 6 — the first and most complex AI step.** It sets the tone for the entire SDG output. If TIL applicability is wrong, everything downstream (scope, cost, schedule) is wrong.

---

## 2. Why TIL Matters — Significance in Scoping

| Dimension | Why It Matters |
|---|---|
| **Volume** | 31 TILs per event (29 GT + 2 Gen); multiplied across hundreds of outages/year |
| **Time saved** | CPMs spend 5–10 hours/outage manually reviewing TIL PDFs today |
| **Risk** | Missing a Safety/Compliance TIL = regulatory or equipment damage exposure |
| **Schedule impact** | High-impact TILs (1937/1945) add 3+ days to outage critical path |
| **Commercial** | Wrong TIL disposition = wrong PO type = cost overrun or under-recovery |
| **JIS validation** | 4,011 of 7,007 real outage workscopes contain TIL references (57%) |

---

## 3. ISM ↔ SDG Integration: TIL Data Flow

```mermaid
sequenceDiagram
    participant ISM as ISM / Leankor
    participant PowerNow as PowerNow<br/>(TIL Source)
    participant SDG as SDG Step 6<br/>(AI Re-Validator)
    participant WBS as ISM WBS<br/>NON-STD L5

    PowerNow->>ISM: TIL candidates<br/>(auto-loaded by ESN)
    ISM->>ISM: CPM dispositions<br/>Accepted | Rejected | In Review
    ISM->>SDG: INT-SA-001 payload<br/>(pre-dispositioned TIL candidates<br/>+ unit context + questionnaire)
    Note over SDG: Step 6: Re-validate<br/>CPM's judgment with AI
    SDG->>ISM: INT-SA-005 verdict<br/>(per TIL per ESN:<br/>verdict + reasoning + PO type)
    ISM->>WBS: Auto-populate<br/>NON-STANDARD L5 → TILS section
```

**SDG's role is re-validation, not first decision.** ISM CPM pre-dispositions TILs first; SDG provides AI verification and reasoning as a safety check.

---

## 4. TIL Discovery Pipeline

```mermaid
flowchart TD
    PDF["TIL PDF\n(Databricks / Box)"]
    EXT["E6.2: Profile Extraction\nFoundation Model\n(multimodal — reads image tables)"]
    PROF["profile_response.md\n• compliance_category\n• operational_triggers (prose)\n• parts_referenced + inspection_type\n• service_recommendation_line_items\n• usage_counter_requirements"]
    RAW["extracted_document.md\n(raw page text + image descriptions\nfor QnA lookup)"]

    UNIT["Unit Context\n(from INT-SA-001)\n• ESN, frame, fired_hours\n• fired_starts, ECRT\n• equipment_specific_scope"]
    SBOM["SBOM\n(part inventory\nper unit)"]
    FSR["FSR / ER\n(past completion\nevidence)"]
    CALC["External Calculator\n(factored FFH/FFS\napplicability signal)"]

    APP["E6.4: Applicability Evaluation\nLLM Reasoning\n• Does it apply to THIS unit?\n• Is it covered by template?\n• Who pays?"]

    VERDICT["INT-SA-005 Verdict\nper TIL per ESN\n• sdg_verdict: Applicable | Not Applicable | Conditional\n• ism_pre_disposition (audit trail)\n• sdg_reasoning\n• po_type_recommendation"]

    PDF --> EXT
    EXT --> PROF
    EXT --> RAW
    PROF --> APP
    UNIT --> APP
    SBOM --> APP
    FSR --> APP
    CALC --> APP
    APP --> VERDICT

    style PDF fill:#fef3c7,stroke:#d97706
    style PROF fill:#dcfce7,stroke:#16a34a
    style VERDICT fill:#dbeafe,stroke:#3b82f6
    style CALC fill:#fce7f3,stroke:#db2777
```

---

## 5. The Three Questions Step 6 Must Answer

```mermaid
flowchart LR
    TIL["TIL Candidate\n(pre-dispositioned\nby ISM CPM)"]

    Q1{"Q1: Does it apply\nto THIS unit?"}
    Q2{"Q2: What work\ndoes it generate?"}
    Q3{"Q3: Who pays?"}

    Q1_YES["✅ Applicable\n→ proceed to Q2"]
    Q1_NO["❌ Not Applicable\n→ reject with reason"]
    Q1_BASE["⬜ In-scope Baseline\n→ already in template;\nno action needed"]

    Q2_OUT["WBS activity label\n+ labor category\n+ hours estimate\n→ NON-STD TILS section"]

    Q3_OUT["PO type:\nGPP_PO1 | Extra Work\n| Customer | CMU"]

    TIL --> Q1
    Q1 --> Q1_YES
    Q1 --> Q1_NO
    Q1 --> Q1_BASE
    Q1_YES --> Q2 --> Q2_OUT
    Q2_OUT --> Q3 --> Q3_OUT

    style Q1 fill:#ffd966,stroke:#b45309
    style Q1_BASE fill:#e5e7eb,stroke:#6b7280
    style Q1_NO fill:#fee2e2,stroke:#dc2626
    style Q1_YES fill:#dcfce7,stroke:#16a34a
```

| Question | Experiment | Status (June 5) |
|---|---|---|
| **Q1: Does it apply?** | E6.2 + E6.4 | ✅ Pipeline working; JSON structuring of thresholds pending |
| **Q2: What work?** | E6.2 (prose extracted) | ⚠️ Prose extracted; WBS activity code mapping not yet done |
| **Q3: Who pays?** | None | ❌ Future work; deterministic rule post-MVP1 |

---

## 6. What Must Come OUT of TIL Profile Extraction

For Step 6 to work end-to-end, each TIL profile must produce these structured fields:

### 6.1 Applicability Signals (Q1 inputs)

| Field | Purpose | Current Status |
|---|---|---|
| `compliance_category` | Safety / Compliance / Alert / Maintenance — drives urgency and "nothing burger" filter | ✅ Extracted (Code S/C/A/M + text) |
| `operational_triggers` | FFH/FFS/ECRT thresholds → input to external calculator | ⚠️ In prose; **needs JSON structuring** |
| `part_numbers[].inspection_type_tag` | ECI / BI / FPI — validates unit capability via SBOM | ✅ Extracted per part per configuration |
| `usage_counter_requirements` | Flags which counters needed (operating_hours, starts, ECRT) | ✅ New field in June 4 extraction |
| `sbom_dependency_flag` | True/False — whether part lookup is required | ✅ Extracted |
| `baseline_equivalency` | Is this already in the standard template? ("nothing burger") | ❌ Not yet extracted — requires WBS cross-check |

### 6.2 Work Scope Signals (Q2 inputs)

| Field | Purpose | Current Status |
|---|---|---|
| `service_recommendation_line_items` | What to do (prose) | ✅ Extracted |
| `scope_of_work` | Resources / tooling required | ✅ Extracted |
| `estimated_work_days` | Schedule impact signal | ❌ Not extracted — needs inference from scope text |
| `wbs_activity_label` | ISM-compatible WBS activity name (e.g., "GT Wheel Dovetail EC Inspection") | ❌ Not in profile — use JIS workscope templates for known TILs |

### 6.3 Commercial Signals (Q3 inputs — future)

| Field | Purpose | Current Status |
|---|---|---|
| `compliance_category` | Safety/Compliance → GE obligation; Maintenance → customer-elected | ✅ Extracted |
| `contract_tier` | From INT-SA-001 unit context (CSA / T&M) | ✅ Arrives from ISM |

---

## 7. Current State (June 5, 2026)

```mermaid
gantt
    title TIL Discovery — Work Status
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section E6.2 Profile Extraction
    25-TIL pilot completed          :done,    e62a, 2026-06-01, 2026-06-04
    Image tables resolved (foundation model) :done, e62b, 2026-06-04, 2026-06-05
    JSON operational_triggers structuring  :active,  e62c, 2026-06-05, 2026-06-10
    estimated_work_days inference          :         e62d, 2026-06-10, 2026-06-15

    section E6.4 Applicability Evaluation
    Applicability pilot (25 cases)  :done,    e64a, 2026-06-01, 2026-06-04
    SBOM integration                :active,  e64b, 2026-06-05, 2026-06-15
    FSR past-evidence correlation   :         e64c, 2026-06-10, 2026-06-20
    External calculator integration :         e64d, 2026-06-15, 2026-06-25

    section ISM Integration
    INT-SA-001 schema finalized     :active,  ism1, 2026-06-05, 2026-06-07
    ISM handoff (June 5 target)     :milestone, ism2, 2026-06-05, 0d
    KT to dev team                  :         ism3, 2026-06-10, 2026-06-20

    section MVP1
    Step 6 dev implementation       :         mvp1, 2026-06-20, 2026-07-15
```

---

## 8. Key Decisions & Constraints

| Decision | What It Means |
|---|---|
| **TIL profiles = static knowledge packs** | Not real-time PDF parsing in Step 6; pre-extracted profiles are ingested at run time |
| **Foundation model reads image tables** | No OCR pipeline needed; multimodal vision resolves the image-table extraction concern |
| **External calculator handles equations** | SDG Step 6 receives pre-computed applicability signal; does NOT solve FFH/FFS/ECRT equations |
| **ISM CPM pre-dispositions first** | SDG re-validates, not decides; ISM disposition stored in INT-SA-001 for audit trail |
| **JIS workscope labels = WBS templates** | For the top 8 JIS-validated TILs, use JIS workscope descriptions as the activity label (e.g., `"GT Wheel Dovetail EC Inspection"`) |
| **93% of JIS volume = 7 TILs** | Build the compressor bundle (1509/1638/1603/1907) + wheel pair (1937/1945) + 1724 first |
