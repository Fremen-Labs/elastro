from rich.text import Text
from rich.panel import Panel
from rich.align import Align

ELASTRO_ART = r"""
      .   *   .       .   *   .      .
    .   _   .   *   .    *    .   *
  _ __| | __ _ ___| |_ _ __ ___    .
  / _ \ |/ _` / __| __| '__/ _ \  *
 |  __/ | (_| \__ \ |_| | | (_) |  .
  \___|_|\__,_|___/\__|_|  \___/ .
      .    *     .      *    .   *
"""

def get_banner() -> str:
    return ELASTRO_ART

def print_banner():
    from rich.console import Console
    console = Console()
    console.print(ELASTRO_ART, style="bold blue")
