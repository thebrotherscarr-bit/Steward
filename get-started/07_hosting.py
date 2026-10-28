# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "agent-framework-foundry",
#     "agent-framework-foundry-hosting",
#     "azure-identity",
# ]
# ///
# Run with: uv run python/samples/01-get-started/07_hosting.py

# Copyright (c) Microsoft. All rights reserved.

"""Host an agent with the Foundry Responses protocol.

The same Responses host can run locally or as a Microsoft Foundry Hosted Agent.
"""

from agent_framework import Agent
from agent_framework.foundry import ResponsesHostServer
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    agent = Agent(
        client=OllamaChatClient(),
        instructions="You are a friendly assistant. Keep your answers brief.",
    )
    ResponsesHostServer(agent=agent, history_source="agent_server").run()


if __name__ == "__main__":
    main()
