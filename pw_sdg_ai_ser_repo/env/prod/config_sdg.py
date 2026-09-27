# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# SDG Environment Config — PROD
#
# REFERENCE ONLY — these variables are NOT loaded at runtime.
# The ER, Heatmap, and FSR pipelines receive table names via DAB workflow
# parameters (databricks.yaml variables → workflow YAML → get_runtime_param).
# This file documents the expected catalog/schema/table layout for prod.
# ─────────────────────────────────────────────────────────────────────────────

# ── Catalogs ─────────────────────────────────────────────────────────────────
ai_sot_catalog = "vaip"           # AI prod — SOT metadata tables
ai_std_catalog = "vaip"           # AI prod — standard consumption (chunks, VS)
vgp_catalog = "vgpp"              # GP production — enrichment / reference tables (read-only)
viu_catalog = "viup"              # Ingestion unstructured prod — source PDF volumes

# ── Schemas ──────────────────────────────────────────────────────────────────
# FSR
fsr_sot_schema = "ai_sot_field_service_report"
fsr_std_schema = "ai_std_con_field_service_report"

# ER
er_source_schema = "qlt_std_views"
er_std_schema = "ai_std_con_field_service_report"     # target — TBD, placeholder

# Heatmap
heatmap_source_schema = "fsr_std_views"
heatmap_sot_schema = "ai_sot_field_service_report"  # co-located with FSR metadata

# ── FSR Table Names ──────────────────────────────────────────────────────────
fsr_metadata_table = f"{ai_sot_catalog}.{fsr_sot_schema}.biz_metadata_field_service_report"
fsr_chunk_table = f"{ai_std_catalog}.{fsr_std_schema}.vec_field_service_report"
fsr_run_log_table = f"{ai_sot_catalog}.{fsr_sot_schema}.fsr_run_log"
fsr_dq_log_table = f"{ai_sot_catalog}.{fsr_sot_schema}.fsr_data_quality_log"
fsr_vs_index = f"{ai_std_catalog}.{fsr_std_schema}.vs_vec_field_service_report"
fsr_vs_endpoint = "pw-ser-sdg-vector-search"

# ── ER Table Names ───────────────────────────────────────────────────────────
er_source_table = f"{vgp_catalog}.{er_source_schema}.u_pac"
er_chunk_table = f"{ai_std_catalog}.{er_std_schema}.vec_engineering_report"
er_run_log_table = f"{ai_std_catalog}.{er_std_schema}.er_run_log"
er_vs_index = f"{ai_std_catalog}.{er_std_schema}.vs_vec_engineering_report"
er_vs_endpoint = "pw-ser-sdg-vector-search"

# ── Heatmap Table Names ─────────────────────────────────────────────────────
heatmap_source_view = f"{vgp_catalog}.{heatmap_source_schema}.fsr_unit_risk_matrix_view"
heatmap_embedding_table = f"{ai_sot_catalog}.{heatmap_sot_schema}.heatmap_issue_prompt_embeddings"

# ── Volumes ──────────────────────────────────────────────────────────────────
fsr_volume_fieldvision = f"/Volumes/{viu_catalog}/ing_ud_fieldvision/fv_field_service_report"
fsr_volume_manual = f"/Volumes/{viu_catalog}/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports"

# ── Shared Settings ──────────────────────────────────────────────────────────
secret_scope = "fsr-pipeline"
litellm_base_url = "https://dev-gateway.apps.gevernova.net"  # Same gateway for prod
embedding_model = "azure-text-embedding-3-large-1"
embedding_dimension = 3072
