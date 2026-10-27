"""``python -I -m as_engine.bridge``: the hosted engine's process (D-299). The contract is
as_engine.host.bridge (HOST-24..HOST-27) and as_engine.host (the whole of hosting)."""

from __future__ import annotations

if __name__ == "__main__":
    import sys

    from .host.bridge import main
    sys.exit(main())
