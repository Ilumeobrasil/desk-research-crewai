import sys
import builtins

_original_print = builtins.print

def _safe_print_patch(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except AttributeError:
        pass


builtins.print = _safe_print_patch

def safe_print(msg: str) -> None:
    try:
        if hasattr(sys, '__stdout__') and sys.__stdout__:
            sys.__stdout__.write(str(msg) + "\n")
        else:
            print(msg)
    except Exception:
        pass


