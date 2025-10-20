## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import sys
import joyfl.api as J
from joyfl.types import Stack, nil


def test_stack_type_and_accessors():
    # Test Stack type is accessible
    assert hasattr(J, 'Stack')
    assert hasattr(J, 'nil')
    
    # Test stack construction and accessors
    stack = J.to_stack([1, 2, 3])
    assert isinstance(stack, Stack)
    
    # Test head and tail properties (note: list [1,2,3] becomes stack with 1 on top)
    assert stack.head == 1  # top of stack
    assert stack.tail.head == 2
    assert stack.tail.tail.head == 3
    assert stack.tail.tail.tail.head is None  # empty
    
    # Test that Stack is a namedtuple
    assert hasattr(stack, 'tail')
    assert hasattr(stack, 'head')
    assert stack[0] == stack.tail
    assert stack[1] == stack.head
    
    # Test nil properties
    assert J.nil.head is None
    assert J.nil.tail is None


def test_stack_memory_efficiency():
    # Stack should be a compact 56-byte namedtuple
    assert sys.getsizeof(J.nil) == 56
    assert sys.getsizeof(J.to_stack([1])) == 56
    assert sys.getsizeof(J.to_stack([1, 2, 3, 4, 5])) == 56
    
    # All stacks are the same size regardless of depth
    empty = J.nil
    deep = J.to_stack(list(range(100)))
    assert sys.getsizeof(empty) == sys.getsizeof(deep)


def test_stack_empty_checks():
    # Empty check: head is None
    assert J.nil.head is None
    assert J.to_stack([]).head is None
    
    # Non-empty stacks
    stack = J.to_stack([42])
    assert stack.head is not None
    assert stack.head == 42


def test_stack_construction():
    # Direct construction
    s1 = Stack(nil, 5)
    assert s1.head == 5
    assert s1.tail is nil
    
    # Nested construction
    s2 = Stack(s1, 10)
    assert s2.head == 10
    assert s2.tail.head == 5
    
    # Via to_stack
    s3 = J.to_stack([1, 2, 3])
    assert J.from_stack(s3) == [1, 2, 3]


def test_stack_tuple_compatibility():
    # Stack is a namedtuple, so tuple operations work
    stack = J.to_stack([7, 8])
    
    # Indexing (tail, head)
    assert stack[0].head == 8  # tail contains bottom element
    assert stack[1] == 7  # head is top element
    
    # Unpacking
    tail, head = stack
    assert head == 7  # top
    assert tail.head == 8  # bottom
    
    # Length
    assert len(stack) == 2
    assert len(J.nil) == 2  # Always 2 fields (tail, head)

