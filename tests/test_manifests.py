import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_committed_manifests_match_the_data():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_manifest.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "txt_data.csv: OK (300 questions" in result.stdout
    assert "img_data.csv: OK (400 questions" in result.stdout
