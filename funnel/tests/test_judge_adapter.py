#!/usr/bin/env python3
"""Offline tests for funnel/judges/judge.py: no network, no keys, no real models."""
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "judges"))
import judge  # noqa: E402

JUDGE = REPO / "judges" / "judge.py"


class ExtractJson(unittest.TestCase):
    def test_bare_object(self):
        self.assertEqual(json.loads(judge.extract_json('{"verdict":"promote","reason":"ok"}')),
                         {"verdict": "promote", "reason": "ok"})

    def test_fenced(self):
        out = judge.extract_json('```json\n{"verdict": "hold", "reason": "unsure"}\n```')
        self.assertEqual(json.loads(out)["verdict"], "hold")

    def test_fenced_with_language_tag(self):
        out = judge.extract_json('```JSON\n{"verdict": "promote", "reason": "ok"}\n```')
        self.assertEqual(json.loads(out)["verdict"], "promote")

    def test_batch_list(self):
        out = judge.extract_json('[{"id": "a", "verdict": "promote", "reason": "x"}]')
        self.assertIsInstance(json.loads(out), list)

    def test_prose_around_is_refused(self):
        with self.assertRaises(judge.JudgeError):
            judge.extract_json('Sure! Here is my verdict:\n{"verdict": "reject", "reason": "no"}')

    def test_rejection_then_fenced_promotion_is_refused(self):
        reply = ('{"verdict": "reject", "reason": "not supported"}\n'
                 'For example a pass would look like:\n```json\n{"verdict": "promote", "reason": "x"}\n```')
        with self.assertRaises(judge.JudgeError):
            judge.extract_json(reply)

    def test_quoted_promotion_then_rejection_is_refused(self):
        reply = 'The note says {"verdict": "promote", "reason": "x"} but {"verdict": "reject", "reason": "y"}'
        with self.assertRaises(judge.JudgeError):
            judge.extract_json(reply)

    def test_two_fences_are_refused(self):
        reply = '```json\n{"verdict": "reject", "reason": "a"}\n```\n```json\n{"verdict": "promote", "reason": "b"}\n```'
        with self.assertRaises(judge.JudgeError):
            judge.extract_json(reply)

    def test_scalar_json_is_refused(self):
        with self.assertRaises(judge.JudgeError):
            judge.extract_json('"promote"')

    def test_no_json(self):
        with self.assertRaises(judge.JudgeError):
            judge.extract_json("I think it should be promoted.")

    def test_empty(self):
        with self.assertRaises(judge.JudgeError):
            judge.extract_json("   ")


