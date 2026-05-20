"""支持 `python -m phone_agent run ...`。"""

from .cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
