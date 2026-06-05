# ai-arch — local setup

Run notebooks locally in VS Code Jupyter. Industry-standard libs (PyMuPDF, LangChain text splitters, OpenAI SDK, FAISS) — same patterns transfer to Databricks.

## One-time setup (already done)

```bash
# venv with Python 3.11
PYENV_VERSION=3.11.9 python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name ai-arch --display-name "Python (ai-arch)"

# secrets
cp .env.example .env   # already done; .env has the dev LiteLLM key
```

## Daily use

1. Open any `.ipynb` under `code/`.
2. Top-right of the notebook, pick kernel: **Python (ai-arch)**.
3. Run cells with **Shift+Enter**.

## What's in `.env`

| Var | What it is |
| --- | --- |
| `LITELLM_BASE_URL` | GE Vernova LiteLLM gateway — OpenAI-compatible. Dev: `https://dev-gateway.apps.gevernova.net` |
| `LITELLM_API_KEY` | Dev gateway key (from `pw_sdg_ai_ser_repo/databricks.yaml`) |
| `EMBEDDING_MODEL` | `azure-text-embedding-3-large-1` (3072 dims) — same model prod uses |
| `CHAT_MODEL` | `gemini-3-flash` — same model prod uses for ESN extraction |
| `LLM_VERIFY_SSL` | `false` for corp networks without CA bundle |

## Calling the gateway from Python (industry-standard pattern)

The gateway is OpenAI-compatible. Use the **OpenAI Python SDK** with a custom `base_url`:

```python
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
    base_url=os.environ["LITELLM_BASE_URL"] + "/v1",
    api_key=os.environ["LITELLM_API_KEY"],
)

# embeddings
resp = client.embeddings.create(
    model=os.environ["EMBEDDING_MODEL"],
    input=["hello world"],
)

# chat
resp = client.chat.completions.create(
    model=os.environ["CHAT_MODEL"],
    messages=[{"role": "user", "content": "hi"}],
)
```

This is the same pattern that works against OpenAI, Azure OpenAI, AWS Bedrock proxies, and Databricks Foundation Model APIs (all OpenAI-compatible).

## Local vs. Databricks split

| Stage | Where | Notes |
| --- | --- | --- |
| Ingest, Parse | Local | Pure file I/O |
| Chunk | Local | LangChain splitters |
| Embed | Local (via gateway) | Same model as prod |
| Index | **Local FAISS first**, then DBR Vector Search later | FAISS is the standard learning vector store |
| Retrieve | Local FAISS | Same |
| Generate | Local (via gateway) | Same model as prod |
| Re-rank | Local | Cross-encoder via HF |

Anything Databricks-specific (Vector Search, `ai_query`, UC Volumes) we'll move into a separate notebook later.
