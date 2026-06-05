# Slide 7 — AdHoc QA agent architecture diagram (Mermaid draft v2)

Spec source: [`../arch-hive-slides-v2.md`](../arch-hive-slides-v2.md) → "Slide 7 — AdHoc QA agent — architecture".

Style reference: `unit-risk/8. AdHoc QA Agent.pdf` — left-to-right pipeline of grouped boxes (Data Layer → Backend Services → Q&A Agent → Chat Panel), labeled arrows, soft pastel fills.

Intent: Left-to-right flow — **user enters from the right** (Chat Panel), the agent core sits in the middle, tools sit between the agent and the data substrate on the left. The **boundary between the agent core and the tools is the grounding boundary** — tools return data, the LLM reasons over it. Retrieval lands on the *same* Vector Search index the FSR pipeline built (reinforces the shared-substrate claim from Slide 4).

---

## Diagram

```mermaid
flowchart LR
    %% ── Data substrate (left) ────────────────────────────────────────────
    subgraph DATA["Data layer"]
        direction TB
        VS[("Vector Search index<br/><i>built by FSR pipeline</i>")]
        REF["Reference data<br/><i>upstream systems</i>"]
        CTX["Assessment context<br/><i>findings · narrative ·<br/>event history</i>"]
    end

    %% ── Tools (middle-left) ──────────────────────────────────────────────
    subgraph TOOLS["Tools — persona-scoped, fixed at startup"]
        direction TB
        T1["Retrieval tool<br/><i>pre-filtered on<br/>equipment ID</i>"]
        T2["Reference-data tools"]
        T3["Assessment-context tools"]
    end

    %% ── Agent core (middle) ──────────────────────────────────────────────
    subgraph CORE["Agent core"]
        direction TB
        LOOP["ReAct loop<br/><b>Thought → Action → Observe</b>"]
        LLM[("Frontier LLM<br/><i>reasoning only</i>")]
        MEM["Session memory<br/><i>keyed on assessment_id,<br/>scoped to user</i>"]
        LOOP <--> LLM
        LOOP <--> MEM
    end

    %% ── Chat surface (right) ─────────────────────────────────────────────
    subgraph CHAT["Chat surface"]
        direction TB
        UI["Chat panel<br/><i>(frontend)</i>"]
        ENG["RE / OE engineer"]
        ENG --> UI
    end

    %% ── Flow ─────────────────────────────────────────────────────────────
    VS  -->|"reads"| T1
    REF -->|"reads"| T2
    CTX -->|"reads"| T3
    T1 -->|"Observe"| LOOP
    T2 -->|"Observe"| LOOP
    T3 -->|"Observe"| LOOP
    LOOP -->|"Action"| T1
    LOOP -->|"Action"| T2
    LOOP -->|"Action"| T3
    UI <-->|"Streaming<br/>HTTP"| LOOP

    %% ── Styling (matches deck palette) ───────────────────────────────────
    classDef data    fill:#EFF4F8,stroke:#4A5D71,stroke-width:1.5px,color:#0E1B2C;
    classDef tools   fill:#DFF1FD,stroke:#2095B2,stroke-width:1.5px,color:#0E1B2C;
    classDef core    fill:#0E1B2C,stroke:#2095B2,stroke-width:2px,color:#FFFFFF;
    classDef chat    fill:#FFFFFF,stroke:#4A5D71,stroke-width:1.5px,color:#0E1B2C;
    classDef sub     fill:#FFFFFF,stroke:#0E1B2C,stroke-width:1px,color:#0E1B2C;

    class VS,REF,CTX data;
    class T1,T2,T3 tools;
    class LOOP,LLM,MEM core;
    class UI,ENG chat;
    class DATA,TOOLS,CORE,CHAT sub;
```

> **The boundary between TOOLS and CORE is the grounding boundary.** Tools return data; the LLM reasons over the data. No tool result → no claim. That posture is what makes the agent trustable on day one.

---

## Notes for the PPT pass

- **Four grouped lanes left-to-right**: Data layer · Tools · Agent core · Chat surface. Mirrors the unit-risk reference layout.
- **Agent core is filled navy** (deck primary), so it reads as the centre of gravity. Tools sit in pale teal next to it. Data layer in neutral pale blue on the far left. Chat surface in white on the far right.
- **Retrieval arrow lands on the same VS index box visually used on Slide 4** — in the PPT pass, mirror the box shape/color from Slide 4 onto Slide 7 to reinforce "shared substrate."
- **No vendor / framework / LLM names on the diagram.** "ReAct loop", "frontier LLM", role-based tool names. Talk track can mention specifics if asked (Slide 4 / Stack slide names the stack).

## Open decisions for the visual pass

1. Persona indicator (RE vs OE) — currently implicit in the "RE / OE engineer" label, with tool list "persona-scoped, fixed at startup" called out on the TOOLS lane header. **Default: keep implicit; talk track makes the persona-aware point.**
2. Session memory shown as a separate node inside CORE so the privacy boundary reads as first-class. **Default: keep separate.**
3. Tools shown as 3 buckets; specific tool names *not* shown (would leak upstream system names). **Default: keep 3 buckets.**

