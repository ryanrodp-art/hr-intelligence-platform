import subprocess
import sys

print("Running Phase 1 DeepEval evaluation suite...")

result = subprocess.run(
    ["deepeval", "test", "run", "evaluation/tests/test_chat.py", "-v"],
    text=True,
)

print(result.stdout)
if result.stderr:
    print(result.stderr)

sys.exit(result.returncode)
