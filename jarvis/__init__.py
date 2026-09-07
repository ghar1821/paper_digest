"""
jarvis — a personal assistant over your own notes, papers and drafts.

This module exists to switch off third-party telemetry before anything else
imports the libraries that read these settings. Every entry point in
pyproject.toml is a `jarvis.*` module, so importing this package always happens
first — which matters for HF_HUB_DISABLE_TELEMETRY in particular, because
huggingface_hub reads it at import time and never looks again.

Each variable is set only when it is unset, so a deliberate override on the
command line still wins. Chroma's own telemetry knob is not here: it is a
constructor argument rather than an environment variable, and is passed where
the client is built (jarvis/kb/store.py).
"""

import os

# huggingface_hub reports library usage back to Hugging Face by default. The
# embedding and re-ranking models are pulled from there, so this would report
# every jarvis install that ever loaded one.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

# LangSmith tracing ships with LangChain and is off unless one of these is set.
# Pinning it means a variable exported for some other project cannot quietly
# start sending this one's prompts and retrieved chunks to a hosted service.
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
