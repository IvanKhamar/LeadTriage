"""Exports the workflows from the running n8n into n8n/workflows/, cleaned for a public repository.

    uv run python tools/export_workflows.py

Uses the n8n CLI inside the container (`n8n export:workflow`), then keeps only what is needed to import the workflow
again. Dropped: pinData (pinned test data may hold real messages), staticData, meta (instance id), shared (owner and
project names), timestamps and version counters (noise in diffs). Credential references (id + name) stay; their
values never leave n8n's encrypted store. tests/test_workflows.py checks the result.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "n8n" / "workflows"
KEEP = ("id", "name", "description", "active", "nodes", "connections", "settings", "tags")
CONTAINER_DIR = "/tmp/leadtriage-export"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def clean(workflow: dict) -> dict:
    cleaned = {key: workflow[key] for key in KEEP if key in workflow and workflow[key] not in (None, "")}
    cleaned["tags"] = [{"name": tag["name"]} for tag in workflow.get("tags") or []]
    if not cleaned["tags"]:
        del cleaned["tags"]
    return cleaned


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    run("docker", "compose", "exec", "-T", "n8n", "sh", "-c", f"rm -rf {CONTAINER_DIR} && mkdir -p {CONTAINER_DIR}")
    run(
        "docker",
        "compose",
        "exec",
        "-T",
        "n8n",
        "n8n",
        "export:workflow",
        "--all",
        "--separate",
        "--output",
        CONTAINER_DIR,
    )
    with tempfile.TemporaryDirectory() as tmp:
        run("docker", "compose", "cp", f"n8n:{CONTAINER_DIR}/.", tmp)
        run("docker", "compose", "exec", "-T", "n8n", "rm", "-rf", CONTAINER_DIR)
        for path in sorted(Path(tmp).glob("*.json")):
            workflow = json.loads(path.read_text(encoding="utf-8"))
            if workflow.get("isArchived"):
                continue
            out = TARGET / f"{slug(workflow['name'])}.json"
            out.write_text(json.dumps(clean(workflow), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"exported {out.relative_to(ROOT)}")
    print("Now run: uv run pytest tests/test_workflows.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
