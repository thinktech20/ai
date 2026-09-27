### Default Databricks Folder Structure
```bash
.
├── Common
│   ├── __init__.py
│   ├── common_utils.py
│   ├── custom_funcs.py
│   ├── data.py
│   ├── test_config.py
│   ├── test_custom_funcs.py
│   └── utils.py
├── bronze
│   ├── src
│   │   ├── ddl
│   │   │   └── nb_ehs_dept_ref.sql
│   │   ├── dml
│   │   │   └── README.md
│   │   ├── etl
│   │   │   └── README.md
│   │   ├── utils
│   │   │   └── README.md
│   │   ├── validation
│   │   │   └── README.md
│   │   └── workflows
│   │       └── README.md
│   └── unit_test
│       └── README.md
├── env
│   ├── dev
│   │   ├── config.py
│   │   └── config_ehs.py
│   └── prod
│       ├── config.py
│       └── config_ehs.py
├── gold
│   ├── src
│   │   ├── ddl
│   │   │   └── README.md
│   │   ├── utils
│   │   │   └── README.md
│   │   └── validation
│   │       └── README.md
│   └── unit_test
│       └── README.md
├── silver
│   ├── src
│   │   ├── ddl
│   │   │   ├── nb_ehs_bus_param_cntl_ref_ddl.py
│   │   │   ├── nb_ehs_dept_ref_ddl.py
│   │   │   └── nb_ehs_driver_csot_ddl.py
│   │   ├── dml
│   │   │   └── README.md
│   │   ├── etl
│   │   │   └── nb_ehs_driver_csot.py
│   │   ├── utils
│   │   │   └── README.md
│   │   ├── validation
│   │   │   └── README.md
│   │   └── workflows
│   │       └── jb_ehs_driver_csot.yaml
│   └── unit_test
│       └── README.md
├── Notebook_Development_Template.py
├── config.json
└── databricks.yaml

28 directories, 34 files
```

---

## FSR Pipeline (SDG — Field Service Report Processing)

### Files

| File | Layer | Purpose |
|---|---|---|
| `common/fsr_config.py` | Shared | Runtime config, table names, secrets, chunking params, DDL column definitions |
| `silver/src/ddl/nb_sdg_fsr_ddl.py` | Silver | CREATE TABLE for metadata registry + chunk table (idempotent) |
| `silver/src/etl/nb_sdg_fsr_metadata.py` | Silver | Process 1: PDF discovery, page-1 extraction, LLM normalization, IBAT/EV/PSOT enrichment |
| `gold/src/etl/nb_sdg_fsr_chunks.py` | Gold | Process 2: Full-text extraction, recursive chunking, embedding, Delta write, VS sync |
| `silver/src/validation/nb_sdg_fsr_validate.py` | Silver | Post-run validation: schema checks, cross-process consistency, data profile |

### Tables

| Table | Schema |
|---|---|
| Metadata registry (silver) | `vaid.ai_sot_field_service_report.biz_metadata_field_service_report` |
| Chunk + embeddings (gold) | `vaid.ai_std_con_field_service_report.vec_field_service_report` |
| Vector Search index | `vaid.ai_std_con_field_service_report.vs_vec_field_service_report` |

### How to run

All notebooks use `%run ../../../common/fsr_config` for shared config. Run order:

1. `nb_sdg_fsr_ddl.py` — creates tables
2. `nb_sdg_fsr_metadata.py` — Process 1 (metadata extraction)
3. `nb_sdg_fsr_chunks.py` — Process 2 (chunking + embedding)
4. `nb_sdg_fsr_validate.py` — validation checks
