"""
Rich terminal UI utilities for Hack-GPT.
Handles colored output, banners, progress, and formatting.
"""

import sys
import os

# ── Force UTF-8 output on Windows to prevent UnicodeEncodeError ──────────────
# This must happen BEFORE any output, including rich imports.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass  # Python < 3.7 or already configured

# ── Detect terminal capabilities ──────────────────────────────────────────────
_is_win_legacy = (
    sys.platform == "win32"
    and not os.environ.get("WT_SESSION")      # Windows Terminal
    and not os.environ.get("TERM_PROGRAM")    # VSCode, etc.
    and not os.environ.get("TERM")            # Unix-style term
    and not os.environ.get("ConEmuPID")       # ConEmu
)

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

    if _is_win_legacy:
        # Legacy Windows CMD: use ASCII-only box chars, force encoding safe mode
        console = Console(
            highlight=False,
            safe_box=True,
            soft_wrap=True,
            force_terminal=True,
            legacy_windows=False,
        )
        _BOX_STYLE = box.ASCII
    else:
        console = Console(highlight=False, safe_box=True)
        _BOX_STYLE = box.ROUNDED
except ImportError:
    RICH_AVAILABLE = False
    console = None
    _BOX_STYLE = None

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

# Enable VT processing on Windows for ANSI color support
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Best effort


# Hack-GPT pure-ASCII banner (safe on ALL terminals including legacy Windows CMD)
BANNER_SAFE = (
    "\n"
    "  ##  ##  ##   ##  ####  ##  ##        ####  ####  ######  \n"
    "  ##  ##  ## # ##  ## ## ## ##        ## ##  ## ##    ##   \n"
    "  ######  ##   ##  ##    ####   ####  ## ##  ## ##    ##   \n"
    "  ##  ##  ##   ##  ## ## ## ##        ###   ## ##    ##   \n"
    "  ##  ##  ##   ##   ####  ##  ##     ## ##  ####     ##   \n"
    "\n"
    "        [ HACK-GPT v2.0.0 ]  Advanced Cybersecurity AI  \n"
    "\n"
)

SUBTITLE = "Advanced Cybersecurity CLI AI Assistant | v2.0.0"


def _safe_print(text: str, color_prefix: str = "", color_reset: str = ""):
    """Print text safely, with ASCII fallback on encoding errors."""
    try:
        print(f"{color_prefix}{text}{color_reset}")
    except (UnicodeEncodeError, UnicodeDecodeError):
        safe = text.encode("ascii", errors="replace").decode("ascii")
        print(f"{color_prefix}{safe}{color_reset}")


def _safe_console_print(markup: str):
    """Print rich markup, falling back to plain text on encoding error."""
    try:
        console.print(markup)
    except (UnicodeEncodeError, UnicodeDecodeError, Exception):
        # Strip markup tags and print plain
        import re as _re
        plain = _re.sub(r"\[/?[^\]]+\]", "", markup)
        try:
            print(plain)
        except Exception:
            print(plain.encode("ascii", errors="replace").decode("ascii"))


def print_banner():
    banner_text = BANNER_SAFE

    if RICH_AVAILABLE:
        try:
            console.print(f"[bold red]{banner_text}[/bold red]")
            console.print(
                Panel(
                    f"[bold cyan]{SUBTITLE}[/bold cyan]\n"
                    "[dim]Type [bold]hackgpt --help[/bold] for usage | "
                    "[bold]hackgpt --config[/bold] to setup API key | "
                    "[bold]hackgpt --force[/bold] to skip confirmations[/dim]",
                    border_style="red",
                    box=_BOX_STYLE,
                    padding=(0, 2),
                )
            )
        except Exception:
            _safe_print(banner_text, RED, RESET)
            _safe_print(SUBTITLE, CYAN + BOLD, RESET)
    else:
        _safe_print(banner_text, RED, RESET)
        _safe_print(f"{SUBTITLE}\n", CYAN + BOLD, RESET)


def print_section(title: str, color: str = "cyan"):
    if RICH_AVAILABLE:
        try:
            console.rule(f"[bold {color}]{title}[/bold {color}]")
        except Exception:
            print(f"\n{CYAN}{BOLD}{'='*20} {title} {'='*20}{RESET}")
    else:
        print(f"\n{CYAN}{BOLD}{'='*20} {title} {'='*20}{RESET}")


def print_plan(text: str):
    if not text:
        return
    if RICH_AVAILABLE:
        try:
            console.print(
                Panel(text, title="[bold yellow][PLAN][/bold yellow]",
                      border_style="yellow", box=_BOX_STYLE, padding=(1, 2))
            )
        except Exception:
            print(f"\n{YELLOW}{BOLD}[PLAN]{RESET}")
            print(text)
    else:
        print(f"\n{YELLOW}{BOLD}[PLAN]{RESET}")
        print(text)


def print_command(cmd: str, index: int = 0):
    if RICH_AVAILABLE:
        try:
            lang = "powershell" if any(k in cmd.lower() for k in ["get-", "set-", "invoke-"]) else "bash"
            console.print(
                Panel(
                    Syntax(cmd, lang, theme="monokai", word_wrap=True),
                    title=f"[bold green]CMD [{index+1}][/bold green]",
                    border_style="green",
                    box=_BOX_STYLE,
                    padding=(0, 1),
                )
            )
        except Exception:
            print(f"\n{GREEN}{BOLD}[CMD {index+1}]{RESET} {CYAN}{cmd}{RESET}")
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
        try:
            console.print(
                Panel(
                    Markdown(text),
                    title="[bold magenta]NOTES & NEXT STEPS[/bold magenta]",
                    border_style="magenta",
                    box=_BOX_STYLE,
                    padding=(1, 2),
                )
            )
        except Exception:
            print(f"\n{MAGENTA}{BOLD}[NOTES]{RESET}")
            print(text)
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
        try:
            table = Table(title="Tool Availability", box=_BOX_STYLE)
            table.add_column("Tool", style="cyan")
            table.add_column("Status")
            for tool, ok in sorted(available.items()):
                status = "[green]installed[/green]" if ok else "[red]missing[/red]"
                table.add_row(tool, status)
            console.print(table)
        except Exception:
            print("\n[TOOLS]")
            for tool, ok in sorted(available.items()):
                mark = "[+]" if ok else "[-]"
                print(f"  {mark} {tool}")
    else:
        print("\n[TOOLS]")
        for tool, ok in sorted(available.items()):
            mark = f"{GREEN}[+]{RESET}" if ok else f"{RED}[-]{RESET}"
            print(f"  {mark} {tool}")


def print_workspace_info(target: str, ws_path: str):
    if RICH_AVAILABLE:
        try:
            console.print(
                Panel(
                    f"[cyan]Target:[/cyan] [bold]{target}[/bold]\n"
                    f"[cyan]Workspace:[/cyan] {ws_path}",
                    title="[bold blue]WORKSPACE[/bold blue]",
                    border_style="blue",
                    box=_BOX_STYLE,
                )
            )
        except Exception:
            print(f"\n[WORKSPACE] Target: {target}")
            print(f"  Path: {ws_path}")
    else:
        print(f"\n[WORKSPACE] Target: {target}")
        print(f"  Path: {ws_path}")
