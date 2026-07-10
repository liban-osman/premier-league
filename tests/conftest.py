import sys
from pathlib import Path

# scripts/ is a plain folder, not a package -- put it on the path so tests
# can import the modules under test directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
