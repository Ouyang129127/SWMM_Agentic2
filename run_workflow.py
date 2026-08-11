"""Command-line entry point for SWMM-Agentic2 workflow-stage agents."""

from __future__ import annotations

import argparse

from workflow_agents.orchestrator import run_workflow_stage, workflow_result_to_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SWMM-Agentic2 workflow-stage agents.")
    parser.add_argument("--model", default="songhua_swmm_2d", help="Model project name under models/.")
    parser.add_argument("--run-id", required=True, help="Run ID under models/<model>/runs/.")
    parser.add_argument(
        "--stage",
        default="",
        choices=["", "evidence_building", "diagnosis", "verification"],
        help="Run exactly one stage. Defaults to the next legal stage.",
    )
    parser.add_argument(
        "--until",
        default="",
        choices=["", "evidence_building", "diagnosis", "verification"],
        help="Run legal stages sequentially until this stage is complete.",
    )
    parser.add_argument("--rerun", action="store_true", help="Allow rerunning a stage.")
    args = parser.parse_args()

    result = run_workflow_stage(
        model_name=args.model,
        run_id=args.run_id,
        target_stage=args.stage,
        until_stage=args.until,
        rerun=args.rerun,
    )
    print(workflow_result_to_text(result))


if __name__ == "__main__":
    main()
