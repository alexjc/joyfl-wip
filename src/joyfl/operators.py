## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import math
from typing import Any, TypeVar
from fractions import Fraction

from .types import Stack
from .errors import JoyAssertionError
from .formatting import stack_to_list, list_to_stack, format_item


num = int | float | Fraction

## ARITHMETIC
def op_add(b: num, a: num) -> num: return b + a
def op_sub(b: num, a: num) -> num: return b - a
def op_neg(x: num) -> num: return -x
def op_abs(x: num) -> num: return abs(x)
def op_sign(x: num) -> num: return (x > 0) - (x < 0)
def op_min(b: num, a: num) -> num: return min(b, a)
def op_max(b: num, a: num) -> num: return max(b, a)
def op_mul(b: num, a: num) -> num: return b * a
def op_div(b: num, a: num) -> num: return b / a
def op_rem(b: num, a: num) -> num: return b % a
def op_equal_q(b: Any, a: Any) -> bool: return b == a
def op_differ_q(b: Any, a: Any) -> bool: return b != a
## BOOLEAN LOGIC
def op_gt(b: num, a: num) -> bool: return b > a
def op_gte(b: num, a: num) -> bool: return b >= a
def op_lt(b: num, a: num) -> bool: return b < a
def op_lte(b: num, a: num) -> bool: return b <= a
def op_and(b: bool, a: bool) -> bool: return b and a
def op_or(b: bool, a: bool) -> bool: return b or a
def op_not(x: bool) -> bool: return not x
def op_xor(b: Any, a: Any) -> Any: return b ^ a
## DATA & INTROSPECTION
def op_null_q(x: Any) -> bool: return (len(x) if isinstance(x, (list, str)) else x) == 0
def op_small_q(x: Any) -> bool: return (len(x) if isinstance(x, (list, str)) else x) < 2
def op_sametype_q(b: Any, a: Any) -> bool: return type(b) == type(a)
def op_integer_q(x: Any) -> bool: return isinstance(x, int)
def op_float_q(x: Any) -> bool: return isinstance(x, float)
def op_list_q(x: Any) -> bool: return isinstance(x, list)
def op_string_q(x: Any) -> bool: return isinstance(x, str)
def op_boolean_q(x: Any) -> bool: return isinstance(x, bool)
## LIST MANIPULATION
def op_cons(b: Any, a: list) -> list: return [b] + a
def op_append(b: Any, a: list) -> list: return a + [b]
def op_remove(b: list, a: Any) -> list: return [x for x in b if x != a]
def op_take(b: list, a: int) -> list: return b[:a]
def op_drop(b: list, a: int) -> list: return b[a:]
def op_uncons(x: list) -> tuple[Any, list]: return (x[0], x[1:])
def op_concat(b: list, a: list) -> list: return b + a
def op_reverse(x: list) -> list: return list(reversed(x))
def op_first(x: list) -> Any: return x[0]
def op_rest(x: list) -> list: return x[1:]
def op_last(x: list) -> Any: return x[-1]
def op_index(b: int, a: list) -> Any: return a[int(b)]
def op_member_q(b: Any, a: list | dict | set) -> bool: return b in a
def op_length(x: Any) -> int: return len(x)
def op_sum(x: list) -> num: return sum(x)
def op_product(x: list) -> num: return math.prod(x)
# STACK OPERATIONS
X, Y = (TypeVar(v, bound=Any) for v in ('X', 'Y'))
def op_swap(b: Y, a: X) -> tuple[X, Y]: return (a, b)
def op_dup(x: X) -> tuple[X, X]: return (x, x)
def op_pop(_: Any) -> None: return None
def op_stack(s: Stack) -> list: return stack_to_list(s)
def op_unstack(x: list) -> tuple: return list_to_stack(x)
def op_stack_size(s: Stack) -> int: return len(stack_to_list(s))
# INPUT/OUTPUT
def op_id(x: Any) -> Any: return x
def op_put_b(x: Any) -> None:
    text = x if isinstance(x, str) else format_item(x, width=120)
    print('\033[97m' + text + '\033[0m')
def op_assert_b(x: bool) -> None:
    if not x: raise JoyAssertionError
def op_raise_b(x: Any) -> None: raise x
# STRING MANIPULATION
def op_str_concat(b: str, a: str) -> str: return str(b) + str(a)
def op_str_contains_q(b: str, a: str) -> bool: return str(b) in str(a)
def op_str_split(b: str, a: str) -> Any: return a.split(b)
def op_str_cast(x: Any) -> str: return str(x)
def op_str_join(b: list, a: str) -> str: return a.join(b)
# DICTIONARIES (mutable)
def op_dict_new() -> dict: return {}
def op_dict_q(d: dict) -> bool: return isinstance(d, dict)
def op_dict_store(d: dict, k: bytes, v: Any) -> dict: return d.__setitem__(k, v) or d
def op_dict_fetch(d: dict, k: bytes) -> Any: return d[k]

# ERROR ACCESSORS
def op_error_kind(e: Exception) -> str:
    return e.__class__.__name__

def op_error_message(e: Exception) -> str:
    return str(e)

def op_error_data(e: Exception) -> Any:
    data = {}
    if hasattr(e, 'joy_op'): data['joy_op'] = getattr(e, 'joy_op')
    if hasattr(e, 'joy_meta'): data['joy_meta'] = getattr(e, 'joy_meta')
    return data
