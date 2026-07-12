import os
import sys

from dotenv import load_dotenv

load_dotenv()

current_folder = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_folder)

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from tools import search_catalog

SYSTEM_PROMPT = """
You are an expert Electronics Recommender Assistant. 
Your goal is to help users find the best products based on their needs.

INSTRUCTIONS:
1. ALWAYS use the `search_catalog` tool when a user asks for a product, recommendation, or price.
2. Read the results from the tool and summarize them clearly for the user.
3. If the tool returns "Price unavailable", suggest that they check the latest price online.
4. Keep your responses conversational, helpful, and concise. Do not just dump the raw data.
5. If the user is just saying hello, greet them back and ask what kind of electronics they are looking for.
"""


def _ollama_chat_kwargs(model_name: str) -> dict:
    base_url = (
        os.getenv("OLLAMA_BASE_URL", "").strip() or "http://localhost:11434/v1"
    )
    api_key = os.getenv("OLLAMA_API_KEY", "").strip() or "ollama"
    return {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": 0.3,
    }


def create_recommender_agent(model_name: str | None = None):
    resolved_model = (
        model_name
        if model_name
        else os.getenv("OLLAMA_MODEL", "").strip() or "qwen2.5:3b"
    )

    llm = ChatOpenAI(**_ollama_chat_kwargs(resolved_model))

    tools = [search_catalog]

    agent_executor = create_react_agent(
        llm,
        tools=tools,
    )

    return agent_executor


def resolve_system_prompt_for_user(user_id: str) -> str:
    from memory.user_memory import build_memory_context

    prefs_block = build_memory_context(user_id)
    base = SYSTEM_PROMPT.strip()
    if prefs_block.strip():
        return base + "\n" + prefs_block.strip()
    return base


def invoke_recommender_with_memory(agent, user_id: str, user_input: str) -> str:
    from memory.user_memory import load_history, save_message

    user_input_clean = user_input.strip()
    if not user_input_clean:
        return ""

    system_text = resolve_system_prompt_for_user(user_id)
    history = load_history(user_id, limit=20)

    messages_payload = (
        [SystemMessage(content=system_text)]
        + history
        + [HumanMessage(content=user_input_clean)]
    )

    result = agent.invoke({"messages": messages_payload})
    final_answer = result["messages"][-1].content

    save_message(user_id, "user", user_input_clean)
    save_message(user_id, "assistant", final_answer)

    return final_answer


if __name__ == "__main__":

    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or "qwen2.5:3b"

    print("Initializing Agent. Connecting to local Ollama server...")
    app_local = create_recommender_agent(model_name=OLLAMA_MODEL)

    print("-" * 50)
    print("WELCOME TO THE ELECTRONICS RECOMMENDER")
    print("Type 'quit' or 'exit' to stop.")
    print("-" * 50)

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ["quit", "exit"]:
            print("Goodbye.")
            break

        if not user_input.strip():
            continue

        messages_cli = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_input),
            ]
        }

        print("Agent: ", end="", flush=True)

        try:
            result_cli = app_local.invoke(messages_cli)

            print(result_cli["messages"][-1].content + "\n")

        except Exception as e_cli:
            print(f"\nError connecting to local LLM: {e_cli}")
            print("Tip: Make sure the Ollama application is running in the background.")
