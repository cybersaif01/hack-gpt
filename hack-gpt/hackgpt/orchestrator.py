"""
Core orchestrator for Hack-GPT.
Handles the full pipeline: AI → parse → confirm → execute → save → report.
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from hackgpt.config import load_config
from hackgpt.shell_utils import run_command, detect_shell, get_system_info
from hackgpt.workspace import create_workspace, workspace_path, save_finding, save_note
from hackgpt.history import get_api_messages, append_message, clear_history
from hackgpt.ai_engine import HackGPTEngine, needs_confirmation, strip_confirm_marker
from hackgpt.display import (
    print_banner, print_plan, print_command, print_output_header,
    print_output_footer, print_notes, print_info, print_success,
    print_warning, print_error, prompt_confirm, print_workspace_info,
    print_section,
)


# ─────────────────────────────────────────────────────────────────────────────
# Target extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_target(prompt: str) -> Optional[str]:
    """Try to extract a valid IP or hostname from the prompt."""
    # IP address pattern with basic validity check (each octet 0-255)
    ip_pat = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)\b"
    m = re.search(ip_pat, prompt)
    if m:
        ip = m.group(1).split("/")[0]  # strip CIDR for validation
        parts = ip.split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            return m.group(1)
    # Domain pattern — only well-formed hostnames
    domain_pat = r"\b([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+)\b"
    m = re.search(domain_pat, prompt)
    if m and "." in m.group(1):
        return m.group(1)
    return None


def _sanitize_output_file(path: str) -> str:
    """
    Sanitize a user-supplied output file path.
    - Blocks absolute paths outside CWD
    - Blocks path traversal (../)
    - Only allows safe extensions
    """
    from pathlib import PurePosixPath, PureWindowsPath
    SAFE_EXTENSIONS = {".txt", ".json", ".xml", ".md", ".log", ".csv", ".out"}
    p = Path(path)
    # Block absolute paths to sensitive dirs
    if p.is_absolute():
        sensitive = ("/etc", "/bin", "/boot", "/usr", "/sbin",
                     "C:\\Windows", "C:\\System32")
        for s in sensitive:
            if str(p).startswith(s):
                raise ValueError(f"Output path blocked (sensitive dir): {path}")
    # Block traversal sequences
    parts = p.parts
    if ".." in parts:
        raise ValueError(f"Path traversal blocked in output file: {path}")
    # Check extension
    if p.suffix.lower() not in SAFE_EXTENSIONS:
        # Allow no extension (e.g., 'output') but add .txt
        if p.suffix:
            raise ValueError(f"Unsafe output file extension: {p.suffix}")
    return str(p)


def detect_output_file(commands: list, prompt: str) -> Optional[str]:
    """Detect if any command pipes to a specific output file."""
    for cmd in commands:
        clean = strip_confirm_marker(cmd)
        m = re.search(r"(?:>|tee)\s+([^\s|&;]+)", clean)
        if m:
            return m.group(1)
    # Check prompt for "save to X.txt" or "output.txt"
    m = re.search(
        r"(?:save|output|write)(?:\s+(?:to|in|as))?\s+([^\s,]+\.(?:txt|json|xml|log|md))",
        prompt, re.IGNORECASE
    )
    if m:
        return m.group(1)
    return None


# Command execution pipeline
# ─────────────────────────────────────────────────────────────────────────────

def execute_commands(
    commands: list,
    target: Optional[str] = None,
    session_id: str = "default",
    shell_type: str = "auto",
    confirm_destructive: bool = True,
    output_file: Optional[str] = None,
) -> list:
    """
    Execute a list of commands, stream output, handle confirmations.
    Returns list of (command, returncode, stdout) tuples.
    """
    if shell_type == "auto":
        shell_type = detect_shell()

    results = []

    for i, cmd in enumerate(commands):
        # Strip internal __CONFIRM__ prefix before display/execution
        clean_cmd = strip_confirm_marker(cmd)
        print_command(clean_cmd, index=i)

        # Check if dangerous
        if confirm_destructive and needs_confirmation(cmd):
            print_warning(f"This command may be destructive or involve brute-force/exploitation.")
            if not prompt_confirm("Proceed with this command?"):
                print_info("Skipped by user.")
                results.append((clean_cmd, -1, ""))
                continue

        # Determine if this specific command has its own output file
        cmd_output_file = None
        m = re.search(r"(?:>|tee)\s+([^\s|&;]+)", clean_cmd)
        if m:
            cmd_output_file = m.group(1)  # already in command
        elif i == len(commands) - 1 and output_file:
            # Validate output file path before using it
            try:
                cmd_output_file = _sanitize_output_file(output_file)
            except ValueError as e:
                print_warning(str(e))
                cmd_output_file = None

        # Determine workspace-relative CWD
        cwd = None
        if target:
            cwd = create_workspace(target)

        print_output_header(clean_cmd)
        start = time.time()
        rc, stdout, stderr = run_command(
            clean_cmd,
            shell_type=shell_type,
            cwd=cwd,
            output_file=cmd_output_file if cmd_output_file and ">" not in clean_cmd else None,
            stream=True,
        )
        elapsed = time.time() - start
        print_output_footer(rc, cmd_output_file)

        if rc == 0 and stdout.strip():
            print_success(f"Completed in {elapsed:.1f}s")
        elif rc != 0:
            print_warning(f"Command exited with code {rc}")

        # Save to workspace logs if target known
        if target and stdout.strip():
            log_path = workspace_path(target, "logs", f"cmd_{i+1}.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"# Command: {clean_cmd}\n\n")
                f.write(stdout)
                if stderr:
                    f.write(f"\n\n# STDERR:\n{stderr}")

        results.append((clean_cmd, rc, stdout))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class HackGPTOrchestrator:
    def __init__(self, session_id: str = "default"):
        self.cfg = load_config()
        self.engine = HackGPTEngine()
        self.session_id = session_id
        self.shell_type = detect_shell()

    def run(
        self,
        prompt: str,
        target: Optional[str] = None,
        output_file: Optional[str] = None,
        no_execute: bool = False,
        no_stream: bool = False,
    ):
        """Full pipeline: AI → parse → execute → report."""

        # Try to auto-detect target from prompt
        if not target:
            target = extract_target(prompt)
            if target:
                print_info(f"Auto-detected target: {target}")

        # Setup workspace
        if target:
            ws = create_workspace(target)
            print_workspace_info(target, ws)

        # Load conversation history
        history = get_api_messages(self.session_id)
        history.append({"role": "user", "content": prompt})

        # Query AI
        print_section("Hack-GPT Response", color="cyan")
        try:
            raw_response = self.engine.chat(
                messages=history,
                stream=not no_stream,
            )
        except Exception as e:
            print_error(f"AI error: {e}")
            return

        # Save to history
        if self.cfg.get("save_history", True):
            append_message(self.session_id, "user", prompt)
            append_message(self.session_id, "assistant", raw_response)

        # Parse response
        parsed = self.engine.parse_response(raw_response)

        # Print plan & notes
        if parsed["plan"]:
            print_plan(parsed["plan"])

        # Detect output file from prompt or commands
        if not output_file:
            output_file = detect_output_file(parsed["commands"], prompt)

        # Execute commands
        if parsed["commands"] and not no_execute:
            print_section("Command Execution", color="green")
            results = execute_commands(
                commands=parsed["commands"],
                target=target,
                session_id=self.session_id,
                shell_type=self.shell_type,
                confirm_destructive=self.cfg.get("confirm_destructive", True),
                output_file=output_file,
            )

            # Feed results back as context for next turn
            if self.cfg.get("save_history", True):
                results_summary = "\n".join(
                    f"[CMD {i+1}] rc={rc}: {stdout[:500]}"
                    for i, (_, rc, stdout) in enumerate(results)
                )
                append_message(
                    self.session_id,
                    "user",
                    f"[EXECUTION RESULTS]\n{results_summary}"
                )

        elif no_execute and parsed["commands"]:
            print_section("Commands (dry-run — not executed)", color="yellow")
            for i, cmd in enumerate(parsed["commands"]):
                print_command(cmd, index=i)

        # Print notes
        if parsed["notes"]:
            print_notes(parsed["notes"])

        return parsed

    def interactive_chat(self):
        """Start an interactive REPL session."""
        print_banner()
        print_info("Interactive mode. Type 'exit' or Ctrl+C to quit. 'clear' to reset history.")
        print()

        while True:
            try:
                if RICH_AVAILABLE_DISPLAY():
                    from hackgpt.display import console
                    console.print("[bold red]hackgpt[/bold red][dim]>[/dim] ", end="")
                else:
                    print("hackgpt> ", end="", flush=True)
                prompt = input().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[*] Exiting Hack-GPT. Stay legal. Stay safe.")
                break

            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                print("[*] Exiting Hack-GPT. Stay legal. Stay safe.")
                break
            if prompt.lower() == "clear":
                clear_history(self.session_id)
                print_success("History cleared.")
                continue

            self.run(prompt)
            print()


def RICH_AVAILABLE_DISPLAY():
    try:
        import rich
        return True
    except ImportError:
        return False
