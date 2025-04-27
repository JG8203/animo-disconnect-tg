from typing import Tuple, Optional

def parse_course_arg(arg: str) -> Tuple[str, Optional[int]]:
    """Parse a course argument (e.g., "CSOPESY" or "CSOPESY:1234")."""
    arg = arg.upper().strip()
    if ":" not in arg:
        return arg, None

    course, nbr_str = arg.split(":", 1)
    if not nbr_str.isdigit():
        raise ValueError("Class number must be numeric")

    return course, int(nbr_str)
