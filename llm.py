"""LLM client: mock (offline) or any OpenAI-compatible endpoint (Nebius Token Factory by default)."""
import json
import os
import urllib.request

DEFAULTS = {
    "mock": {"base_url": "", "model": "mock"},
    # Nebius Token Factory (OpenAI-compatible). Override base/model via env.
    "nebius": {
        "base_url": "https://api.tokenfactory.nebius.com/v1",
        "model": os.environ.get("NEBIUS_MODEL", "NousResearch/Hermes-4-405B"),
    },
    "openai": {"base_url": "https://api.openai.com/v1", "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini")},
}

class LLM:
    def __init__(self, provider=None):
        self.provider = provider or os.environ.get("HERMES_LLM_PROVIDER", "mock")
        cfg = DEFAULTS[self.provider]
        self.base_url = os.environ.get("HERMES_LLM_BASE_URL", cfg["base_url"])
        self.model = os.environ.get("HERMES_LLM_MODEL", cfg["model"])
        self.api_key = os.environ.get("NEBIUS_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

    def complete(self, system, user):
        if self.provider == "mock":
            return self._mock(system, user)
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.3,
            "max_tokens": 400,
        }).encode()
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"]

    @staticmethod
    def _mock(system, user):
        """Deterministic offline stand-in: emits a canon violation once, then a clean answer."""
        if "fix ONLY these canon violations" in user or "Fix ONLY" in system:
            return "Martin (28) shipped the parser today."
        return "Martin (19) shipped the parser today."
