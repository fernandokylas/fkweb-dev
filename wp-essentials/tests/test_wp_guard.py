"""Tests for hooks/wp_guard.py, run as a subprocess the way Claude Code runs it."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "hooks" / "wp_guard.py"


def run_guard(stdin_text):
    proc = subprocess.run([sys.executable, "-B", str(GUARD)], input=stdin_text, capture_output=True, text=True, timeout=20)
    return proc.returncode, proc.stdout


def bash(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class AskTests(unittest.TestCase):
    COMMANDS = [
        "wp plugin delete hello",
        "wp @live search-replace a b",
        "wp --path=/x db reset --yes",
        'docker compose run --rm cli eval "x"',
        "wp post delete 5 --force",
        "wp config set WP_DEBUG true",
        "wp media regenerate --delete-unknown --yes",
        "wp core update",
        "wp user set-role 2 administrator",
        # quoted, path-prefixed and separate-value forms
        'ssh live "wp db reset --yes"',
        "bash -c 'wp plugin delete hello'",
        "./wp-cli.phar db drop --yes",
        "/usr/local/bin/wp theme delete twentytwenty",
        "php wp-cli.phar eval 'echo 1;'",
        "wp --path /var/www/html db reset --yes",
        # --dry-run must belong to the same command and be the exact flag
        "wp search-replace a b\nwp option get home --dry-run",
        "wp search-replace a b --dry-run-later",
        "wp option update siteurl https://example.test",
        "wp package install foo/bar",
    ]

    def test_asks(self):
        for cmd in self.COMMANDS:
            with self.subTest(cmd=cmd):
                code, out = run_guard(bash(cmd))
                self.assertEqual(code, 0)
                spec = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(spec["hookEventName"], "PreToolUse")
                self.assertEqual(spec["permissionDecision"], "ask")
                self.assertTrue(spec["permissionDecisionReason"].strip())

    def test_chained_command_still_caught(self):
        code, out = run_guard(bash("cd /srv && wp plugin delete hello"))
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_reason_names_the_risk(self):
        _, out = run_guard(bash("wp db reset --yes"))
        self.assertIn("database", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])


class SilentTests(unittest.TestCase):
    def assert_silent(self, stdin_text):
        code, out = run_guard(stdin_text)
        self.assertEqual((code, out), (0, ""))

    def test_safe_commands(self):
        for cmd in ["wp option get blogname", "wp plugin list", "wp search-replace a b --dry-run",
                    "wp search-replace a b \\\n  --dry-run", "wp --path /x plugin list", 'ssh live "wp option get home"',
                    "wp option update blogname Bakery", "echo evaluate", 'git commit -m "fix"']:
            with self.subTest(cmd=cmd):
                self.assert_silent(bash(cmd))

    def test_non_bash_tool(self):
        self.assert_silent(json.dumps({"tool_name": "Edit", "tool_input": {"command": "wp plugin delete x"}}))

    def test_malformed_input(self):
        self.assert_silent("{not json")
        self.assert_silent("")
        self.assert_silent("[]")

    def test_empty_or_non_string_command(self):
        self.assert_silent(bash(""))
        self.assert_silent(json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}}))
        self.assert_silent(json.dumps({"tool_name": "Bash"}))


if __name__ == "__main__":
    unittest.main()
