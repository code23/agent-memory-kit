#!/usr/bin/env python3
"""Ready-made model command for the memory funnel.

Reads a prompt on standard input, asks one model, and prints only the JSON reply on
standard output. Use it for any seat: MEMORY_JUDGE_A_CMD, MEMORY_JUDGE_B_CMD,
MEMORY_TIEBREAK_CMD or MEMORY_EXTRACTOR_CMD.

Two ways to reach a model:

  API:  judge.py --provider anthropic --model <model name>
        Providers: anthropic, openai, gemini, xai, openrouter, openai-compatible.
        The key is read from an environment variable (see KEY_ENV below, or pass
        --key-env). This script never stores, prints or logs a key.

  CLI:  judge.py --exec "claude -p"
        Runs a model's own command-line tool, sends the prompt on its standard input
        and keeps only the JSON from whatever it prints. Use this to judge with a
        subscription you already sign in to, rather than an API key.

Models chatter. Whatever comes back, this script prints exactly one JSON value (the
first JSON object or list in the reply) or exits non-zero. The funnel treats a
non-zero exit as an invalid vote, so a broken seat parks facts for a person instead
of letting them through.

Standard library only. See docs/judges.md and docs/first-real-run.md.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai-compatible": None,  # pass --key-env if your endpoint needs a key
}

BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

SYSTEM = (
    "You are a careful reviewer inside a memory system. Follow the instructions in the "
    "user message exactly. Reply with the JSON those instructions ask for and nothing "
    "else: no explanation, no markdown, no code fences."
)

EXIT_CONFIG = 2   # bad arguments or a missing key
EXIT_MODEL = 3    # the model or tool failed, or its reply held no JSON


class JudgeError(Exception):
    def __init__(self, message, code=EXIT_MODEL):
        super().__init__(message)
        self.code = code


def extract_json(text):
    """Return the first JSON object or list in *text*, re-serialised compactly.

    Handles a bare JSON reply, a reply wrapped in ``` fences, and JSON surrounded by
    prose. Raises JudgeError when there is none.
    """
    s = (text or "").strip()
    if not s:
        raise JudgeError("the model returned an empty reply")
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", s, flags=re.S)
    for chunk in fenced + [s]:
        chunk = chunk.strip()
        try:
            obj = json.loads(chunk)
            if isinstance(obj, (dict, list)):
                return json.dumps(obj, ensure_ascii=False)
        except ValueError:
            pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(s[i:])
        except ValueError:
            continue
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, ensure_ascii=False)
    raise JudgeError("the model's reply held no JSON object or list")


def build_request(provider, model, prompt, key, base_url=None, max_tokens=2048):
    """Return (url, headers, body_dict) for one provider. No network."""
    if provider == "anthropic":
        url = (base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {"model": model, "max_tokens": max_tokens, "system": SYSTEM,
                "messages": [{"role": "user", "content": prompt}]}
    elif provider == "gemini":
        root = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{root}/models/{model}:generateContent"
        headers = {"x-goog-api-key": key}
        body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    elif provider in ("openai", "xai", "openrouter", "openai-compatible"):
        root = base_url or BASE_URL.get(provider)
        if not root:
            raise JudgeError("openai-compatible needs --base-url", EXIT_CONFIG)
        url = root.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        body = {"model": model,
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": prompt}]}
    else:
        raise JudgeError(f"unknown provider '{provider}'", EXIT_CONFIG)
    headers["content-type"] = "application/json"
    return url, headers, body


def reply_text(provider, data):
    """Pull the model's text out of a provider response. Raises JudgeError."""
    try:
        if provider == "anthropic":
            return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        if provider == "gemini":
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # some compatible servers return parts
            return "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content or ""
    except (KeyError, IndexError, TypeError):
        raise JudgeError("unexpected response shape from the provider")


def call_api(provider, model, prompt, key_env=None, base_url=None, timeout=100,
             max_tokens=2048):
    env_name = key_env or KEY_ENV.get(provider)
    key = os.environ.get(env_name, "").strip() if env_name else ""
    if env_name and not key:
        raise JudgeError(f"{env_name} is not set. Set it in your shell or secret store "
                         "before running (never in a file in this kit).", EXIT_CONFIG)
    url, headers, body = build_request(provider, model, prompt, key, base_url, max_tokens)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise JudgeError(f"{provider} returned HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise JudgeError(f"could not reach {provider}: {e.reason}")
    except TimeoutError:
        raise JudgeError(f"{provider} did not answer within {timeout} seconds")
    except ValueError:
        raise JudgeError(f"{provider} returned something that is not JSON")
    return reply_text(provider, data)


def call_exec(command, prompt, timeout=100):
    argv = shlex.split(command)
    if not argv:
        raise JudgeError("--exec needs a command", EXIT_CONFIG)
    try:
        r = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                           timeout=timeout)
    except FileNotFoundError:
        raise JudgeError(f"'{argv[0]}' was not found on PATH", EXIT_CONFIG)
    except subprocess.TimeoutExpired:
        raise JudgeError(f"'{argv[0]}' did not finish within {timeout} seconds")
    if r.returncode != 0:
        raise JudgeError(f"'{argv[0]}' exited {r.returncode}")
    return r.stdout


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="judge.py",
        description="Ask one model for a JSON reply. Prompt on stdin, JSON on stdout.")
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--provider", choices=sorted(KEY_ENV),
                     help="call a provider's API (needs --model and a key in the environment)")
    how.add_argument("--exec", dest="exec_cmd", metavar="COMMAND",
                     help='run a model CLI that reads the prompt on stdin, e.g. "claude -p"')
    ap.add_argument("--model", help="model name, exactly as your provider lists it")
    ap.add_argument("--key-env", help="environment variable holding the key (overrides the default)")
    ap.add_argument("--base-url", help="API root for openai-compatible servers (or to override a provider)")
    ap.add_argument("--timeout", type=int, default=100,
                    help="seconds to wait (default 100; the funnel gives each seat 120)")
    ap.add_argument("--max-tokens", type=int, default=2048, help="reply limit (Anthropic needs one)")
    a = ap.parse_args(argv)
    if a.provider and not a.model:
        ap.error("--provider needs --model (use the exact name from your provider's model list)")
    return a


def main(argv=None):
    a = parse_args(argv)
    prompt = sys.stdin.read()
    if not prompt.strip():
        print("judge.py: no prompt on stdin", file=sys.stderr)
        return EXIT_CONFIG
    try:
        if a.exec_cmd:
            text = call_exec(a.exec_cmd, prompt, a.timeout)
        else:
            text = call_api(a.provider, a.model, prompt, a.key_env, a.base_url,
                            a.timeout, a.max_tokens)
        print(extract_json(text))
        return 0
    except JudgeError as e:
        print(f"judge.py: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
