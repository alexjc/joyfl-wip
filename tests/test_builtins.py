import joyfl.api as J


def test_stack_on_empty_stack_returns_empty_list():
    stack = J.run("stack .")
    assert J.from_stack(stack) == [[]]


def test_stack_on_non_empty_stack_returns_list_representation():
    stack = J.run("1 2 stack .")
    top = J.from_stack(stack)[0]
    assert top == [2, 1]
