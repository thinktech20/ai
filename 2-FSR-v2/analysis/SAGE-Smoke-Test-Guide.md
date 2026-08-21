# SAGE End-to-End Smoke Test Guide

**Tool:** DS Guru (SAGE) — http://localhost:8005  
**Purpose:** Verify preprocessor fix produces correct Equipment Type labels in real retrieval  
**When to run:** After updating the preprocessor, before production deployment

---

## Prerequisites

### 1. Start DS Guru (SAGE)

```bash
cd /home/u560060992/dbx/ds-guru
docker compose up -d

# Verify it's running
curl http://localhost:8005/health
```

Open browser: **http://localhost:8005**

### 2. Get the Test PDFs

Download from Vince's Box: https://gevernova.box.com/s/csbs8cl4fcjcquy7i5m879zmpzjuol42

Required files:
- `Riverside_Generator_Partial_Restack_Full_Rewind.pdf` (693 pages, Gen-only report)
- `b775cf29-8b42-4a83-af21-53075fef0802 (1).pdf` (325 pages, nested Gen under Turbine)
- Any single-equipment FSR for regression (e.g., `HGPI___IDC...pdf` or `Unit_10B...pdf`)

### 3. Install the Preprocessor (v2_fix1_fix2)

> Do this once per collection, or if the preprocessor code has changed.

1. Go to **Collections** in the left sidebar
2. Select (or create) collection: `fsr-multi-equip`
3. Click **Metadata Schema**
4. Define these fields if not already present:

   | Field | Type |
   |---|---|
   | `primary_equip_type` | string |
   | `primary_esn` | string |
   | `gt_esn` | string |
   | `gen_esn` | string |
   | `primary_technology_code` | string |
   | `inactive_esns` | string |

5. Scroll down to **Preprocessor (advanced)**
6. Paste the contents of `ds-guru/app/preprocessor_v2_fix1_fix2.py`
7. Check **Enable**
8. Click **Save Schema**
9. Click **Test** and paste a few lines from a multi-ESN FSR to verify it parses correctly

---

## Test Cases

### Test 1 — Riverside (Fix 1 validation)

**Document:** `Riverside_Generator_Partial_Restack_Full_Rewind.pdf`  
**What this tests:** Fix 1 (content-weighted primary) correctly labels a Gen-dominant doc as Generator

**Upload:**
1. Go to **Collections → fsr-multi-equip**
2. Click **Upload Documents**
3. Select the Riverside PDF
4. Check **Extract custom metadata**
5. Select chunking strategy: **Large / Scanned** (for 693-page PDF)
6. Click **Upload** — wait for processing to complete

**Test:**
1. Go to **Discovery** page
2. Set filter: `primary_equip_type = Generator`
3. Query: `stator rewind findings`

**Expected result ✓:**
```
Returns chunks with content like:
• Lamination fragmentation near slots 5-6, 16-17
• EL-CID test, Knife Checks, Wedge Map, Core Ring test
• Partial core restack (packages #81-83)
• Full Stator Rewind with new End Winding Support
```

**Failure (bug still present ✗):**
```
"No context available" or "No generator inspection findings available"
→ All chunks are still labeled Gas Turbine
```

---

### Test 2 — b775cf29 (Fix 2 validation)

**Document:** `b775cf29-8b42-4a83-af21-53075fef0802 (1).pdf`  
**What this tests:** Fix 2 (nested Generator section detection) correctly labels subsection "3.1.1 Generator Stator/Field Tests" as Generator

**Upload:** Same steps as Test 1

**Test:**
1. Go to **Discovery** page
2. Set filter: `primary_equip_type = Generator`
3. Query: `generator stator test results`

**Expected result ✓:**
```
Returns chunks with content like:
• Stator IR: 3.19, 3.16, 3.14 GΩ (criteria ≥ 1 GΩ)
• PI: 7.04, 6.8, 6.76 (criteria ≥ 2)
• DC leakage: 3.5, 3.0, 3.5 µA @ 40 kVDC (< 100 µA)
• Winding resistance: 0.001220 Ω @ 16°C
```

**Failure (bug still present ✗):**
```
"No context available"
→ Gen ESN 337X766 not detected; all 376 chunks labeled Gas Turbine
```

**Additional check (Test 2b):**
1. Same document, **no equipment filter**
2. Query: `generator bearings`
3. Check returned chunks — they should now show `primary_equip_type = Generator`
4. Before fix: chunks mention "generator" but are labeled Gas Turbine

---

### Test 3 — Regression (clean single-equipment doc)

**Document:** `HGPI___IDC...pdf` or `Unit_10B...pdf`  
**What this tests:** Fix doesn't break single-equipment documents (zero regressions)

**Upload:** Same steps as above

**Test:**
1. Go to **Discovery** page
2. Set filter: `primary_equip_type = Gas Turbine`
3. Query: `turbine blade inspection findings`

**Expected result ✓:**
```
Returns GT-specific content only
No Generator chunks appear in results
All returned chunks: primary_equip_type = Gas Turbine
```

**Failure ✗:**
```
Some chunks labeled Generator (false flip)
→ Preprocessor incorrectly detected Generator sections in a clean GT doc
```

---

## How to Check Chunk Labels (Debug)

If a test fails and you want to see what labels were assigned:

1. Go to **Collections → fsr-multi-equip**
2. Click **Browse Documents**
3. Find the uploaded document → click **View Chunks**
4. Each chunk shows its metadata including `primary_equip_type`
5. Scan through chunks to see where label changes happen

**Or via API:**
```bash
# List all chunks for a document
curl "http://localhost:8005/documents?namespace=fsr-multi-equip&limit=500" \
  | python3 -m json.tool | grep -A3 "primary_equip_type"
```

---

## Pass / Fail Summary

| Test | Doc | Filter | Query | Pass Condition |
|---|---|---|---|---|
| **T1** | Riverside | Generator | stator rewind findings | Returns lamination/winding content |
| **T2** | b775cf29 | Generator | generator stator test | Returns IR/PI/Hipot data |
| **T2b** | b775cf29 | _(none)_ | generator bearings | Returned chunks labeled Generator (not GT) |
| **T3** | HGPI/Unit_10B | Gas Turbine | turbine blade inspection | GT chunks only, no Gen false-flips |

**All 4 pass → preprocessor fix validated → ready for production deployment**

---

## Clean Up Between Runs

If testing a new preprocessor version, delete old document data first:

1. Go to **Collections → fsr-multi-equip**
2. Click **Browse Documents**
3. Delete the previously uploaded test PDFs
4. Update the preprocessor code in Metadata Schema
5. Re-upload the same PDFs

This ensures chunks are re-processed with the new preprocessor version.

---

## Reference

- DS Guru source: `ds-guru/app/preprocessor_v2_fix1_fix2.py`
- Preprocessor docs: `ds-guru/FSR_PREPROCESSOR.md`
- Accuracy scoring (numeric): run `python tools/run_our_v3.py` in sdg-autotest
