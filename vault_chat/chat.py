"""
CLI chat tool that connects an Obsidian vault to a local Ollama model
using native tool calling.

Configuration:
  MODEL      — Ollama model name to use
  VAULT_PATH — Path to the root of the Obsidian vault
"""

import sys
from pathlib import Path

import ollama

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL = "gemma4:26b"
VAULT_PATH = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("~/vault").expanduser()

# ── Tool definition ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full contents of a file from the Obsidian vault. "
                "Use this whenever you need the actual content of a note, "
                "the glossary, or the reading list before answering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file within the vault, e.g. 'to-read.md' or 'notes/paper.md'",
                    }
                },
                "required": ["path"],
            },
        },
    }
]

# ── Vault helpers ─────────────────────────────────────────────────────────────


def build_file_index(vault: Path) -> str:
    """Walk the vault and return a plain-text index of all .md files."""
    lines = ["Available files in vault:"]
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        lines.append(f"  {rel}")
    return "\n".join(lines)


def read_file(vault: Path, rel_path: str) -> str:
    """Read a vault file by relative path. Returns an error string if not found."""
    target = (vault / rel_path).resolve()
    # Guard against path traversal outside the vault
    try:
        target.relative_to(vault.resolve())
    except ValueError:
        return f"[Error: '{rel_path}' is outside the vault]"
    if not target.exists() or not target.is_file():
        return f"[Error: file not found: '{rel_path}']"
    return target.read_text(encoding="utf-8")


def build_system_prompt(vault: Path) -> str:
    """Load SKILL.md and append the file index so the model knows what exists."""
    skill_path = vault / "system" / "SKILL.md"
    if skill_path.exists():
        base = skill_path.read_text(encoding="utf-8").rstrip()
    else:
        base = "You are a knowledgeable assistant with access to an Obsidian vault."

    file_index = build_file_index(vault)
    return f"{base}\n\n{file_index}"


# ── Agentic loop ──────────────────────────────────────────────────────────────


def run_agentic_turn(
    client: ollama.Client,
    history: list[dict],
    vault: Path,
) -> str:
    """
    Send history to the model and execute any tool calls in a loop.
    Returns the final plain-text response.
    """
    while True:
        response = client.chat(
            model=MODEL,
            messages=history,
            tools=TOOLS,
            format=None,
        )
        message = response["message"]

        # No tool call — this is the final answer
        if not message.get("tool_calls"):
            reply = message["content"]
            history.append({"role": "assistant", "content": reply})
            return reply

        # Append the assistant's tool-call message to history
        history.append(message)

        # Execute each tool call and append the results
        for tool_call in message["tool_calls"]:
            fn = tool_call["function"]
            if fn["name"] == "read_file":
                path_arg = fn["arguments"].get("path", "")
                result = read_file(vault, path_arg)
            else:
                result = f"[Error: unknown tool '{fn['name']}']"

            history.append({"role": "tool", "content": result})


# ── Main session loop ─────────────────────────────────────────────────────────


def main() -> None:
    if not VAULT_PATH.exists():
        print(f"Error: vault path does not exist: {VAULT_PATH}", file=sys.stderr)
        sys.exit(1)

    client = ollama.Client()
    system_prompt = build_system_prompt(VAULT_PATH)

    history: list[dict] = [{"role": "system", "content": system_prompt}]

    print(f"Vault chat ready. Model: {MODEL}  Vault: {VAULT_PATH}")
    print("Type your question and press Enter. Ctrl-C or Ctrl-D to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})

        try:
            answer = run_agentic_turn(client, history, VAULT_PATH)
        except ollama.ResponseError as exc:
            print(f"[Ollama error: {exc}]")
            continue

        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()
