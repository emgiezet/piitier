"""Root conftest.py — adds the project root to sys.path.

This allows ``eval.*``, ``training.*``, etc. to be imported in tests without
needing PYTHONPATH to be set externally.  The ``src/`` directory is already on
the path via the editable install; only the root is added here.
"""

import sys
from pathlib import Path

# Insert once so that `import eval`, `import eval.baselines`, etc. work.
_root = str(Path(__file__).parent.resolve())
if _root not in sys.path:
    sys.path.insert(0, _root)
