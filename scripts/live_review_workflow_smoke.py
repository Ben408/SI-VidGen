"""Exercise the live local review workflow without calling Higgsfield."""

from __future__ import annotations

from fastapi.testclient import TestClient

from config.settings import get_settings
from src.api.app import create_app

SAMPLE_ISSUE = (
    "A business user needs to reverse a posted General Ledger journal entry "
    "that was entered directly in General Ledger. Create a short instructional "
    "video showing how to find the journal transaction, open it, select Reverse, "
    "choose the reversal date, add an audit-trail description, and complete the "
    "reversal. Explain why the Reverse button might not appear for an entry "
    "created in another application."
)


def main() -> int:
    client = TestClient(create_app(get_settings()))
    created = client.post(
        "/api/runs",
        json={
            "text": SAMPLE_ISSUE,
            "module": "General Ledger",
            "auto_generate": False,
        },
    )
    created.raise_for_status()
    run_id = created.json()["run_id"]

    result = client.get(f"/api/runs/{run_id}")
    result.raise_for_status()
    run = result.json()
    if run["status"] != "completed":
        raise RuntimeError(f"Pipeline failed: {run}")

    script_response = client.get(f"/api/runs/{run_id}/script")
    script_response.raise_for_status()
    script = script_response.json()
    if not script["scenes"] or not all(
        scene["source_ids"] for scene in script["scenes"]
    ):
        raise RuntimeError("Generated script contains an ungrounded scene")
    if "reverse journal" not in run["sources"][0]["title"].lower():
        raise RuntimeError(f"Top source is not the reversal topic: {run['sources'][0]}")
    script_text = " ".join(
        [
            script["title"],
            script["narration"],
            *[scene["voiceover"] for scene in script["scenes"]],
        ]
    ).lower()
    if "reverse" not in script_text:
        raise RuntimeError("Generated script does not explain journal reversal")
    top_source_id = run["sources"][0]["source_id"]
    if not any(top_source_id in scene["source_ids"] for scene in script["scenes"]):
        raise RuntimeError("Generated script did not cite the highest-relevance source")

    script["title"] = f"{script['title']} — reviewed"
    edit_response = client.put(
        f"/api/runs/{run_id}/script",
        json={
            "title": script["title"],
            "narration": script["narration"],
            "scenes": script["scenes"],
        },
    )
    edit_response.raise_for_status()
    edited = edit_response.json()
    if edited["script_version"] != 2 or edited["review_status"] != "draft":
        raise RuntimeError(f"Unexpected edited run state: {edited}")

    approval = client.post(
        f"/api/runs/{run_id}/approve",
        json={"generate_video": False},
    )
    approval.raise_for_status()
    approved = approval.json()
    if approved["review_status"] != "approved":
        raise RuntimeError(f"Approval failed: {approved}")

    print(f"run_id={run_id}")
    print(f"feature={approved['classification']['feature']}")
    print(f"confidence={approved['classification']['confidence']}")
    print(f"sources={len(approved['sources'])}")
    print(f"scenes={len(script['scenes'])}")
    print(f"script_version={approved['script_version']}")
    print(f"review_status={approved['review_status']}")
    print(f"generation_status={approved['generation_status']}")
    print(f"script_path={approved['script_path']}")
    print(f"payload_path={approved['payload_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
