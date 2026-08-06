#!/usr/bin/env python3
"""Trap 15 probe: can this endpoint do choice-logprob scoring at all?

Choice-logprob MMLU scoring needs the log-probability of a *given* continuation,
which over an OpenAI-compatible API means /v1/completions with echo=true and
logprobs set, or an equivalent prompt-logprobs field. This records what the lane
actually returns, so the scoring-path decision rests on a measurement rather
than on an assumption about the stack.
"""
import json, sys
import requests

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "qwen36"
S = requests.Session()

def show(name, path, body):
    print("=" * 70)
    print("PROBE:", name)
    print("POST", path, json.dumps(body)[:300])
    try:
        r = S.post(URL + path, json=body, timeout=120)
        print("HTTP", r.status_code)
        txt = r.text
        print("BODY:", txt[:1200])
        if r.status_code == 200:
            j = r.json()
            ch = (j.get("choices") or [{}])[0]
            print("  choices[0].logprobs =", json.dumps(ch.get("logprobs"))[:400])
            print("  prompt_logprobs     =", json.dumps(j.get("prompt_logprobs"))[:400])
    except Exception as e:
        print("EXCEPTION", type(e).__name__, str(e)[:300])
    print()

PROMPT = "The capital of France is"

show("completions echo+logprobs, max_tokens=0 (the choice-logprob shape)",
     "/v1/completions",
     {"model": MODEL, "prompt": PROMPT + " Paris", "max_tokens": 0,
      "echo": True, "logprobs": 1, "temperature": 0})

show("completions echo+logprobs, max_tokens=1",
     "/v1/completions",
     {"model": MODEL, "prompt": PROMPT, "max_tokens": 1,
      "echo": True, "logprobs": 1, "temperature": 0})

show("completions prompt_logprobs extension",
     "/v1/completions",
     {"model": MODEL, "prompt": PROMPT + " Paris", "max_tokens": 1,
      "prompt_logprobs": 1, "temperature": 0})

show("chat completions logprobs (generated tokens only, NOT choice scoring)",
     "/v1/chat/completions",
     {"model": MODEL, "messages": [{"role": "user", "content": "Say A"}],
      "max_tokens": 4, "logprobs": True, "top_logprobs": 5, "temperature": 0})
