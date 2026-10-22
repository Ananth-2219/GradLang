"""Allow 'python -m gradlang' to invoke the compiler CLI."""
import sys
from .compiler import main_cli

sys.exit(main_cli())
