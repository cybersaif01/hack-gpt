# Hack-GPT 🔐

> **Advanced Cybersecurity CLI AI Assistant** — like `shell-gpt`, but for pentesting.

```
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗      ██████╗ ██████╗ ████████╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝     ██╔════╝ ██╔══██╗╚══██╔══╝
 ███████║███████║██║     █████╔╝      ██║  ███╗██████╔╝   ██║   
 ██╔══██║██╔══██║██║     ██╔═██╗      ██║   ██║██╔═══╝    ██║   
 ██║  ██║██║  ██║╚██████╗██║  ██╗     ╚██████╔╝██║        ██║   
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝     ╚═════╝ ╚═╝        ╚═╝   
```

## What is Hack-GPT?

Hack-GPT is a **CLI AI assistant for cybersecurity professionals**. You type a natural language command, and it:

1. Sends your prompt to GPT-4
2. The AI decides which tools to run
3. Commands are **actually executed** in your terminal
4. Output is streamed live and saved
5. Findings are stored in an organized workspace

---

## ⚡ Quick Install

```bash
# Clone and install
git clone https://github.com/your-repo/hack-gpt
cd hack-gpt
pip install -e .
```

**That's it.** Now `hackgpt` is a command on your system — Windows CMD, PowerShell, Linux bash, WSL, all work.

---

## 🔑 Setup API Key

```bash
# Option 1: Store in config (recommended)
hackgpt --config set api_key sk-yourOpenAIkey

# Option 2: Environment variable
export OPENAI_API_KEY=sk-yourkey        # Linux/Mac/WSL
set OPENAI_API_KEY=sk-yourkey           # Windows CMD
$env:OPENAI_API_KEY="sk-yourkey"       # PowerShell
```

---

## 🚀 Usage Examples

### Run an Nmap scan and save to file
```
hackgpt -chat "run nmap scan on 10.10.10.5 and save output in output.txt"
```

### Full recon on a target
```
hackgpt -chat "run full recon on 10.10.10.5"
```

### Enumerate SMB shares
```
hackgpt -chat "enumerate smb on 192.168.1.100"
```

### Web fuzzing
```
hackgpt -chat "perform web directory fuzzing on http://target.htb"
```

### Specify target explicitly
```
hackgpt --target 10.10.10.5 -chat "run vulnerability scan"
```

### Save output to file
```
hackgpt -o results.txt -chat "run nmap -sV on 10.10.10.5"
```

### Dry run (show commands, don't execute)
```
hackgpt --no-execute -chat "enumerate ldap on 10.10.10.100"
```

### Interactive REPL mode
```
hackgpt --interactive
```

### Use a specific session (for context continuity)
```
hackgpt --session htb-box1 -chat "run recon on 10.10.11.20"
hackgpt --session htb-box1 -chat "now enumerate web services"
```

### Generate a pentest report
```
hackgpt --report 10.10.10.5
```

### Check installed tools
```
hackgpt --tools
```

---

## ⚙️ Configuration

```bash
hackgpt --config show                          # Show current config
hackgpt --config set model gpt-4o             # Change model
hackgpt --config set api_base https://...     # Use custom API (Ollama, etc.)
hackgpt --config set confirm_destructive true # Confirm dangerous commands
hackgpt --config set workspace_dir /pentest   # Change workspace dir
```

### Use with Ollama (local LLMs)
```bash
hackgpt --config set api_base http://localhost:11434/v1
hackgpt --config set api_key ollama
hackgpt --config set model llama3.2
```

---

## 📁 Workspace Structure

For each target, Hack-GPT automatically creates:

```
~/hackgpt-workspace/10.10.10.5/
├── recon/          # passive recon output
├── scans/          # nmap, nuclei, etc.
├── web/            # ffuf, whatweb, etc.
├── smb/            # enum4linux, smbclient
├── creds/          # discovered credentials
├── screenshots/    # eyewitness, etc.
├── loot/           # files, hashes, keys
├── exploits/       # exploit code
├── reports/        # markdown reports
├── logs/           # all command outputs
└── notes/          # your notes
```

---

## 🛠️ Supported Tools

Hack-GPT knows about and can use:

| Category | Tools |
|----------|-------|
| Port Scanning | nmap, rustscan, masscan, naabu |
| Subdomain Enum | amass, subfinder, assetfinder |
| Web Fuzzing | ffuf, gobuster, feroxbuster, dirsearch |
| Vuln Scanning | nuclei, nikto |
| Web Analysis | whatweb, wafw00f, curl |
| SMB/AD | enum4linux, smbclient, crackmapexec, netexec, bloodhound |
| Password Attacks | hydra, john, hashcat |
| Exploitation | metasploit, sqlmap, impacket |
| Network | tcpdump, tshark, wireshark, responder |
| Scripting | Python, Bash, PowerShell |

---

## 🔒 Safety Policy

Hack-GPT **only operates within**:
- TryHackMe / HackTheBox / VulnHub
- Local VMs and Docker labs
- Explicitly authorized environments

It **refuses**:
- Unauthorized access
- Malware deployment
- Credential theft
- DDoS / ransomware

---

## 📋 All CLI Options

```
hackgpt -chat "PROMPT"          Send prompt and execute commands
hackgpt --interactive           Interactive REPL session
hackgpt --target IP             Set target explicitly
hackgpt --output FILE           Save output to file
hackgpt --session NAME          Use named session for history
hackgpt --no-execute            Dry run — show commands only
hackgpt --no-stream             Disable AI streaming
hackgpt --model MODEL           Override AI model
hackgpt --config show           Show config
hackgpt --config set KEY VAL    Set config value
hackgpt --tools                 Check installed tools
hackgpt --workspaces            List pentest workspaces
hackgpt --report TARGET         Generate pentest report
hackgpt --clear-history         Clear session history
hackgpt --sessions              List saved sessions
hackgpt --version               Show version
```

---

## 📄 License

MIT License — Use responsibly and legally.
