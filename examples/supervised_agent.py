"""Trusted host example. The operator channel is intentionally outside AgentTools.

Run: PYTHONPATH=src python examples/supervised_agent.py
Replace the simple deterministic loop with your agent's allowlisted tool calls;
never give that agent this host's Python execution or confirmation function.
"""
from pathlib import Path

from arm_workbench.runtime import AgentTools, Workbench


def main():
    workbench = Workbench(Path("runs"))
    agent = AgentTools(workbench)
    status = agent.call("start_task", {"task": "photo_scan"})
    try:
        while status["state"] not in {"completed", "failed", "stopped"}:
            print(status)
            gate = status["pending_confirmation"]
            if gate:
                # Trusted operator host code, NOT an agent-callable tool.
                if input(f"SIMULATION operator gate {gate}. Type yes: ") != "yes":
                    status = agent.call("stop_task")
                else:
                    status = workbench.confirm(gate)
            else:
                status = agent.call("advance_task")
        print(status)
    finally:
        workbench.stop()


if __name__ == "__main__":
    main()
