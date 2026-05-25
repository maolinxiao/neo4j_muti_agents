from pathlib import Path
import sys


vendor_path = Path(__file__).resolve().parents[1] / "_vendor"
if vendor_path.exists():
    sys.path.insert(0, str(vendor_path))
