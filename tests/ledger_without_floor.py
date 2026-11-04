# MODULE: ledger_without_floor.py - spend_ledger with the floor and step-back off, so the older tests still pin the count itself (test_round_floor.py pins those two)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "dev-auto" / "scripts"))
import spend_ledger  # noqa: E402

spend_ledger.ROUND_FLOOR = 0
spend_ledger.step_back_problem = lambda *_: None
raise SystemExit(spend_ledger.main(sys.argv[1:]))
