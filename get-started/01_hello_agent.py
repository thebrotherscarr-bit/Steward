# Copyright (c) Microsoft. All rights reserved.

"""Create and run a minimal Agent Framework agent.

The agent uses a Microsoft Foundry chat client and prints one response.
For streaming, see `foundry_chat_client_basic.py` in:
https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/providers/foundry
"""

import asyncio

from agent_framework import Agent
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    agent = Agent(
        client=OllamaChatClient(),
        instructions="You are a friendly assistant. Keep your answers brief.",
    )
    print(await agent.run("What is the largest city of France?"))


if __name__ == "__main__":
    asyncio.run(main())
