# Copyright (c) Microsoft. All rights reserved.

"""Create a harness agent for multi-step tasks.

A harness adds planning, todos, and compaction to a regular agent.
More samples: https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness
"""

import asyncio

from agent_framework import create_harness_agent
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    agent = create_harness_agent(
        client=OllamaChatClient(),
        agent_instructions="Help users plan and complete multi-step tasks.",
        disable_file_memory=True,
        disable_web_search=True,
    )
    session = agent.create_session()

    print(await agent.run("Plan a weekend trip to Seattle.", session=session))
    print(await agent.run("Turn that plan into a checklist.", session=session))


if __name__ == "__main__":
    asyncio.run(main())
