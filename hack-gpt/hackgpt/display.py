"""
Rich terminal UI utilities for Hack-GPT.
Handles colored output, banners, progress, and formatting.
"""

import sys
import os

# Try rich first, fall back to basic ANSI
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.markdown import Markdown
    from rich import box
    RICH_AVAILABLE = True
    # safe_box=True disables Unicode box-drawing; force_terminal lets us control rendering
    # On Windows without full VT support, use no-color safe mode
    _is_win_legacy = sys.platform == "win32" and not os.environ.get("WT_SESSION") and not os.environ.get("TERM")
    if _is_win_legacy:
        console = Console(highlight=False, safe_box=True, soft_wrap=True,
                          force_terminal=False, no_color=False)
    else:
        console = Console(highlight=False, safe_box=True)
except ImportError:
    RICH_AVAILABLE = False
    console = None

# ANSI color codes (fallback)
RESET   = "\033[0m"
BOLD    = "\033[1m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"
DIM     = "\033[2m"

# Disable ANSI on Windows CMD if not supported
if sys.platform == "win32" and not os.environ.get("WT_SESSION") and not os.environ.get("TERM"):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Best effort


BANNER = r"""
  _   _            _           ___  ____ _____
 | | | | __ _  ___| | __      / _ \|  _ \_   _|
 | |_| |/ _` |/ __| |/ /____ | | | | |_) || |
 |  _  | (_| | (__|   <_____|| |_| |  __/ | |
 |_| |_|\__,_|\___|_|\_\      \__\_\_|    |_|
"""

SUBTITLE = "Advanced Cybersecurity CLI AI Assistant | v1.0.0"


def print_banner():
    if RICH_AVAILABLE:
        console.print(f"[bold red]{BANNER}[/bold red]")
        console.print(
            Panel(
                f"[bold cyan]{SUBTITLE}[/bold cyan]\n"
                "[dim]Type [bold]hackgpt --help[/bold] for usage | "
                "[bold]hackgpt --config[/bold] to setup API key[/dim]",
                border_style="red",
                padding=(0, 2),
            )
        )
    else:
        print(f"{RED}{BANNER}{RESET}")
        print(f"{CYAN}{BOLD}{SUBTITLE}{RESET}\n")


def print_section(title: str, color: str = "cyan"):
    if RICH_AVAILABLE:
        console.rule(f"[bold {color}]{title}[/bold {color}]")
    else:
        print(f"\n{CYAN}{BOLD}{'─'*20} {title} {'─'*20}{RESET}")


def print_plan(text: str):
    if not text:
        return
    if RICH_AVAILABLE:
        console.print(
            Panel(text, title="[bold yellow][PLAN][/bold yellow]",
                  border_style="yellow", padding=(1, 2))
        )
    else:
        print(f"\n{YELLOW}{BOLD}[PLAN]{RESET}")
        print(text)


def print_command(cmd: str, index: int = 0):
    if RICH_AVAILABLE:
        lang = "powershell" if any(k in cmd.lower() for k in ["get-", "set-", "invoke-"]) else "bash"
        console.print(
            Panel(
                Syntax(cmd, lang, theme="monokai", word_wrap=True),
                title=f"[bold green]CMD [{index+1}][/bold green]",
                border_style="green",
                padding=(0, 1),
            )
        )
    else:
        print(f"\n{GREEN}{BOLD}[CMD {index+1}]{RESET} {CYAN}{cmd}{RESET}")


def print_output_header(cmd: str):
    if RICH_AVAILABLE:
        console.print(f"[dim]── Output ──────────────────────────────[/dim]")
    else:
        print(f"{DIM}── Output ─────────────────────{RESET}")


def print_output_footer(rc: int, output_file: str = None):
    status = "[+] Done" if rc == 0 else f"[!] Exit code: {rc}"
    color = "green" if rc == 0 else "red"
    if RICH_AVAILABLE:
        msg = f"[{color}]{status}[/{color}]"
        if output_file:
            msg += f"  [dim]-> Saved: {output_file}[/dim]"
        console.print(msg)
    else:
        clr = GREEN if rc == 0 else RED
        print(f"{clr}{status}{RESET}" + (f"  -> Saved: {output_file}" if output_file else ""))


def print_notes(text: str):
    if not text:
        return
    if RICH_AVAILABLE:
        console.print(
            Panel(
                Markdown(text),
                title="[bold magenta]NOTES & NEXT STEPS[/bold magenta]",
                border_style="magenta",
                padding=(1, 2),
            )
        )
    else:
        print(f"\n{MAGENTA}{BOLD}[NOTES]{RESET}")
        print(text)


def print_info(msg: str):
    if RICH_AVAILABLE:
        console.print(f"[dim][*][/dim] {msg}")
    else:
        print(f"[*] {msg}")


def print_success(msg: str):
    if RICH_AVAILABLE:
        console.print(f"[bold green][+][/bold green] {msg}")
    else:
        print(f"{GREEN}[+]{RESET} {msg}")


def print_warning(msg: str):
    if RICH_AVAILABLE:
        console.print(f"[bold yellow][!][/bold yellow] {msg}")
    else:
        print(f"{YELLOW}[!]{RESET} {msg}")


def print_error(msg: str):
    if RICH_AVAILABLE:
        console.print(f"[bold red][ERROR][/bold red] {msg}")
    else:
        print(f"{RED}[ERROR]{RESET} {msg}", file=sys.stderr)


def prompt_confirm(question: str) -> bool:
    """Ask user for yes/no confirmation."""
    if RICH_AVAILABLE:
        console.print(f"[bold yellow][?][/bold yellow] {question} [dim](y/N)[/dim] ", end="")
    else:
        print(f"{YELLOW}[?]{RESET} {question} (y/N) ", end="")
    try:
        ans = input().strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def print_tool_check(available: dict):
    """Print a tool availability table."""
    if RICH_AVAILABLE:
        table = Table(title="Tool Availability", box=box.SIMPLE)
        table.add_column("Tool", style="cyan")
        table.add_column("Status")
        for tool, ok in sorted(available.items()):
            status = "[green]installed[/green]" if ok else "[red]missing[/red]"
            table.add_row(tool, status)
        console.print(table)
    else:
        print("\n[TOOLS]")
        for tool, ok in sorted(available.items()):
            mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
            print(f"  {mark} {tool}")


def print_workspace_info(target: str, ws_path: str):
    if RICH_AVAILABLE:
        console.print(
            Panel(
                f"[cyan]Target:[/cyan] [bold]{target}[/bold]\n"
                f"[cyan]Workspace:[/cyan] {ws_path}",
                title="[bold blue]WORKSPACE[/bold blue]",
                border_style="blue",
            )
        )
    else:
        print(f"\n[WORKSPACE] Target: {target}")
        print(f"  Path: {ws_path}")
