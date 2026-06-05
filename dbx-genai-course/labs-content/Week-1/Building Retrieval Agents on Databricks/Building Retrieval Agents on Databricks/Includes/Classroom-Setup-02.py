# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

# MAGIC %md
# MAGIC **Checking for right compute environment:**

# COMMAND ----------

if not is_serverless_4():
    raise EnvironmentError("⛔️ ERROR: This notebook must be run on a Databricks Serverless 4 environment. Please switch your compute to Serverless 4 and retry.")
else:
    print("✅ Environment check passed: Serverless 4 detected.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Variables needed for this demo/lab:**

# COMMAND ----------

print(f"✍️ Sample documents volume: {user_docs_volume}")

# COMMAND ----------

import json
from typing import Any, Optional

def _page_id_from_bbox(bbox: Any) -> Optional[int]:
    """
    bbox can be a list[dict], a dict, or None. Return bbox.page_id if present.
    Kept intentionally simple.
    """
    if not bbox:
        return None
    if isinstance(bbox, list) and bbox:
        first = bbox[0] or {}
        return first.get("page_id")
    if isinstance(bbox, dict):
        return bbox.get("page_id")
    return None

def extract_contents_from_json(json_str: str) -> str:
    """
    - Concatenate element 'content' (fallback to 'description' if missing).
    - Insert '== page ==' when page_id changes.
    - Insert an extra newline after elements whose type != 'text'.
    - Return an error string on failure (for easy debugging in DataFrame).
    """
    try:
        doc = json.loads(json_str) if isinstance(json_str, str) else json_str
        if not isinstance(doc, dict):
            return ""

        # Support both {"document":{"elements":[...]}} and {"elements":[...]}
        document = doc.get("document", doc)
        elements = document.get("elements", []) if isinstance(document, dict) else []
        if not isinstance(elements, list):
            return ""

        out_lines = []
        current_page = None

        for el in elements:
            if not isinstance(el, dict):
                continue

            # Page divider on change
            pid = _page_id_from_bbox(el.get("bbox"))
            if pid is not None and current_page is not None and pid != current_page:
                out_lines.append("")
                out_lines.append("== page ==")
                out_lines.append("")
            if pid is not None:
                current_page = pid

            # Content (fallback to description)
            c = el.get("content")
            if not (isinstance(c, str) and c.strip()):
                c = el.get("description")
            if isinstance(c, str) and c.strip():
                out_lines.append(c)

                # Extra newline after non-text elements
                t = (el.get("type") or "").lower()
                if t != "text":
                    out_lines.append("")  # produces a blank line after joining

        return "\n".join(out_lines)

    except Exception as e:
        return f"Error: {str(e)}"


# A small factory to create a PySpark UDF that uses the function above.
def extract_contents_udf():
    from pyspark.sql.types import StringType
    from pyspark.sql.functions import udf
    @udf(StringType())
    def _udf(json_str):
        try:
            return extract_contents_from_json(json_str)
        except Exception as e:
            return f"Error: {str(e)}"
    return _udf