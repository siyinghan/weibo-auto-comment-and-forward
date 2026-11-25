import os
import sys
from pathlib import Path

if __name__ == "__main__":
    # Make conf/, resources/ and log/ work regardless of the current directory.
    os.chdir(Path(__file__).resolve().parent)

    from core.runner import main

    sys.exit(main())
