# TIL Profile Extraction Difference

All Keys in the Json are the same, good!

---

## 1. Categorical / Structured Value Differences

### 1.1 `extraction_confidence` is lower on average

### 1.2 `coarse_outage_type` is different for ~6 Tils
But I think it is not critical since we have SOT outage type as primary data in downstream analysis

### 1.3 `sbom_dependency_flag` Disagreements

The sbom_dependency_flag is different, but the part_number are the same, which are "null", which won't trigger later analysis different because we are actually using part_number to trigger SBOM sql.

| TIL | DS | DEV |
|-----|-------|-----|
| 1502-2R1 | False | True |
| 1615-R1 | False | True |
| 1870-R2 | True | False |
| 1972-R2 | True | False |
| 2297 | True | False |
| 2511 | True | False |

### 1.4 `recurring_indicator_if_found` Disagreements
Not critical since we have SOT recurring information as primary data

| TIL | DS | DEV |
|-----|-------|-----|
| 2322-R2 | Yes | None |

### 1.5 `til_number` Format Difference

DS always uses prefix "TIL " (e.g., `"TIL 1502-2R1"`), DEV uses bare number sometimes (e.g., `"1502-2R1"`).

**Please keep in mind** as it may affect downstream formatting.

### 1.6 `source_location` difference

Don't know why it is different, but I would prefer the page, location format we used currently. (Edited the instruction in system prompt, try again)

---

## 2. Part Number Differences

### 2.1 Genuine Part Number Discrepancy
 
**CRITICAL** your parsing reads 6 to 5, 8 to 3 sometimes

| TIL | Only in DS | Only in DEV |
|-----|-------|-----|
| **1937-R2** | `131T7528, 144E7562, 146E2874, 146E3626, 323E1860` | `131T7523, 145E2874, 145E3626` |
| **1945-R2** | `119E6594, 188D7848, 188D7895, 323E1860, 323E1916` | `183D7848, 183D7895` |

### 2.2 DEV Extracts Range-Style Part Numbers

TIL 2045-R2, DEV extracted `"129T6911P0001 through P048"` and `"129T6911P0101 through P0108"` while DS version extracted `129T6911`, we want to keep part_number be free of text. (changed prompt and you can retry)

### 2.3 Missing vs Null

Some Tils has different number of free text parts references, but we only use part number downstream, so not critical to me.

## 3 Line activities/completion criterion Difference

Noticed some different line activities numbers, but need SME's knowledge on if there are any real disagreements.
