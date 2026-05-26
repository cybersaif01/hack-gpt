"""
Hack-GPT CLI Entry Point
Usage:
    hackgpt -chat "run nmap scan on 10.10.10.5"
    hackgpt -chat "enumerate smb on 192.168.1.1"
    hackgpt --interactive
    hackgpt --config set api_key sk-...
    hackgpt --config show
    hackgpt --tools
    hackgpt --workspaces
    hackgpt --report 10.10.10.5
"""

import sys
import os
import argparse

from hackgpt.display import (
    print_banner, print_info, print_success, print_error, print_warning,
    print_tool_check,
)
from hackgpt.config import (
    load_config, save_config, set_config_value, CONFIG_FILE,
    PROVIDER_PRESETS, apply_provider_preset,
)
from hackgpt.shell_utils import get_system_info, check_tools
from hackgpt.workspace import list_workspaces, get_workspace_summary
from hackgpt.orchestrator import HackGPTOrchestrator
from hackgpt.history import clear_history, list_sessions


# ─────────────────────────────────────────────────────────────────────────────
# Config management commands
# ─────────────────────────────────────────────────────────────────────────────

def handle_config(args_rest: list):
    """Handle config subcommands: show, set, get"""
    cfg = load_config()

    if not args_rest:
        print_info("Usage: hackgpt --config [show|set <key> <value>|get <key>]")
        return

    sub = args_rest[0].lower()

    if sub == "show":
        print_info(f"Config file: {CONFIG_FILE}")
        print()
        masked = dict(cfg)
        if masked.get("api_key"):
            masked["api_key"] = masked["api_key"][:8] + "..." + masked["api_key"][-4:]
        for k, v in masked.items():
            print(f"  {k:25s} = {v}")

    elif sub == "set":
        if len(args_rest) < 3:
            print_error("Usage: hackgpt --config set <key> <value>")
            return
        key, value = args_rest[1], " ".join(args_rest[2:])
        # Type coercion
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)
        set_config_value(key, value)
        print_success(f"Set {key} = {value}")

    elif sub == "get":
        if len(args_rest) < 2:
            print_error("Usage: hackgpt --config get <key>")
            return
        key = args_rest[1]
        val = cfg.get(key, "<not set>")
        if key == "api_key" and val and val != "<not set>":
            val = val[:8] + "..." + val[-4:]
        print(f"{key} = {val}")

    else:
        print_error(f"Unknown config sub-command: {sub}")


# ─────────────────────────────────────────────────────────────────────────────
# Provider setup
# ─────────────────────────────────────────────────────────────────────────────

