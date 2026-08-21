# Databricks Full Regression Run Instructions

Use this in `pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb` after syncing latest code.

## 1) Run setup cells
Run notebook cells 1 through 9 first (dependency, imports, parser/preprocessor setup).

## 2) Add one new code cell for custom batch IDs
Paste and run the following Python cell.

```python
import os as _os
import json
from datetime import datetime, timezone
from types import SimpleNamespace

OUTPUT_DIR = "/Workspace/Users/madhurima.saxena@gevernova.com/pw_sdg_ai_ser_repo/2-FSR-v2/validate/section-issue/preprocessor-outputs/after-fix-full-regression"
_os.makedirs(OUTPUT_DIR, exist_ok=True)

custom_doc_ids = [
    "cc9fe3d7-87cc-4687-9fe3-d787cc3687b3",
    "0be4a3ad-7395-41ea-8ec2-e7669c9c15aa",
    "bdd56c7a-ebe5-4bf7-904a-5bb63091ba20",
    "4597a853-5ffb-40bb-b0be-bd6307b0acdc",
    "27314604-ed52-402f-921f-34737a048841",
    "4a56cb21-fd6b-4300-ac1b-62cf53b868a0",
    "11338269-9d7c-4865-bfcf-1a4db9014acf",
    "af693a98-1e5c-499d-aa10-cccc54885c64",
    "b775cf29-8b42-4a83-af21-53075fef0802",
    "9e279e5a-a24e-4ebd-a79e-5aa24efebd04",
    "cdd0cca4-93ba-43b0-98e5-3d1ea2312c19",
    "69dfe261-34b0-4740-ab89-498e7d0072df",
    "d9b6c08b-d098-4939-a549-d113964e3150",
    "796f4d53-a8ad-42e1-af4d-53a8add2e1a4",
    "5b688732-39f2-48d2-a887-3239f258d28b",
    "fcb1511e-596a-4a56-b151-1e596afa569c",
    "b7b347fd-0b59-4c67-b609-9ad2c35105cc",
    "35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report",
    "806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report",
    "3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report",
]

batch_volume_roots = [
    "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report",
    "/Volumes/vaid/ai_std_con_field_service_report/fsr_v2_test",
]

batch_results = []

for document_id_raw in custom_doc_ids:
    document_id = document_id_raw.split("_")[0].rstrip(".")
    volume_path, selected_root, found_in_any_root = _resolve_volume_path(document_id, batch_volume_roots)

    print("\n" + "=" * 90)
    print("document_id_raw:", document_id_raw)
    print("document_id_normalized:", document_id)
    print("selected_volume_root:", selected_root)

    if not found_in_any_root:
        row = {
            "document_id_raw": document_id_raw,
            "document_id": document_id,
            "status": "skipped_missing_in_volume",
            "volume_path": volume_path,
        }
        batch_results.append(row)
        print("status: skipped_missing_in_volume |", volume_path)
        continue

    doc = {
        "document_id": document_id,
        "volume_path": volume_path,
    }

    try:
        parsed_local = parse_pymupdf(doc)
        ctx_local = SimpleNamespace(
            pages=parsed_local.pages,
            raw_pages=parsed_local.raw_pages,
            page_offsets=parsed_local.page_offsets,
            full_text=parsed_local.full_text,
            fields=fields,
            filename=parsed_local.filename,
        )
        result_local = preprocessor.preprocess(ctx_local)

        artifact_local = {
            "document_id_raw": document_id_raw,
            "document_id": document_id,
            "volume_path": volume_path,
            "selected_volume_root": selected_root,
            "run_utc": datetime.now(timezone.utc).isoformat(),
            "page_count": len(parsed_local.pages),
            "char_count": len(parsed_local.full_text),
            "metadata": result_local.get("metadata", {}) or {},
            "hints": result_local.get("hints", "") or "",
            "regions": result_local.get("regions", []) or [],
        }

        out_path = f"{OUTPUT_DIR}/{document_id}.json"
        with open(out_path, "w") as f:
            f.write(json.dumps(artifact_local, indent=2))

        row = {
            "document_id_raw": document_id_raw,
            "document_id": document_id,
            "status": "ok",
            "region_count": len(artifact_local["regions"]),
            "primary_esn": artifact_local["metadata"].get("primary_esn", ""),
            "primary_equip_type": artifact_local["metadata"].get("primary_equip_type", ""),
            "saved_to": out_path,
        }
        batch_results.append(row)
        print("status: ok | regions:", row["region_count"], "| saved:", out_path)

    except Exception as exc:
        row = {
            "document_id_raw": document_id_raw,
            "document_id": document_id,
            "status": "error",
            "error": str(exc),
        }
        batch_results.append(row)
        print("status: error |", exc)

summary_path = f"{OUTPUT_DIR}/_batch_summary.json"
with open(summary_path, "w") as f:
    f.write(json.dumps(batch_results, indent=2))

print("\n" + "=" * 90)
print("Batch summary saved:", summary_path)
print(json.dumps(batch_results, indent=2))
```

## 3) Share back these results
- `OUTPUT_DIR/_batch_summary.json`
- All generated per-doc JSON files under `OUTPUT_DIR`

## 4) Optional post-check cells
After run, use notebook validation cells near the end to spot obvious schema/coverage issues.
