# Current Pipeline ESN Extraction Method

Confirmed: current ESN extraction in the notebook uses a layered approach.

## 1. Primary ESN Source (LLM Output)

- The pipeline reads first-page key:value text and sends it to the LLM normalizer.
- It then takes the normalized ESN field from that output as the first candidate.
- Code reference: [LLM output mapped to document rows](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L880)

## 2. Fallback ESN Source (Regex on Page-1 Raw Text)

- If the LLM ESN is empty, the pipeline falls back to helper-based regex extraction from raw page-1 text.
- Code reference: [Fallback helper function](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L466)

Regex patterns currently target:

- ESN or ESN/SY style labels followed by an alphanumeric token.
- Equipment Serial No / Equipment Serial Number style labels followed by an alphanumeric token.
- Code reference: [Regex pattern block](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L470)

## 3. ESN Validation and Reference Override

- The resolved ESN is validated against an invalid/deny list.
- If ESN is empty or not present in the FSR PDF reference ESN set, it is overridden by a reference ESN.
- Code reference: [Resolved ESN validation and override flow](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L909)

## 4. all_esns Construction and Multi-ESN Fan-out

- The pipeline builds all_esns as a union of the resolved ESN and ESNs from fsr_pdf_ref.
- This set is later used to fan out one metadata row per ESN.
- Code references:
- [Build all_esns union](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L933)
- [Multi-ESN fan-out implementation](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L1120)

## 5. IBAT Backfill During Enrichment

- During enrichment, if ESN is still blank, IBAT join can fill ESN from equip_serial_number.
- esn_source is then set to reflect whether ESN came from fsr_pdf_ref, llm, or ibat.
- Code references:
- [IBAT join and ESN fill logic](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L986)
- [esn_source assignment logic](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L1013)

## Practical Note

- When the LLM returns multiple rows for one document in a batch, this pass keeps the first matched row per document.
- Code reference: [First-match assignment behavior](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L891)