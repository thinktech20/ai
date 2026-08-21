# Generated TIL Profiles

Use `materialize_til_profiles.py` to export rows from the TIL metadata table into shareable per-TIL JSON files.

For Databricks, open `nb_materialize_til_profiles.py`, set the `table` and `output_dir` widgets, and run the notebook. It writes one folder per TIL plus a root `manifest.json`.

Default layout:

`data/generated-til-profiles/<til_id>/metadata_row.json`
`data/generated-til-profiles/<til_id>/profile_response.json`

The script also writes `data/generated-til-profiles/manifest.json` with the exported TIL list and source table name.