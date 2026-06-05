import os
from typing import Any, Dict, List

import yaml
import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from uuid import uuid4

from langchain.agents import create_agent
from databricks_langchain import ChatDatabricks, VectorSearchRetrieverTool

# Load agent configuration from YAML file
def _load_config(path: str = "agent-config-lab.yaml") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found at '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    llm_endpoint = cfg.get("llm_endpoint_name")
    vs = cfg.get("vector_search", {}) or {}
    index_name = vs.get("index_name")
    num_results = int(vs.get("num_results", 5))
    if not llm_endpoint or not index_name:
        raise ValueError("Missing 'llm_endpoint_name' or 'vector_search.index_name' in agent-config-lab.yaml")
    return {
        "llm_endpoint_name": llm_endpoint,
        "vs_index_name": index_name,
        "vs_num_results": num_results,
    }

# Build LangChain agent with LLM and vector search tool
def build_agent(llm_endpoint: str, index_name: str, num_results: int = 5):
    model = ChatDatabricks(endpoint=llm_endpoint, max_tokens=300)
    vs_tool = VectorSearchRetrieverTool(
        name="orion_knowledge_search",
        index_name=index_name,
        description="Search Orion knowledge base for relevant information",
        num_results=num_results,
    )

    system_prompt = (
        "You are the Orion Knowledge Assistant (OKA). Respond in a clear, professional, and factual tone "
        "appropriate for engineers and technical staff. Use only verified information from Orion's internal "
        "documents, and include source references when available. If the answer cannot be found, clearly state "
        "that and suggest related sections or next steps. Do not speculate, make assumptions, or provide "
        "information outside the provided context."
    )
    agent = create_agent(
        model=model,
        tools=[vs_tool],
        system_prompt=system_prompt
    )
    return agent

# Extract last user message from conversation
def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    user_msgs = [m for m in messages if (m.get("role") == "user")]
    return str(user_msgs[-1].get("content", "")) if user_msgs else str(messages[-1].get("content", ""))

# MLflow ResponsesAgent implementation for LangChain agent
class LangChainResponsesAgent(ResponsesAgent):
    def __init__(self):
        cfg = _load_config()
        self._cfg = cfg
        self._agent = build_agent(
            llm_endpoint=cfg["llm_endpoint_name"],
            index_name=cfg["vs_index_name"],
            num_results=cfg["vs_num_results"],
        )

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        msgs = [m.model_dump() for m in request.input]  # [{'role': 'user'|'assistant', 'content': '...'}, ...]
        _ = _last_user_text(msgs) if msgs else ""

        result = self._agent.invoke(
            {"messages": msgs}
        )
        # Extract agent response text
        try:
            text = result["messages"][-1].content
        except Exception:
            text = str(result)

        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text, str(uuid4()))],
            custom_outputs=request.custom_inputs,
        )

# Set the model for mlflow. This is needed when using agent-as-code approach
AGENT = LangChainResponsesAgent()
mlflow.models.set_model(AGENT)
