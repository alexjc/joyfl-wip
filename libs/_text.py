import re

from joyfl.errors import JoyValueError


def op_format(b: list, a: str) -> str:
    # b: list of values; a: template string with %1..%N and %%.
    values = [str(v) for v in b]
    # Validate template only contains legal tokens: %<digits>, %% or non-% chars
    if not re.fullmatch(r'(?:%(\d+)|%%|[^%])+', a):
        raise JoyValueError("Invalid placeholder after '%' (expected digits or '%%').")
    # Range-check numeric placeholders
    for m in re.finditer(r'%(\d+)', a):
        idx = int(m.group(1))
        if idx < 1 or idx > len(values):
            raise JoyValueError(f"Placeholder %{idx} out of range for {len(values)} values.")
    # Translate: first numeric placeholders, then literal percents
    fmt = re.sub(r'%(\d+)', lambda m: '{%d}' % (int(m.group(1)) - 1), a)
    fmt = fmt.replace('%%', '%')
    try:
        return fmt.format(*values)
    except Exception as e:
        raise JoyValueError(f"Invalid format string: {e}")


__operators__ = [op_format]