"""
CLI chat tool that connects an Obsidian vault to a local Ollama model.

Configuration:
  MODEL      — Ollama model name to use
  VAULT_PATH — Path to the root of the Obsidian vault
"""

import sys
from pathlib import Path

import ollama

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL = "gemma4:26b"
VAULT_PATH = Path("~/vault").expanduser()

# ── Vault helpers ─────────────────────────────────────────────────────────────


def build_file_index(vault: Path) -> str:
    """Walk the vault and return a plain-text index of all .md files."""
    lines = ["Available files in vault:"]
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        lines.append(f"  {rel}")
    return "\n".join(lines)


def load_file(vault: Path, rel_path: str) -> str | None:
    """Read a vault file by relative path. Returns None if not found."""
    target = (vault / rel_path).resolve()
    # Guard against path traversal outside the vault
    try:
        target.relative_to(vault.resolve())
    except ValueError:
        return None
    if not target.exists() or not target.is_file():
        return None
    return target.read_text(encoding="utf-8")


def load_system_prompt(vault: Path) -> str:
    """Load vault/system/SKILL.md as the system prompt, or use a default."""
    skill_path = vault / "system" / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return (
        "You are a knowledgeable assistant with access to an Obsidian vault. "
        "When you need to read a file to answer a question, output exactly:\n"
        "  READ: path/to/file.md\n"
        "on its own line. Once you have the information you need, answer directly."
    )


# ── Agentic loop ──────────────────────────────────────────────────────────────


def parse_read_request(text: str) -> str | None:
    """Return the path from the first 'READ: path' line found, or None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("READ:"):
            return stripped[len("READ:") :].strip()
    return None


def run_agentic_turn(
    client: ollama.Client,
    history: list[dict],
    vault: Path,
) -> str:
    """
    Send history to the model and handle READ: requests in a loop.
    Returns the final model response (no READ: request present).
    """
    while True:
        response = client.chat(model=MODEL, messages=history)
        reply = response["message"]["content"]

        read_path = parse_read_request(reply)
        if read_path is None:
            # No file request — this is the final answer
            history.append({"role": "assistant", "content": reply})
            return reply

        # Acknowledge the model's request and feed back the file contents
        history.append({"role": "assistant", "content": reply})

        content = load_file(vault, read_path)
        if content is None:
            file_message = f"[File not found: {read_path}]"
        else:
            file_message = f"Contents of {read_path}:\n\n{content}"

        history.append({"role": "user", "content": file_message})


# ── Main session loop ─────────────────────────────────────────────────────────


def main() -> None:
    if not VAULT_PATH.exists():
        print(f"Error: vault path does not exist: {VAULT_PATH}", file=sys.stderr)
        sys.exit(1)

    client = ollama.Client()

    system_prompt = load_system_prompt(VAULT_PATH)
    file_index = build_file_index(VAULT_PATH)

    # Conversation history shared across all turns in this session
    history: list[dict] = [{"role": "system", "content": system_prompt}]

    # Prime the first user message with the file index so the model knows
    # what is available without having to ask.
    index_preamble = (
        f"{file_index}\n\n"
        "Use READ: <path> on its own line whenever you need to see a file's contents."
    )
    history.append({"role": "user", "content": index_preamble})

    # Consume the index message silently (no user question yet)
    response = client.chat(model=MODEL, messages=history)
    history.append({"role": "assistant", "content": response["message"]["content"]})

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
