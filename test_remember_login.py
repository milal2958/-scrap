import ast
import hashlib
import secrets
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

from remember_login import (
    REMEMBER_SECONDS, derive_key, issue_token, read_token, credentials_match,
)


class Halt(BaseException):
    pass


class RememberLoginTests(unittest.TestCase):
    def setUp(self):
        self.key = derive_key("server-only-test-secret")
        self.password = hashlib.sha256(b"test-password").hexdigest()
        self.token = issue_token(self.key, "12345", self.password, now=1000)

    def test_restore_and_expiry(self):
        payload = read_token(self.key, self.token, now=1001)
        self.assertTrue(credentials_match(self.key, payload, {"12345": self.password}))
        self.assertIsNone(read_token(self.key, self.token, now=1000 + REMEMBER_SECONDS))

    def test_tampering_wrong_key_and_malformed_tokens(self):
        for token in ("", "broken", "x" * 3000, None, self.token[:-1] + "x"):
            self.assertIsNone(read_token(self.key, token, now=1001))
        self.assertIsNone(read_token(derive_key("other-server"), self.token, now=1001))

    def test_password_change_and_deleted_user_invalidate_token(self):
        payload = read_token(self.key, self.token, now=1001)
        self.assertFalse(credentials_match(self.key, payload, {"12345": "new-hash"}))
        self.assertFalse(credentials_match(self.key, payload, {}))

    def test_token_contains_no_password_hash_and_is_unique(self):
        import base64
        body = self.token.split(".")[0]
        decoded = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
        self.assertNotIn(self.password, decoded)
        self.assertNotEqual(self.token, issue_token(self.key, "12345", self.password, now=1000))

    def app_functions(self, state, browser):
        # Exercise the real login flow without contacting production Google Sheets.
        module = ast.parse(Path("app.py").read_text(encoding="utf-8"))
        selected = [node for node in module.body if isinstance(node, ast.FunctionDef)
                    and node.name in ("login", "queue_login_cookie", "clear_login")]
        st = SimpleNamespace(session_state=state, stop=Mock(side_effect=Halt),
                             rerun=Mock(side_effect=Halt), warning=Mock(),
                             subheader=Mock(), container=MagicMock(), markdown=Mock(),
                             text_input=Mock(side_effect=["12345", "test-password"]),
                             checkbox=Mock(return_value=True),
                             form_submit_button=Mock(return_value=True), error=Mock())
        ns = dict(st=st, secrets=secrets, time=time, REMEMBER_SECONDS=REMEMBER_SECONDS,
                  read_token=read_token, credentials_match=credentials_match,
                  issue_token=issue_token, hash_password=lambda value: hashlib.sha256(value.encode()).hexdigest(),
                  _login_cookie=Mock(return_value=browser),
                  login_signing_key=lambda: self.key,
                  connect_google_sheet_client=lambda: object(),
                  user_credentials=lambda client: {"12345": self.password})
        exec(compile(ast.Module(body=selected, type_ignores=[]), "app.py", "exec"), ns)
        return ns

    def test_new_browser_session_restores_authenticated_user(self):
        token = issue_token(self.key, "12345", self.password)
        state = {}
        ns = self.app_functions(state, {"token": token, "ack": None, "error": False})
        self.assertTrue(ns["login"]())
        self.assertEqual(state["user_id"], "12345")

    def test_waits_for_cookie_hydration_and_write_ack(self):
        for state, browser in (({}, None),
                               ({"login_cookie_command": {"id": "new"}}, {"ack": "old"})):
            ns = self.app_functions(state, browser)
            with self.assertRaises(Halt):
                ns["login"]()
            ns["st"].stop.assert_called_once()
            self.assertNotIn("logged_in", state)

    def test_cookie_ack_finishes_login(self):
        state = {"logged_in": True, "user_id": "12345",
                 "login_cookie_command": {"id": "new", "value": "token"}}
        ns = self.app_functions(state, {"ack": "new", "token": "token", "error": False})
        self.assertTrue(ns["login"]())
        self.assertNotIn("login_cookie_command", state)

    def test_manual_login_remember_selected_and_opt_out(self):
        for remember in (True, False):
            state = {}
            ns = self.app_functions(state, {"ack": None, "token": "", "error": False})
            ns["st"].checkbox.return_value = remember
            with self.assertRaises(Halt):
                ns["login"]()
            self.assertTrue(state["logged_in"])
            token = state["login_cookie_command"]["value"]
            if remember:
                self.assertEqual(read_token(self.key, token)["user"], "12345")
            else:
                self.assertEqual(token, "")

    def test_wrong_password_never_creates_token(self):
        state = {}
        ns = self.app_functions(state, {"token": "", "ack": None})
        ns["st"].text_input.side_effect = ["12345", "wrong-password"]
        self.assertFalse(ns["login"]())
        self.assertFalse(state["logged_in"])
        self.assertNotIn("login_cookie_command", state)

    def test_changed_password_cookie_is_deleted_without_login(self):
        state = {}
        ns = self.app_functions(state, {"token": issue_token(self.key, "12345", "old-hash")})
        with self.assertRaises(Halt):
            ns["login"]()
        self.assertFalse(state["logged_in"])
        self.assertEqual(state["login_cookie_command"]["value"], "")

    def test_sheet_outage_does_not_authenticate_from_cookie(self):
        state = {}
        ns = self.app_functions(state, {"token": issue_token(self.key, "12345", self.password)})
        ns["user_credentials"] = Mock(side_effect=RuntimeError("unavailable"))
        ns["st"].form_submit_button.return_value = False
        self.assertFalse(ns["login"]())
        self.assertFalse(state["logged_in"])

    def test_logout_clears_cached_data_and_queues_cookie_deletion(self):
        state = {"logged_in": True, "user_id": "12345", "raw_df": "private",
                 "main_data_editor": "old edits"}
        ns = self.app_functions(state, None)
        ns["clear_login"]()
        self.assertFalse(state["logged_in"])
        self.assertTrue(state["login_restore_attempted"])
        self.assertEqual(state["login_cookie_command"]["value"], "")
        self.assertEqual(state["login_cookie_command"]["expires"], 0)
        self.assertNotIn("user_id", state)
        self.assertNotIn("raw_df", state)
        self.assertNotIn("main_data_editor", state)


if __name__ == "__main__":
    unittest.main()
