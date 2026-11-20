import os
import sys

ELASTRO_ART = r"""
```text
      .   *   .       .   *   .      .
    .   _   .   *   .    *    .   *
  _ __| | __ _ ___| |_ _ __ ___    .
  / _ \ |/ _` / __| __| '__/ _ \  *
 |  __/ | (_| \__ \ |_| | | (_) |  .
  \___|_|\__,_|___/\__|_|  \___/ .
      .    *     .      *    .   *
```
"""


def banner_enabled() -> bool:
    """Return True when the CLI ASCII banner should be printed."""
    if os.environ.get("ELASTRO_GUI_MODE") == "1":
        return False
    if os.environ.get("ELASTRO_NO_ART"):
        return False
    try:
        return sys.stdout.isatty()
    except (ValueError, OSError):
        return False


def get_banner() -> str:
    return ELASTRO_ART


def print_banner() -> None:
    if not banner_enabled():
        return
    from rich.console import Console

    console = Console()
    console.print(ELASTRO_ART, style="bold blue")
