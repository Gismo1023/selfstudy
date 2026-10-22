"""pytest가 프로젝트 루트에서 `from src import ...`를 찾을 수 있도록 경로 추가."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
