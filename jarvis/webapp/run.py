"""Entry point for `uv run webapp`."""

import argparse
import os


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(
        prog="webapp",
        description="Jarvis web UI — starts a local server at http://127.0.0.1:8080.",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "anthropic", "openrouter"],
        help=(
            "Provider for new sessions. Overrides config and CHAT_PROVIDER. "
            "Each session can then switch model from the picker."
        ),
    )
    args = parser.parse_args()

    # Set the env var before uvicorn imports jarvis.webapp.app, so get_config()
    # picks it up when the module is first loaded (get_config is a process-wide
    # singleton).
    if args.provider:
        os.environ["CHAT_PROVIDER"] = args.provider

    # Print what was actually loaded before serving anything. Almost every
    # setup problem is "jarvis is not reading the config I think it is", and
    # the resolved values answer that in one glance. Secrets are reduced to
    # set/not set by describe().
    from jarvis.core.config import format_describe

    print("Jarvis configuration" + format_describe() + "\n")

    # Check the knowledge-base server before uvicorn takes over the terminal.
    # The webapp is a long-lived reader, so it must never fall back to opening
    # the index files itself — that is the fault the server exists to remove.
    # Failing here, with the command to run, beats a stack trace on the first
    # search half an hour into a conversation.
    _require_kb_server()

    # A backend change needs the process restarted to be picked up. Static
    # files are served from disk on every request, so those only ever need a
    # browser reload.
    uvicorn.run("jarvis.webapp.app:app", host="127.0.0.1", port=8080)


def _require_kb_server() -> None:
    """Exit with the fix if the knowledge-base server is not answering."""
    import sys

    from jarvis.core.config import get_config
    from jarvis.kb.store import _server_client

    try:
        _server_client(get_config().server_port)
    except Exception as exc:
        print(
            "\n✗ The knowledge-base server is not running, and the webapp needs it.\n"
            "  Start it in another terminal (or tmux):  uv run kb server\n"
            f"  ({exc})",
            file=sys.stderr,
        )
        sys.exit(1)
