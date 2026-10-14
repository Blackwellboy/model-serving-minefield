"""Exact synthetic wire templates shared by preview and probe implementation."""
def validation_requests(model):
    base = {"model": model or "default", "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0, "max_tokens": 16}
    return [base, {**base, "__minefield_unvalidated_field_probe__": "minefield"}]
