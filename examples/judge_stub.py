#!/usr/bin/env python3
"""Offline stand-in for a judge command. Makes NO model call and needs no key.

A real judge command reads the prompt on stdin and prints the model's JSON reply on
stdout. Replace this with a script that calls your provider, reading its API key from
an environment variable (never from a file in this repo). The reply shape the funnel
expects for a single item is:

    {"verdict": "promote" | "reject" | "hold", "reason": "<short reason>"}

For batched prompts it expects a JSON list of {"id", "verdict", "reason"} objects.
This stub promotes everything it is asked about, which is only useful for a dry run.
"""
import json
import re
import sys

prompt = sys.stdin.read()
ids = re.findall(r"=== ITEM \w+ id=(\S+) ===", prompt)
if ids:
    print(json.dumps([{"id": i, "verdict": "promote", "reason": "stub judge"} for i in ids]))
else:
    print(json.dumps({"verdict": "promote", "reason": "stub judge"}))
