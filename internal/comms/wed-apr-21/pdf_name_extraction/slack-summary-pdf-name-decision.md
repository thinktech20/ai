# Slack Summary — PDF Name Decision

---

ran validation queries against `vgpp.fsr_std_views.fsr_pdf_ref` today, here's what the data says:

**source for pdf_name:** `fsr_pdf_ref.PDF_name` — it has 15,133 unique document UUIDs, all of them have a non-null PDF_name, and zero UUIDs map to more than one filename. clean 1:1 mapping.

**join key:** should be the normalized UUID (`document_id` = `s3_filename` with `.pdf` stripped and lowercased). ESN is not safe — 3,459 ESNs map to multiple filenames because one unit can have many FSRs.

**what this means for the schema:**
- reintroduce `document_id` as PK (the current UUID value that's sitting in `pdf_name` today)
- `pdf_name` becomes a separate derived field with the human-readable name from `fsr_pdf_ref.PDF_name`
- for manual files not in fsr_pdf_ref, fall back to the basename from volume_path

**psot:** does not carry a filename column, so it's not a source for pdf_name. it's a downstream enrichment table we reach through ESN + event key after the file is already identified. the exact event bridge is still being tested.

the schema recommendation is written up, can align with whatever Pranesh puts on the Confluence page.
