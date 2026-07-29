import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambdas"))
sys.path.insert(0, str(ROOT / "client"))

# update_check reads these at import time; boto3 clients are created but never
# hit the network in tests (all AWS calls are patched).
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("PINS_TABLE", "test-pins")
os.environ.setdefault("RELEASES_TABLE", "test-releases")
os.environ.setdefault("RELEASES_BUCKET", "test-releases-bucket")
