"""
AI engine for Hack-GPT — handles OpenAI API calls, system prompt construction,
command extraction, and response parsing.
"""

import re
import json
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from hackgpt.config import load_config
from hackgpt.shell_utils import get_system_info


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(sys_info: dict) -> str:
    installed = ", ".join(sys_info.get("installed_tools", [])) or "none detected"
    missing = ", ".join(sys_info.get("missing_tools", [])) or "all tools present"
    is_root_user = sys_info.get("is_root", False)
    root_note = " (Running as ROOT — no sudo needed)" if is_root_user else ""

    return f"""You are Hack-GPT, an advanced cybersecurity CLI AI assistant.

## ENVIRONMENT
- OS: {sys_info['platform']} {sys_info['release']} ({sys_info['os']}){root_note}
- Shell: {sys_info['shell']}
- Python: {sys_info['python_version']}
- INSTALLED tools (ALREADY available — DO NOT install these): {installed}
- MISSING tools (not on PATH — install ONLY these if needed): {missing}

## CRITICAL TOOL RULE
NEVER output install commands for tools that appear in the INSTALLED list above.
Only suggest installing a tool if it is explicitly in the MISSING list.
If a tool is installed, use it directly — no apt/pip/gem install needed.

## ROLE
Senior Red Team Operator | Pentest Workflow Orchestrator | SOC/DFIR Analyst

## AUTHORIZED SCOPE
Only operate within: TryHackMe, HackTheBox, VulnHub, Docker labs, local VMs, authorized pentest environments.
REFUSE: unauthorized hacking, malware deployment, credential theft, DDoS, ransomware, data destruction.

## RESPONSE FORMAT (STRICT)
When you need to run commands, output them in this EXACT format:

<hackgpt-plan>
Brief explanation of what you're about to do.
</hackgpt-plan>

<hackgpt-commands>
command1
command2
command3
</hackgpt-commands>

<hackgpt-notes>
Findings, next steps, recommendations.
</hackgpt-notes>

RULES:
1. Commands must be valid for the detected OS/shell.
2. One command per line inside <hackgpt-commands>.
3. If saving output to file, use shell redirection (e.g., nmap ... > output.txt or tee output.txt).
4. ONLY include install commands for tools in the MISSING list. NEVER reinstall installed tools.
5. For destructive/dangerous operations, add a comment: # CONFIRM_REQUIRED
6. Always use the workspace structure: ~/hackgpt-workspace/<target>/<category>/
7. If no commands needed (just answering a question), omit the command blocks entirely.
8. For Windows PowerShell, use PowerShell-compatible syntax.
9. For Linux/bash, use bash-compatible syntax.
10. Chain commands logically for maximum efficiency.
{f'11. Running as ROOT — do NOT prefix commands with sudo.' if is_root_user else ''}

## CYBERSECURITY TOOLS COVERAGE
You have expertise with ALL major cybersecurity tools including:
- Recon: nmap, rustscan, masscan, naabu, amass, subfinder, assetfinder, theHarvester, recon-ng, shodan, censys
- Web: ffuf, gobuster, feroxbuster, dirsearch, nikto, whatweb, wafw00f, wfuzz, arjun, hakrawler, gau
- Exploitation: metasploit, msfconsole, msfvenom, searchsploit, sqlmap, xsstrike, commix
- Password: hydra, medusa, hashcat, john, crackmapexec, netexec, kerbrute
- Network: wireshark, tshark, tcpdump, responder, bettercap, ettercap, arpspoof
- OSINT: maltego, spiderfoot, osintframework, twint, sherlock, holehe
- Wireless: aircrack-ng, wifite, kismet, airodump-ng
- Forensics: volatility, autopsy, binwalk, foremost, exiftool, strings
- Privilege Escalation: linpeas, winpeas, pspy, gtfobins, lse.sh
- Active Directory: bloodhound, sharphound, impacket, ldapdomaindump, mimikatz
- Post-Exploitation: empire, covenant, sliver, cobalt-strike, chisel, ligolo
- Cloud: pacu, scoutsuite, prowler, cloudmapper, trivy
- Container: docker, kubectl, hadolint, dive, kube-hunter
- Mobile: apktool, jadx, frida, objection, drozer, mobsf
- Crypto: openssl, hashid, hash-identifier, cyberchef
- Steganography: steghide, stegsolve, zsteg, outguess

## PENTEST WORKFLOW
1. Validate target → Create workspace → Passive recon
2. Active enumeration → Service identification
3. Vulnerability scanning → Correlation
4. Report generation → Next actions

## WORKSPACE STRUCTURE
~/hackgpt-workspace/<target>/recon/ scans/ web/ smb/ creds/ screenshots/ loot/ exploits/ reports/ logs/ notes/

## REPORTING
Generate markdown reports with: Executive Summary, Scope, Open Ports, Services, Technologies, Vulnerabilities, CVEs, Evidence, Risk Levels, Exploitation Notes, Remediation, Next Steps.

Be direct, technical, efficient. Minimal fluff. Execute autonomously within authorized scope."""


