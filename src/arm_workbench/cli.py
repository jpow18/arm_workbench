import argparse
import json
import sys
from pathlib import Path

from .runtime import AgentTools, TOOLS, Workbench


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulation-only robot task workbench")
    parser.add_argument("command", choices=["list", "run", "tools", "tool-schema"])
    parser.add_argument("--task", default="photo_scan")
    parser.add_argument("--output", type=Path, default=Path("runs"))
    parser.add_argument("--auto-confirm-simulation", action="store_true",
                        help="Automatically pass simulator gates (never valid for hardware)")
    args = parser.parse_args(argv)
    workbench = Workbench(args.output)
    tools = AgentTools(workbench)
    try:
        if args.command == "list":
            print(json.dumps(tools.call("list_tasks")))
        elif args.command == "tool-schema":
            print(json.dumps(TOOLS, indent=2))
        elif args.command == "tools":
            # Local JSON-lines transport. Approval is deliberately absent.
            for line in sys.stdin:
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict) or set(request) - {"tool", "arguments"}:
                        raise ValueError("Expected tool and optional arguments")
                    result = tools.call(request["tool"], request.get("arguments"))
                    print(json.dumps({"result": result}), flush=True)
                except (ValueError, KeyError, TypeError) as exc:
                    print(json.dumps({"error": str(exc)}), flush=True)
            if workbench.task and not workbench.terminal:
                workbench.stop()  # Disconnect/EOF does not leave an active session.
        else:
            status = workbench.start(args.task)
            while not workbench.terminal:
                print(json.dumps(status), flush=True)
                gate = status["pending_confirmation"]
                if gate:
                    if not args.auto_confirm_simulation:
                        response = input(f"SIMULATION: operator confirms {gate}? Type yes: ")
                        if response != "yes":
                            workbench.stop()
                            break
                    status = workbench.confirm(gate)
                else:
                    status = workbench.advance()
            print(json.dumps(workbench.status()), flush=True)
            return 0 if workbench.terminal == "completed" else 1
    except (KeyboardInterrupt, EOFError):
        workbench.stop()
        print("Stopped", file=sys.stderr)
        return 130
    except Exception as exc:
        workbench.stop()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
