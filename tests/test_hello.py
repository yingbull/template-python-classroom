"""Example practice tests; instructors replace or extend these per assignment."""

from examples.hello import greeting


def test_greeting():
    assert greeting("Ada") == "Hello, Ada!"