# ─────────────────────────────────────────────────────────────────────────────
# Command Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_commands(text: str) -> list:
    """Extract commands from <hackgpt-commands> blocks."""
    pattern = r"<hackgpt-commands>(.*?)</hackgpt-commands>"
    matches = re.findall(pattern, text, re.DOTALL)
    commands = []
    next_needs_confirm = False
    for block in matches:
        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if "CONFIRM_REQUIRED" in line:
                    next_needs_confirm = True  # tag the NEXT command
                continue
            # Attach confirm flag as metadata prefix (parsed later)
            if next_needs_confirm:
                commands.append("__CONFIRM__" + line)
                next_needs_confirm = False
            else:
                commands.append(line)
    return commands


def extract_plan(text: str) -> str:
    """Extract plan section."""
    pattern = r"<hackgpt-plan>(.*?)</hackgpt-plan>"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_notes(text: str) -> str:
    """Extract notes/recommendations section."""
    pattern = r"<hackgpt-notes>(.*?)</hackgpt-notes>"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


# Commands that require confirmation even without CONFIRM_REQUIRED tag
_ALWAYS_CONFIRM_PATTERNS = [
    # Brute-force / credential attacks
    r"\bhydra\b",
    r"\bmedusa\b",
    r"\bthc-hydra\b",
    r"\bncrack\b",
    r"\bhashcat\b",
    r"\bjohn\b.*--wordlist",
    r"\bcrack\b.*password",
    r"\bpassword.spray",
    r"\bbruteforc",
    # Exploitation
    r"\bmsfconsole\b",
    r"\bmetasploit\b",
    r"\bmsfvenom\b",
    r"\bexploit\b.*--target",
    r"\bpayload\b.*lhost",
    # Destructive file operations
    r"\brm\s+(-[^\s]*f[^\s]*|-[^\s]*r[^\s]*)\s+",  # rm -rf, rm -fr, etc.
    r"\brmdir\b.*/[sq]",
    r"\bdel\s+/[fqs]",
    r"\bformat\s+[a-zA-Z]:",
    r"\bshred\b",
    r"\bwipe\b",
    r"\bdd\b.*of=/dev",
    # Network disruption
    r"\bresponder\b",
    r"\barpspoof\b",
    r"\bethercap\b",
    r"\bhping3\b.*--flood",
    # Privilege escalation helpers
    r"\bsudo\s+(-i|bash|sh|zsh|su)\b",
    r"\bchmod\s+[0-9]*7[0-9]*\s+/etc",
    r"\bcrontab\s+-[el]",
    # Sqlmap with high aggression
    r"\bsqlmap\b.*--level=[3-5]",
    r"\bsqlmap\b.*--risk=[2-3]",
    r"\bsqlmap\b.*--os-shell",
    r"\bsqlmap\b.*--file-write",
    # wget/curl writing to system paths
    r"(?:wget|curl).*-[oO]\s+/(?:etc|bin|usr|sbin|boot)",
    # Netcat / reverse shells
    r"\b(?:nc|netcat|ncat)\b.*-[el].*(?:\d{4,5}|/bin/(?:bash|sh))",
    r"/bin/(?:bash|sh)\s+-i",
    r"\bbash\s+-i\b",
]


