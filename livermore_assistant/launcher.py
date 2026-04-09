from __future__ import annotations

import sys

from livermore_assistant.app import main


if __name__ == "__main__":
    if "--open-browser" not in sys.argv:
        sys.argv.append("--open-browser")
    main()
