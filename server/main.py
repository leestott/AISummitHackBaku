"""Microsoft Foundry hosted Responses entry point, separate from the web API."""

import os
import json
from importlib.metadata import version

from agent_framework_foundry_hosting import ResponsesHostServer

from caspian.agent_runtime import create_hosted_agent


def main() -> None:
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
    print(
        json.dumps({
            "event": "hosted_runtime_start",
            "packages": {
                name: version(name)
                for name in (
                    "agent-framework-core",
                    "agent-framework-foundry",
                    "agent-framework-foundry-hosting",
                    "agent-framework-openai",
                    "azure-ai-agentserver-core",
                    "azure-ai-agentserver-responses",
                    "openai",
                )
            },
        }),
        flush=True,
    )
    ResponsesHostServer(create_hosted_agent(), log_level="WARNING").run()


if __name__ == "__main__":
    main()
