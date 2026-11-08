"""STEWARD: a Microsoft Agent Framework agent running on local Ollama."""

import asyncio
import os
import sys
from pathlib import Path

from agent_framework import Agent
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "harness" / "steward"))
import install  # noqa: E402 - the install's own entries (ExecPlan 0006 P1)

load_dotenv()
os.environ.setdefault("OLLAMA_MODEL", "gpt-oss:20b")

INSTRUCTIONS = f"""You are STEWARD, {install.owner()}'s local engineering and development assistant.
You help with research, conversation, planning and managing work, and writing code.
Be direct and brief. Say plainly when you don't know something."""


def build_agent() -> Agent:
    return Agent(client=OllamaChatClient(), name="STEWARD", instructions=INSTRUCTIONS)


async def main() -> None:
    agent = build_agent()
    session = agent.create_session()
    print(f"STEWARD on {os.environ['OLLAMA_MODEL']}. Type 'exit' to quit.\n")
    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in {"exit", "quit"}:
            break
        if not query:
            continue
        print("STEWARD: ", end="", flush=True)
        async for chunk in agent.run(query, session=session, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
