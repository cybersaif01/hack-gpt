"""
Shell detection and cross-platform command execution engine for Hack-GPT
"""

import os
import sys
import platform
import subprocess
import shutil
from typing import Optional, Tuple


def detect_os() -> str:
    """Return 'windows', 'linux', or 'darwin'"""
    s = platform.system().lower()
    if "windows" in s:
        return "windows"
    elif "darwin" in s:
        return "darwin"
    return "linux"


def detect_shell() -> str:
    """Detect the running shell type."""
    os_type = detect_os()
    if os_type == "windows":
        # Check if running inside WSL
        if "microsoft" in platform.uname().release.lower():
            return "bash"
        # Check SHELL env
        shell = os.environ.get("SHELL", "")
        if "bash" in shell or "zsh" in shell:
            return "bash"
        # Check if PowerShell
        if os.environ.get("PSModulePath"):
            return "powershell"
        return "cmd"
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            return "zsh"
        if "fish" in shell:
            return "fish"
        return "bash"


def get_shell_command(command: str, shell_type: str) -> list:
    """Wrap command for the detected shell."""
    if shell_type == "powershell":
        return ["powershell", "-NoProfile", "-Command", command]
    elif shell_type == "cmd":
        return ["cmd", "/c", command]
    elif shell_type in ("bash", "zsh", "fish"):
        sh = shutil.which(shell_type) or "/bin/bash"
        return [sh, "-c", command]
    else:
        # fallback
        if detect_os() == "windows":
            return ["cmd", "/c", command]
        return ["/bin/bash", "-c", command]


def is_tool_available(name: str) -> bool:
    """Check whether a tool is on PATH."""
    return shutil.which(name) is not None


def check_tools(tool_list: list) -> dict:
    """Return availability dict for a list of tools."""
    return {t: is_tool_available(t) for t in tool_list}


def run_command(
    command: str,
    shell_type: str = "auto",
    timeout: int = 300,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    output_file: Optional[str] = None,
    stream: bool = True,
) -> Tuple[int, str, str]:
    """
    Execute a shell command, stream output to stdout, and optionally save to file.
    Returns (returncode, stdout, stderr)
    """
    if shell_type == "auto":
        shell_type = detect_shell()

    cmd_args = get_shell_command(command, shell_type)
    exec_env = os.environ.copy()
    if env:
        exec_env.update(env)

    collected_stdout = []
    collected_stderr = []

    try:
        proc = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=exec_env,
            text=True,
            bufsize=1,
        )

        # Stream stdout
        if stream:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                collected_stdout.append(line)
            for line in proc.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
                collected_stderr.append(line)
        else:
            out, err = proc.communicate(timeout=timeout)
            collected_stdout = [out] if out else []
            collected_stderr = [err] if err else []

        proc.wait(timeout=timeout)
        rc = proc.returncode

    except subprocess.TimeoutExpired:
        proc.kill()
        rc = -1
        collected_stderr.append("Command timed out.\n")
    except FileNotFoundError as e:
        rc = -1
        collected_stderr.append(str(e) + "\n")

    stdout_text = "".join(collected_stdout)
    stderr_text = "".join(collected_stderr)

    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(stdout_text)
            if stderr_text:
                f.write("\n--- STDERR ---\n")
                f.write(stderr_text)

    return rc, stdout_text, stderr_text


def get_system_info() -> dict:
    """Collect system information for AI context."""
    os_type = detect_os()
    shell = detect_shell()

    common_tools = [
        "nmap", "rustscan", "masscan", "naabu",
        "amass", "subfinder", "assetfinder",
        "ffuf", "gobuster", "feroxbuster", "dirsearch",
        "nuclei", "nikto", "sqlmap",
        "hydra", "john", "hashcat",
        "responder", "crackmapexec", "netexec",
        "smbclient", "enum4linux",
        "tcpdump", "wireshark", "tshark",
        "whatweb", "wafw00f", "eyewitness",
        "curl", "wget", "jq",
        "python3", "python", "pip",
        "git", "nc", "netcat",
        "metasploit", "msfconsole",
        "impacket-scripts",
    ]

    available = check_tools(common_tools)
    installed = [t for t, ok in available.items() if ok]

    uname = platform.uname()
    return {
        "os": os_type,
        "platform": uname.system,
        "release": uname.release,
        "machine": uname.machine,
        "shell": shell,
        "python_version": sys.version.split()[0],
        "installed_tools": installed,
        "missing_tools": [t for t, ok in available.items() if not ok],
        "path": os.environ.get("PATH", ""),
    }
