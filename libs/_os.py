import glob
from joyfl import api as J


def op_list_files_b(pattern: str) -> list[str]:
    return sorted(glob.glob(pattern, recursive=True))

def op_exec_file_b(filename: str) -> bool:
    res = J.run(open(filename, 'r').read(), filename=filename)
    return res[-1]


__operators__ = [
    op_list_files_b,
    op_exec_file_b,
]