def needs_confirmation(command: str) -> bool:
    """Determine if a command needs user confirmation before running."""
    # Strip the internal marker prefix before checking
    cmd = command.removeprefix("__CONFIRM__")
    if command.startswith("__CONFIRM__"):
        return True  # AI explicitly flagged it
    cmd_lower = cmd.lower()
    for p in _ALWAYS_CONFIRM_PATTERNS:
        if re.search(p, cmd_lower):
            return True
    return False


def strip_confirm_marker(command: str) -> str:
    """Remove the internal __CONFIRM__ prefix before execution."""
    return command.removeprefix("__CONFIRM__")


# ─────────────────────────────────────────────────────────────────────────────
# AI Client
# ─────────────────────────────────────────────────────────────────────────────

def _parse_retry_delay(error_body) -> float:
    """Extract retry-after seconds from a 429 error response."""
    try:
        # OpenAI-style: error.message contains "retry in Xs"
        import re as _re
        msg = str(error_body)
        m = _re.search(r"retry[^\d]+(\d+(?:\.\d+)?)\s*s", msg, _re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return 30.0  # safe default


def _is_daily_quota_exhausted(error_body) -> bool:
    """Return True if this is a daily (non-recoverable until midnight) quota error."""
    msg = str(error_body).lower()
    return any(k in msg for k in (
        "per_day", "perday", "daily", "quota_exceeded",
        "free_tier_requests", "resource_exhausted",
    ))


def _build_quota_error_message(error_body, model: str, api_base: str) -> str:
    """Build a human-friendly quota error message with actionable advice."""
    is_daily = _is_daily_quota_exhausted(error_body)
    retry_s  = _parse_retry_delay(error_body)

    lines = [
        "",
        "  QUOTA / RATE LIMIT ERROR",
        f"  Model    : {model}",
        f"  Provider : {api_base}",
        "",
    ]

    if is_daily and "generativelanguage" in api_base:
        lines += [
            "  [!] Your Gemini FREE TIER daily quota is EXHAUSTED.",
            "      Free tier resets at midnight Pacific Time (PST/PDT).",
            "",
            "  Options right now:",
            "  1. Switch model (separate quota bucket):",
            "       hackgpt --config set model gemini-1.5-flash",
            "       hackgpt --config set model gemini-2.0-flash-lite",
            "",
            "  2. Switch to Groq (completely free, generous limits):",
            "       hackgpt --provider groq --key gsk_...",
            "       Get key: https://console.groq.com/keys",
            "",
            "  3. Enable billing on Google AI Studio for higher quotas:",
            "       https://aistudio.google.com/app/billing",
            "",
            "  4. Wait until midnight PST for free tier reset.",
        ]
    elif "generativelanguage" in api_base:
        lines += [
            f"  [!] Per-minute rate limit hit. Auto-retrying in {retry_s:.0f}s...",
            "      (This is temporary — will recover automatically)",
        ]
    else:
        lines += [
            f"  [!] Rate limit hit. Retry in {retry_s:.0f}s.",
            "      Or switch provider: hackgpt --provider groq",
        ]

    return "\n".join(lines)


class HackGPTEngine:
    # Max retries for per-minute 429s (NOT for daily exhaustion)
    MAX_RETRIES = 3
    BASE_BACKOFF = 10  # seconds

    def __init__(self):
        self.cfg = load_config()
        self.sys_info = get_system_info()
        self._client = None

    def _get_client(self):
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )
        if not self.cfg.get("api_key"):
            raise ValueError(
                "No API key configured. Run: hackgpt --config set api_key YOUR_KEY\n"
                "Or set env var: OPENAI_API_KEY=your_key"
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=self.cfg["api_key"],
                base_url=self.cfg.get("api_base", "https://api.openai.com/v1"),
            )
        return self._client

    def _call_api(self, client, full_messages: list, stream: bool) -> str:
        """Single API call — raises on error, returns text on success."""
        if stream:
            response_text = ""
            stream_resp = client.chat.completions.create(
                model=self.cfg["model"],
                messages=full_messages,
                max_tokens=self.cfg.get("max_tokens", 4096),
                temperature=self.cfg.get("temperature", 0.2),
                stream=True,
            )
            for chunk in stream_resp:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    print(delta.content, end="", flush=True)
                    response_text += delta.content
            print()  # newline after stream
            return response_text
        else:
            resp = client.chat.completions.create(
                model=self.cfg["model"],
                messages=full_messages,
                max_tokens=self.cfg.get("max_tokens", 4096),
                temperature=self.cfg.get("temperature", 0.2),
            )
            return resp.choices[0].message.content

    def chat(self, messages: list, stream: bool = True) -> str:
        """
        Send messages to AI with automatic retry on per-minute 429s.
        Raises a clean, human-readable error on daily quota exhaustion.
        """
        import time

        client = self._get_client()
        system_msg = {
            "role": "system",
            "content": build_system_prompt(self.sys_info),
        }
        full_messages = [system_msg] + messages

        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return self._call_api(client, full_messages, stream)

            except Exception as e:
                last_error = e
                err_str = str(e)
                status_code = getattr(e, "status_code", None)

                # ── 429 Rate Limit ──
                if status_code == 429 or "429" in err_str:
                    is_daily = _is_daily_quota_exhausted(err_str)

                    # Daily quota: no point retrying, fail immediately with advice
                    if is_daily:
                        friendly = _build_quota_error_message(
                            err_str,
                            self.cfg["model"],
                            self.cfg.get("api_base", ""),
                        )
                        raise RuntimeError(friendly) from e

                    # Per-minute quota: retry with backoff
                    retry_s = _parse_retry_delay(err_str)
                    wait = max(retry_s, self.BASE_BACKOFF * (2 ** attempt))

                    if attempt < self.MAX_RETRIES:
                        print(
                            f"\n[!] Rate limited. Waiting {wait:.0f}s before retry "
                            f"(attempt {attempt + 1}/{self.MAX_RETRIES})...",
                            flush=True,
                        )
                        time.sleep(wait)
                        continue
                    else:
                        friendly = _build_quota_error_message(
                            err_str,
                            self.cfg["model"],
                            self.cfg.get("api_base", ""),
                        )
                        raise RuntimeError(friendly) from e

                # ── 401 Auth Error ──
                elif status_code == 401 or "401" in err_str or "invalid_api_key" in err_str:
                    provider_hint = ""
                    api_base = self.cfg.get("api_base", "")
                    if "generativelanguage" in api_base:
                        provider_hint = (
                            "\n  Your key starts with 'AIzaSy' — make sure provider is set to gemini:"
                            "\n    hackgpt --provider gemini --key AIzaSy..."
                        )
                    elif "openai" in api_base:
                        provider_hint = (
                            "\n  OpenAI keys start with 'sk-'. Get one at:"
                            "\n    https://platform.openai.com/account/api-keys"
                        )
                    raise RuntimeError(
                        f"\n  AUTHENTICATION FAILED (401)\n"
                        f"  API base : {api_base}\n"
                        f"  Model    : {self.cfg['model']}\n"
                        f"{provider_hint}\n"
                        f"  Run: hackgpt --provider <name> --key <your-key>"
                    ) from e

                # ── Other errors: don't retry ──
                else:
                    raise

        raise last_error  # Should not reach here

    def parse_response(self, text: str) -> dict:
        """Parse AI response into structured components."""
        return {
            "plan": extract_plan(text),
            "commands": extract_commands(text),
            "notes": extract_notes(text),
            "raw": text,
        }
