"""Agent orchestration module."""
from langchain.agents import create_agent
from agents.tools import python_executor
from agents.prompts import SYSTEM_PROMPT
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

load_dotenv()
DEFAULT_MODEL_NAME = "openai/gpt-oss-120b"
SUPPORTED_MODEL_NAMES = {
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
}

def build_agent(model_name: str | None = None, api_key: str | None = None):
    selected_model = (model_name or DEFAULT_MODEL_NAME).strip()
    if selected_model not in SUPPORTED_MODEL_NAMES:
        selected_model = DEFAULT_MODEL_NAME
    resolved_api_key = (api_key or "").strip()

    llm_kwargs = {
        "model_name": selected_model,
        "temperature": 0.3,
    }
    if resolved_api_key:
        llm_kwargs["api_key"] = resolved_api_key

    llm = ChatGroq(**llm_kwargs)
    agent = create_agent(
        model=llm,
        tools=[python_executor],
        system_prompt=SYSTEM_PROMPT,
    )

    return agent