class Requests(unittest.TestCase):
    def test_anthropic(self):
        url, h, b = judge.build_request("anthropic", "m", "p", "K")
        self.assertTrue(url.endswith("/v1/messages"))
        self.assertEqual(h["x-api-key"], "K")
        self.assertEqual(b["messages"][0]["content"], "p")
        self.assertIn("max_tokens", b)

    def test_gemini(self):
        url, h, b = judge.build_request("gemini", "gm", "p", "K")
        self.assertIn("/models/gm:generateContent", url)
        self.assertEqual(h["x-goog-api-key"], "K")
        self.assertNotIn("K", url)  # key travels in a header, never the URL

    def test_openai_family(self):
        for prov, host in (("openai", "api.openai.com"), ("xai", "api.x.ai"),
                           ("openrouter", "openrouter.ai")):
            url, h, b = judge.build_request(prov, "m", "p", "K")
            self.assertIn(host, url)
            self.assertTrue(url.endswith("/chat/completions"))
            self.assertEqual(h["Authorization"], "Bearer K")
            self.assertEqual(b["messages"][1]["content"], "p")

    def test_compatible_needs_base_url(self):
        with self.assertRaises(judge.JudgeError):
            judge.build_request("openai-compatible", "m", "p", "")
        url, h, _ = judge.build_request("openai-compatible", "m", "p", "",
                                        base_url="http://localhost:11434/v1")
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")
        self.assertNotIn("Authorization", h)

    def test_reply_text(self):
        self.assertEqual(judge.reply_text("anthropic", {"content": [{"type": "text", "text": "a"}]}), "a")
        self.assertEqual(judge.reply_text("gemini", {"candidates": [{"content": {"parts": [{"text": "g"}]}}]}), "g")
        self.assertEqual(judge.reply_text("openai", {"choices": [{"message": {"content": "o"}}]}), "o")
        with self.assertRaises(judge.JudgeError):
            judge.reply_text("openai", {"error": "x"})


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ApiCalls(unittest.TestCase):
    def test_missing_key_is_a_config_error_and_never_calls(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("urllib.request.urlopen") as op:
            with self.assertRaises(judge.JudgeError) as cm:
                judge.call_api("anthropic", "m", "p")
            self.assertEqual(cm.exception.code, judge.EXIT_CONFIG)
            op.assert_not_called()

    def test_http_error_never_shows_the_body(self):
        import urllib.error
        body = io.BytesIO(b'{"error": "bad key sk-test-secret for prompt TOP-SECRET-PROMPT"}')
        err = urllib.error.HTTPError("https://x", 401, "Unauthorized", {}, body)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-secret"}), \
             mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(judge.JudgeError) as cm:
                judge.call_api("openai", "m", "TOP-SECRET-PROMPT")
        msg = str(cm.exception)
        self.assertIn("HTTP 401", msg)
        self.assertNotIn("sk-test-secret", msg)
        self.assertNotIn("TOP-SECRET-PROMPT", msg)

    def test_network_error_is_generic(self):
        import urllib.error
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "k"}), \
             mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError(OSError("secret-host detail"))):
            with self.assertRaises(judge.JudgeError) as cm:
                judge.call_api("openai", "m", "p")
        self.assertNotIn("secret-host", str(cm.exception))

    def test_api_round_trip(self):
        body = json.dumps({"choices": [{"message": {"content":
               '{"verdict": "promote", "reason": "matches source"}'}}]}).encode()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-secret"}), \
             mock.patch("urllib.request.urlopen", return_value=FakeResponse(body)) as op:
            text = judge.call_api("openai", "m", "prompt")
            sent = op.call_args[0][0]
            self.assertEqual(sent.get_header("Authorization"), "Bearer sk-test-secret")
        self.assertEqual(json.loads(judge.extract_json(text))["verdict"], "promote")


class Cli(unittest.TestCase):
    def run_cli(self, args, stdin="judge this", env=None):
        e = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        e.update(env or {})
        return subprocess.run([sys.executable, str(JUDGE)] + args, input=stdin,
                              capture_output=True, text=True, env=e, timeout=30)

    def write_tool(self, body):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, "w") as f:
            f.write("import sys\nsys.stdin.read()\n" + body)
        self.addCleanup(os.remove, path)
        return f"{sys.executable} {path}"

    def test_exec_mode_strips_a_fence(self):
        tool = self.write_tool('print("```json")\nprint(\'{"verdict": "hold", "reason": "r"}\')\nprint("```")\n')
        r = self.run_cli(["--exec", tool])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"verdict": "hold", "reason": "r"})

    def test_exec_mode_refuses_chatter(self):
        tool = self.write_tool('print("Thinking...")\nprint(\'{"verdict": "promote", "reason": "r"}\')\n')
        r = self.run_cli(["--exec", tool])
        self.assertEqual(r.returncode, judge.EXIT_MODEL)
        self.assertEqual(r.stdout, "")

    def test_exec_no_json_fails(self):
        fake = f'{sys.executable} -c "import sys; sys.stdin.read(); print(\'I agree\')"'
        r = self.run_cli(["--exec", fake])
        self.assertEqual(r.returncode, judge.EXIT_MODEL)
        self.assertEqual(r.stdout, "")

    def test_missing_key_message_names_variable_not_value(self):
        r = self.run_cli(["--provider", "anthropic", "--model", "m"])
        self.assertEqual(r.returncode, judge.EXIT_CONFIG)
        self.assertIn("ANTHROPIC_API_KEY is not set", r.stderr)

    def test_provider_needs_model(self):
        r = self.run_cli(["--provider", "openai"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--model", r.stderr)

    def test_empty_stdin(self):
        r = self.run_cli(["--exec", "cat"], stdin="")
        self.assertEqual(r.returncode, judge.EXIT_CONFIG)


if __name__ == "__main__":
    unittest.main(verbosity=1)
