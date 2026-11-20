"""Live check of the NVIDIA endpoint through the app's own provider.
Usage (repo root, key in .env):  .venv/bin/python scripts/test_nvidia.py
"""
from ai_code_review.core.config import load_settings
from ai_code_review.llm.providers import create_provider

s = load_settings(".env" if __import__("os").path.exists(".env") else None)
assert s.provider == "openai-compatible", f"provider is {s.provider!r}; set AICR_* in .env"
assert s.api_key.get_secret_value(), "AICR_API_KEY is empty"
findings = create_provider(s).review(
    'Review code. Reply ONLY with JSON: {"findings": [...]}',
    "def f(u):\n    return eval(u)\n",
)
print(f"OK: {len(findings)} finding(s)")
for f in findings:
    print("-", f)
