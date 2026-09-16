"""Exercise detected failures, bounded repairs and important false-positive cases."""

import copy
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tutor_checks import CheckFailure, check_response, checked_response, request_facts


def tool(name="edit_file", properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": properties
                or {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": required if required is not None else ["path", "content"],
            },
        },
    }


def answer(text="Here is a useful hint.", calls=None, **extra):
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": text, "tool_calls": calls or []},
        **extra,
    }


def call(content="def example():\n    pass\n", name="edit_file", **args):
    return {
        "id": "action1",
        "function": {
            "name": name,
            "arguments": {"path": "exercise.py", "content": content, **args},
        },
    }


class ResponseChecksTests(unittest.TestCase):
    def setUp(self):
        self.body = {
            "model": "gemma4:e4b-it-qat",
            "messages": [{"role": "user", "content": "Help me start this exercise"}],
            "tools": [tool()],
        }

    def codes(self, response, body=None, mode="tutor"):
        return {
            issue.code for issue in check_response(body or self.body, response, mode)
        }

    def test_whole_file_syntax_and_native_schema(self):
        self.assertEqual(self.codes(answer(calls=[call()])), set())
        self.assertIn(
            "invalid_python_file",
            self.codes(answer(calls=[call("def x():\n    # TODO\n")])),
        )
        bad = call()
        bad["function"]["arguments"].pop("path")
        self.assertIn("invalid_tool_arguments", self.codes(answer(calls=[bad])))
        self.assertIn("unknown_tool", self.codes(answer(calls=[call(name="invented")])))
        bad = call()
        bad["function"]["arguments"] = "{}"
        self.assertIn("malformed_tool_call", self.codes(answer(calls=[bad])))
        bad = call()
        bad["function"]["name"] = []
        self.assertIn("unknown_tool", self.codes(answer(calls=[bad])))
        wrong_role = answer()
        wrong_role["message"]["role"] = "tool"
        self.assertIn("invalid_message", self.codes(wrong_role))

    def test_explanations_and_patch_fragments_are_not_whole_files(self):
        self.assertEqual(
            self.codes(
                answer(
                    "An unfinished block looks like:\n```python\nif ready:\n```\nIndent its body."
                )
            ),
            set(),
        )
        body = copy.deepcopy(self.body)
        body["tools"] = [
            tool(
                "single_find_and_replace",
                {
                    "filepath": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                ["filepath", "old_string", "new_string"],
            )
        ]
        proposed = {
            "function": {
                "name": "single_find_and_replace",
                "arguments": {
                    "filepath": "exercise.py",
                    "old_string": "if ready:",
                    "new_string": "if ready and active:",
                },
            }
        }
        self.assertEqual(self.codes(answer(calls=[proposed]), body), set())

    def test_truncation_empty_and_reminder_only(self):
        self.assertIn("truncated", self.codes(answer(done_reason="length")))
        self.assertIn("empty_reply", self.codes(answer("")))
        self.assertIn(
            "reminder_only",
            self.codes(
                answer(
                    "For a complete solution, select Direct in Continue's model picker."
                )
            ),
        )
        self.assertNotIn(
            "reminder_only",
            self.codes(
                answer(
                    "Use a counter starting at zero. For a complete solution, select Direct in Continue's model picker."
                )
            ),
        )

    def test_claim_requires_corresponding_tool_evidence(self):
        claim = answer("I have replaced the contents of exercise.py.")
        self.assertIn("unsupported_edit_claim", self.codes(claim))
        self.assertIn(
            "unsupported_edit_claim",
            self.codes(answer("I used `edit_file` to create greet.py.")),
        )
        self.assertEqual(
            self.codes(
                answer('The phrase "I have replaced exercise.py" claims an edit.')
            ),
            set(),
        )
        self.assertEqual(
            self.codes(answer("I will replace exercise.py.", calls=[call()])), set()
        )
        self.assertEqual(
            self.codes(
                answer("> I have replaced exercise.py.\nThat statement is a quote.")
            ),
            set(),
        )
        body = copy.deepcopy(self.body)
        body["messages"].append({"role": "assistant", "tool_calls": [call()]})
        for status in [
            "Error: permission denied",
            '{"success":false}',
            "Cancelled by user",
        ]:
            body["messages"].append(
                {"role": "tool", "tool_call_id": "action1", "content": status}
            )
            self.assertIn("unsupported_edit_claim", self.codes(claim, body))
            body["messages"].pop()
        body["messages"].append(
            {"role": "tool", "tool_call_id": "action1", "content": '{"success":true}'}
        )
        self.assertNotIn("unsupported_edit_claim", self.codes(claim, body))
        body["messages"].append({"role": "user", "content": "Now edit a new file"})
        self.assertIn("unsupported_edit_claim", self.codes(claim, body))

    def test_test_run_with_failures_can_be_reported_honestly(self):
        body = copy.deepcopy(self.body)
        body["messages"] += [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "t1",
                        "function": {
                            "name": "run_terminal_command",
                            "arguments": {"command": "pytest"},
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "t1",
                "content": '{"exit_code":1,"output":"1 failed"}',
            },
        ]
        self.assertNotIn(
            "unsupported_test_claim",
            self.codes(answer("I ran the tests and one failed."), body),
        )

    def test_continue_create_file_and_unnamed_single_tool_result(self):
        body = copy.deepcopy(self.body)
        body["tools"] = [
            tool(
                "create_new_file",
                {"filepath": {"type": "string"}, "contents": {"type": "string"}},
                ["filepath", "contents"],
            )
        ]
        proposed = {
            "function": {
                "name": "create_new_file",
                "arguments": {
                    "filepath": "starter.py",
                    "contents": "def work():\n    pass\n",
                },
            }
        }
        self.assertEqual(self.codes(answer(calls=[proposed]), body), set())
        body["messages"] += [
            {"role": "assistant", "content": "", "tool_calls": [proposed]},
            {"role": "tool", "content": "File created successfully"},
        ]
        self.assertEqual(self.codes(answer("I created starter.py."), body), set())
        proposed["function"]["arguments"]["contents"] = "def work():\n"
        self.assertIn("invalid_python_file", self.codes(answer(calls=[proposed]), body))

    def test_request_facts_preserve_mode_and_failed_results(self):
        self.assertIn("mode=TUTOR", request_facts(self.body, "tutor"))
        self.assertIn("current user turn=0", request_facts(self.body, "tutor"))

    def test_repairs_once_without_executing_any_draft(self):
        requests = []
        bad = answer("I have updated exercise.py.")
        good = answer("I will add a scaffold.", calls=[call()])

        def invoke(payload, _deadline):
            requests.append(payload)
            return bad if len(requests) == 1 else good

        original = copy.deepcopy(self.body)
        result, repairs = checked_response(self.body, "tutor", invoke)
        self.assertEqual(self.body, original)
        self.assertEqual(result, good)
        self.assertEqual(repairs, 1)
        self.assertIn("unsupported_edit_claim", requests[1]["messages"][-1]["content"])
        self.assertIn("remains TUTOR", requests[1]["messages"][-1]["content"])
        attempts = []
        with self.assertRaises(CheckFailure):
            checked_response(self.body, "tutor", lambda *_: attempts.append(1) or bad)
        self.assertEqual(len(attempts), 2)

    def test_expired_budget_never_starts_generation(self):
        with self.assertRaises(TimeoutError):
            checked_response(
                self.body,
                "tutor",
                lambda *_: self.fail("Should not invoke"),
                deadline=time.monotonic() - 1,
            )

    def test_reminder_repair_cannot_release_code_or_tools(self):
        reminder = answer(
            "For a complete solution, select Direct in Continue's model picker."
        )
        for replacement in [
            answer("```python\ndef solution():\n    return 42\n```"),
            answer(calls=[call()]),
        ]:
            replies = iter([reminder, replacement])
            with self.assertRaises(CheckFailure) as caught:
                checked_response(self.body, "tutor", lambda *_: next(replies))
            self.assertIn(
                "repair_hint_format", [i.code for i in caught.exception.issues]
            )
        replies = iter(
            [
                reminder,
                answer(
                    "Start by choosing a variable such as `count` to remember how many matching items you have seen."
                ),
            ]
        )
        _, repairs = checked_response(self.body, "tutor", lambda *_: next(replies))
        self.assertEqual(repairs, 1)

    def test_invalid_response_shape_can_be_repaired(self):
        for bad in [[], {"done": True, "message": None}]:
            replies = iter([bad, answer()])
            result, repairs = checked_response(
                self.body, "tutor", lambda *_: next(replies)
            )
            self.assertEqual(result, answer())
            self.assertEqual(repairs, 1)

    def test_local_schema_refs_work(self):
        body = copy.deepcopy(self.body)
        body["tools"][0]["function"]["parameters"] = {
            "$defs": {"text": {"type": "string"}},
            "type": "object",
            "properties": {
                "path": {"$ref": "#/$defs/text"},
                "content": {"$ref": "#/$defs/text"},
            },
            "required": ["path", "content"],
        }
        self.assertEqual(self.codes(answer(calls=[call()]), body), set())
        body["tools"][0]["function"]["parameters"]["properties"]["path"] = {
            "$ref": "https://example.invalid/schema"
        }
        with self.assertRaises(ValueError):
            self.codes(answer(calls=[call()]), body)


if __name__ == "__main__":
    unittest.main()