def handle_provider(provider_arg: str, api_key: str = None):
    """Switch AI provider preset in one command."""
    provider = provider_arg.lower().strip()

    # List available providers
    if provider in ("list", "ls", ""):
        print_info("Available providers:")
        for name, p in PROVIDER_PRESETS.items():
            print(f"  {name:12s}  {p['label']}")
            print(f"  {'':12s}  {p['key_hint']}")
            print()
        return

    if provider not in PROVIDER_PRESETS:
        print_error(f"Unknown provider: '{provider}'")
        print_info(f"Available: {', '.join(PROVIDER_PRESETS.keys())}")
        return

    preset = PROVIDER_PRESETS[provider]

    # If no key passed and not ollama, ask for it
    if not api_key and provider != "ollama":
        cfg = load_config()
        if not cfg.get("api_key"):
            print_info(f"{preset['key_hint']}")
            print_info("Enter your API key (or press Enter to skip): ", )
            try:
                typed = input().strip()
                if typed:
                    api_key = typed
            except (EOFError, KeyboardInterrupt):
                pass

    try:
        updated = apply_provider_preset(provider, api_key)
        print_success(f"Provider set to: {preset['label']}")
        print_info(f"  Model    : {updated['model']}")
        print_info(f"  API base : {updated['api_base']}")
        if api_key:
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
            print_info(f"  API key  : {masked}")
        print()
        print_success("Done! You can now run: hackgpt -chat \"your prompt\"")
    except ValueError as e:
        print_error(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Report command
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(target: str):
    """Generate a markdown report for an existing workspace."""
    import json
    from pathlib import Path
    from hackgpt.workspace import get_workspace, workspace_path
    from hackgpt.orchestrator import HackGPTOrchestrator

    ws = get_workspace(target)
    summary = get_workspace_summary(target)

    print_info(f"Generating report for: {target}")

    orc = HackGPTOrchestrator(session_id=f"report_{target}")
    prompt = (
        f"Generate a comprehensive professional penetration test report for target: {target}. "
        f"Workspace data: {json.dumps(summary, indent=2)}. "
        "Include: Executive Summary, Scope, Open Ports, Services, Technologies, "
        "Vulnerabilities, CVEs, Evidence, Risk Levels, Exploitation Notes, "
        "Remediation, Recommended Next Steps. Format as markdown."
    )
    parsed = orc.run(prompt, target=target, no_execute=True)

    if parsed and parsed.get("raw"):
        report_file = workspace_path(target, "reports", "pentest_report.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(parsed["raw"])
        print_success(f"Report saved: {report_file}")


# ─────────────────────────────────────────────────────────────────────────────
# Main CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hackgpt",
        description="Hack-GPT: Advanced Cybersecurity CLI AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  hackgpt -chat "run nmap scan on 10.10.10.5 and save output in output.txt"
  hackgpt -chat "enumerate smb on 192.168.1.100"
  hackgpt -chat "run full recon on 10.10.10.5"
  hackgpt -chat "perform web fuzzing on http://target.htb"
  hackgpt -chat "analyze this PCAP: /tmp/capture.pcap"
  hackgpt -chat "run sqlmap on http://target.htb/login" --force
  hackgpt --interactive
  hackgpt --interactive --force
  hackgpt --config set api_key sk-yourkey
  hackgpt --config set model gpt-4o
  hackgpt --config show
  hackgpt --tools
  hackgpt --workspaces
  hackgpt --report 10.10.10.5
  hackgpt --session my-htb-box -chat "run recon"
  hackgpt --clear-history
  hackgpt --no-execute -chat "show me how to enumerate ldap"
  hackgpt --force -chat "run hydra brute force"   # skip all confirmations
        """,
    )

    parser.add_argument(
        "--provider",
        metavar="PROVIDER",
        help="Set AI provider: gemini | openai | groq | ollama | mistral | list",
    )
    parser.add_argument(
        "--key",
        metavar="API_KEY",
        help="API key to use with --provider (optional, will prompt if missing)",
    )
    parser.add_argument(
        "-chat", "--chat",
        metavar="PROMPT",
        nargs="+",
        help="Send a prompt to Hack-GPT and execute the resulting commands",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start interactive chat session (REPL)",
    )

    # ── Options ──
    parser.add_argument(
        "--target", "-t",
        metavar="TARGET",
        help="Explicitly set target IP/domain",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Save command output to this file",
    )
    parser.add_argument(
        "--session", "-s",
        metavar="SESSION_ID",
        default="default",
        help="Session ID for conversation history (default: 'default')",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Show commands but do not execute them (dry-run)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output from AI",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        help="Override AI model for this request",
    )

    # ── Utility flags ──
    parser.add_argument(
        "--config",
        nargs="*",
        metavar="CMD",
        help="Manage config: show | set <key> <value> | get <key>",
    )
    parser.add_argument(
        "--tools",
        action="store_true",
        help="Check which cybersecurity tools are installed",
    )
    parser.add_argument(
        "--workspaces",
        action="store_true",
        help="List all pentest workspaces",
    )
    parser.add_argument(
        "--report",
        metavar="TARGET",
        help="Generate a pentest report for a target",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear conversation history for the current session",
    )
    parser.add_argument(
        "--sessions",
        action="store_true",
        help="List all saved sessions",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip all confirmation prompts (remove permission/root checks). Use with caution!",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version",
    )
    parser.add_argument(
        "--banner",
        action="store_true",
        help="Print banner",
    )

    return parser


def main():
    parser = build_parser()

    # Support hackgpt -chat without -- prefix properly
    # argparse handles -chat as a short option group, let's pre-process
    args, extra = parser.parse_known_args()

    # ── Version ──
    if args.version:
        from hackgpt import __version__
        print(f"Hack-GPT v{__version__}")
        return

    # ── Banner ──
    if args.banner:
        print_banner()
        return

    # ── Config ──
    if args.config is not None:
        handle_config(args.config if args.config else extra)
        return

    # ── Provider setup ──
    if args.provider:
        handle_provider(args.provider, getattr(args, "key", None))
        return

    # ── Tools check ──
    if args.tools:
        print_banner()
        sys_info = get_system_info()
        print_info(f"OS: {sys_info['platform']} {sys_info['release']}")
        print_info(f"Shell: {sys_info['shell']}")
        print_info(f"Python: {sys_info['python_version']}")
        print()
        all_tools = sys_info["installed_tools"] + sys_info["missing_tools"]
        availability = check_tools(all_tools)
        print_tool_check(availability)
        return

    # ── Workspaces ──
    if args.workspaces:
        wss = list_workspaces()
        if not wss:
            print_info("No workspaces found.")
        else:
            print_info(f"Found {len(wss)} workspace(s):")
            for ws in wss:
                print(f"  • {ws}")
        return

    # ── Sessions ──
    if args.sessions:
        sessions = list_sessions()
        if not sessions:
            print_info("No sessions found.")
        else:
            print_info("Saved sessions:")
            for s in sessions:
                print(f"  • {s}")
        return

    # ── Clear history ──
    if args.clear_history:
        clear_history(args.session)
        print_success(f"Cleared history for session: {args.session}")
        return

    # ── Report generation ──
    if args.report:
        print_banner()
        generate_report(args.report)
        return

    # ── Override model if specified ──
    if args.model:
        from hackgpt.config import set_config_value
        # Temporarily override in memory
        os.environ["HACKGPT_MODEL"] = args.model

    # ── Chat mode ──
    if args.chat:
        prompt = " ".join(args.chat)
        force = getattr(args, "force", False)

        print_banner()  # Always show banner in chat mode

        # Validate API key is set before doing anything
        cfg = load_config()
        if not cfg.get("api_key"):
            print_error("No API key configured!")
            print()
            print_info("Quick setup — pick your provider:")
            print()
            print("  Gemini (Google AI Studio — FREE):")
            print("    hackgpt --provider gemini --key AIzaSy...")
            print()
            print("  OpenAI:")
            print("    hackgpt --provider openai --key sk-...")
            print()
            print("  Groq (FREE, very fast):")
            print("    hackgpt --provider groq --key gsk_...")
            print()
            print("  Ollama (local, no key needed):")
            print("    hackgpt --provider ollama")
            print()
            print_info("Or run interactively: hackgpt --provider gemini")
            sys.exit(1)

        orc = HackGPTOrchestrator(session_id=args.session, force=force)
        orc.run(
            prompt=prompt,
            target=args.target,
            output_file=args.output,
            no_execute=args.no_execute,
            no_stream=args.no_stream,
            force=force,
        )
        return

    # ── Interactive mode ──
    if args.interactive:
        force = getattr(args, "force", False)
        cfg = load_config()
        if not cfg.get("api_key"):
            print_banner()
            print_error("No API key configured!")
            print_info("Run: hackgpt --config set api_key sk-yourkey")
            sys.exit(1)
        orc = HackGPTOrchestrator(session_id=args.session, force=force)
        orc.interactive_chat()
        return

    # ── Default: show help ──
    print_banner()
    parser.print_help()


if __name__ == "__main__":
    main()
