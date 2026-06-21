"""Agent/MCP driver — connects to an MCP server as a real client (FastMCP `Client`).

The call-plan validation is pure and unit-tested. The live handshake lazily imports the
FastMCP client and is gated on availability (FastMCP is an optional `pmkit[dogfood]` dep,
not a core one), so the suite runs without it. The driver launches the documented server
command over stdio and calls the documented tools — exercising the real wire, not the engine.

SECURITY: the server launch command is executed verbatim with the operator's local
privileges (same trust assumption as the install runner) — it must come from a trusted,
operator-reviewed source, not an untrusted/auto-scraped doc without a human in the loop.
"""

from __future__ import annotations

from typing import Any


def plan_calls(calls: list[dict]) -> list[dict]:
    """Validate + normalize tool calls into a plan. Pure."""
    plan: list[dict] = []
    for i, c in enumerate(calls):
        tool = c.get("tool")
        if not tool:
            raise ValueError(f"call {i}: missing 'tool'")
        args = c.get("args", {})
        if not isinstance(args, dict):
            raise ValueError(f"call {i}: 'args' must be an object")
        plan.append({"tool": tool, "args": args})
    return plan


def mcp_client_available() -> bool:
    try:
        from fastmcp import Client  # noqa: F401
    except Exception:
        return False
    return True


def drive_mcp(server_cmd: list[str], calls: list[dict], *, timeout: float = 30.0) -> list[dict]:
    """Launch the documented server over stdio and call its tools. Raises if FastMCP absent."""
    plan = plan_calls(calls)
    if not mcp_client_available():
        raise RuntimeError("FastMCP client not available — install pmkit[dogfood] (fastmcp)")
    import asyncio

    return asyncio.run(_drive_async(server_cmd, plan, timeout))


async def _drive_async(server_cmd: list[str], plan: list[dict], timeout: float) -> list[dict]:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    obs: list[dict] = []
    transport = StdioTransport(command=server_cmd[0], args=list(server_cmd[1:]))

    async def _run() -> None:
        async with Client(transport) as client:
            for call in plan:
                try:
                    res = await client.call_tool(call["tool"], call["args"])
                    obs.append({"step": f"{call['tool']}({call['args']})", "ok": True,
                                "observed": str(getattr(res, "data", res))[:500]})
                except Exception as e:
                    obs.append({"step": call["tool"], "ok": False,
                                "observed": f"{type(e).__name__}: {e}"})

    try:
        await asyncio.wait_for(_run(), timeout)
    except asyncio.TimeoutError:
        obs.append({"step": "connect", "ok": False, "observed": f"timeout after {timeout}s"})
    except Exception as e:
        obs.append({"step": "connect", "ok": False, "observed": f"{type(e).__name__}: {e}"})
    return obs
