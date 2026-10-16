import os

# Tests never call the Claude API; a placeholder key lets the client be constructed.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
