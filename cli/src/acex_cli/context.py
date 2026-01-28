import json
from pathlib import Path

CONTEXT_FILE = Path.home() / ".acex/.acex_cli_context.json"

class CLIContext:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if CONTEXT_FILE.exists():
            with open(CONTEXT_FILE) as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        return {}

    def save(self):
        CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONTEXT_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def set_context(self, name, url, **kwargs):
        url = url.rstrip("/")
        ctxs = self.data.setdefault("contexts", {})
        ctxs[name] = {"url": url, **kwargs}
        self.data["active_context"] = name
        self.save()

    def set_active(self, name):
        self.data["active_context"] = name
        self.save()

    def get_active_context(self):
        name = self.data.get("active_context")
        return self.data.get("contexts", {}).get(name)

    def get_active_url(self):
        ctx = self.get_active_context()
        if ctx:
            return ctx.get("url")
        return None
