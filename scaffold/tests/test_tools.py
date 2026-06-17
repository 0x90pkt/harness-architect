import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness.tools import Tool, ToolRegistry, ToolError, SideEffect  # noqa: E402
from harness.providers import ToolCall  # noqa: E402


def echo(args):
    return f"echo:{args['msg']}"


echo_tool = Tool(
    name="echo", description="echo a message", handler=echo,
    parameters={"type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"], "additionalProperties": False},
)


class TestTools(unittest.TestCase):
    def setUp(self):
        self.reg = ToolRegistry([echo_tool])

    def call(self, name, args):
        return self.reg.execute(ToolCall(id="x", name=name, arguments=args))

    def test_happy_path(self):
        r = self.call("echo", {"msg": "hi"})
        self.assertFalse(r.is_error)
        self.assertEqual(r.content, "echo:hi")

    def test_missing_required(self):
        r = self.call("echo", {})
        self.assertTrue(r.is_error)
        self.assertIn("missing required parameter 'msg'", r.content)

    def test_wrong_type(self):
        r = self.call("echo", {"msg": 123})
        self.assertTrue(r.is_error)
        self.assertIn("must be of type string", r.content)

    def test_unexpected_param(self):
        r = self.call("echo", {"msg": "hi", "extra": 1})
        self.assertTrue(r.is_error)
        self.assertIn("unexpected parameter 'extra'", r.content)

    def test_unknown_tool(self):
        r = self.call("nope", {})
        self.assertTrue(r.is_error)
        self.assertIn("Unknown tool", r.content)
        self.assertIn("echo", r.content)  # lists available

    def test_enum(self):
        t = Tool(name="pick", description="pick", handler=lambda a: a["c"],
                 parameters={"type": "object",
                             "properties": {"c": {"type": "string", "enum": ["a", "b"]}},
                             "required": ["c"]})
        reg = ToolRegistry([t])
        r = reg.execute(ToolCall("x", "pick", {"c": "z"}))
        self.assertTrue(r.is_error)
        self.assertIn("must be one of", r.content)

    def test_bool_rejected_for_integer(self):
        t = Tool(name="n", description="n", handler=lambda a: str(a["i"]),
                 parameters={"type": "object",
                             "properties": {"i": {"type": "integer"}},
                             "required": ["i"]})
        reg = ToolRegistry([t])
        self.assertTrue(reg.execute(ToolCall("x", "n", {"i": True})).is_error)
        self.assertFalse(reg.execute(ToolCall("x", "n", {"i": 5})).is_error)

    def test_tool_error_is_actionable(self):
        def bad(_):
            raise ToolError("date must be YYYY-MM-DD")
        reg = ToolRegistry([Tool(name="d", description="d", handler=bad,
                                 parameters={"type": "object", "properties": {}})])
        r = reg.execute(ToolCall("x", "d", {}))
        self.assertTrue(r.is_error)
        self.assertIn("YYYY-MM-DD", r.content)

    def test_unexpected_exception_does_not_crash(self):
        def boom(_):
            raise ValueError("kaboom")
        reg = ToolRegistry([Tool(name="b", description="b", handler=boom,
                                 parameters={"type": "object", "properties": {}})])
        r = reg.execute(ToolCall("x", "b", {}))
        self.assertTrue(r.is_error)
        self.assertIn("kaboom", r.content)

    def test_destructive_denied_by_default(self):
        t = Tool(name="del", description="delete", handler=lambda a: "deleted",
                 parameters={"type": "object", "properties": {}},
                 side_effect=SideEffect.DESTRUCTIVE)
        reg = ToolRegistry([t])
        r = reg.execute(ToolCall("x", "del", {}))
        self.assertTrue(r.is_error)
        self.assertIn("not approved", r.content)

    def test_destructive_allowed_with_approval(self):
        t = Tool(name="del", description="delete", handler=lambda a: "deleted",
                 parameters={"type": "object", "properties": {}},
                 side_effect=SideEffect.DESTRUCTIVE)
        reg = ToolRegistry([t])
        r = reg.execute(ToolCall("x", "del", {}), approve=lambda tool, args: True)
        self.assertFalse(r.is_error)
        self.assertEqual(r.content, "deleted")

    def test_truncation(self):
        big = Tool(name="big", description="big", handler=lambda a: "z" * 100000,
                   parameters={"type": "object", "properties": {}},
                   max_response_tokens=100)
        reg = ToolRegistry([big])
        r = reg.execute(ToolCall("x", "big", {}))
        self.assertIn("truncated", r.content)
        self.assertLess(len(r.content), 100000)

    def test_duplicate_registration(self):
        with self.assertRaises(ValueError):
            ToolRegistry([echo_tool, echo_tool])


if __name__ == "__main__":
    unittest.main()
