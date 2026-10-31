"""The improvement loop's change step as a MAF workflow (ADR-0001 item 12): attempt, check, then keep or drop.

improvement_loop.py ends at a handoff for the coding agent; this workflow takes one change from it (or any
task) and runs it to a decision. It is MAF's checkpoint_with_human_in_the_loop.py sample
(samples/03-workflows/checkpoint), with Steward as the writer:

    prepare -> Steward -> checks -> (failed, attempts left) repair -> Steward -> checks ...
                                 -> (passed, or attempts spent) review -> keep | drop | guidance -> Steward

* Steward runs as an agent node, so each tool call that needs approval reaches Kyle as a request_info
  event, as in MAF's agents_with_approval_requests.py (samples/03-workflows/human-in-the-loop).
* The checks are the gate's own model-free checks, run as commands, never model-run evals (Kyle,
  2026-10-30). Their result routes on conditional edges, as in MAF's edge_condition.py.
* Kyle's review is a request_info: "keep", "drop", or guidance that sends the change back to Steward.
  Keep leaves the change in the workspace for its pull request through the gate; drop puts back every
  file the attempt changed or created, leaving files that were already changed before it as they were.
* Every superstep is checkpointed to improvement_loop/checkpoints, so a run paused on a review can be
  resumed later from its checkpoint, as in the sample.

Run from worlds/steward:
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\improvement_loop_workflow.py "<task>"
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\improvement_loop_workflow.py --resume <checkpoint id>
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    Content,
    Executor,
    FileCheckpointStorage,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    register_checkpoint_type,
    response_handler,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent as steward  # noqa: E402

_REPO_DIR = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = _REPO_DIR / "improvement_loop" / "checkpoints"
# The gate's model-free legs (.github/workflows/gate.yml): the sample project's tests and the harness checks.
GATE_CHECKS: tuple[tuple[str, ...], ...] = (
    (sys.executable, "-m", "pytest", "-q", "harness/steward/working/sample-project"),
    (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "harness/steward/step04_production_ready/test_harness.py"),
)
MAX_ATTEMPTS = 3
_OUTPUT_TAIL = 3000


def _changed_paths() -> tuple[set[str], set[str]]:
    """(changed tracked files, untracked files) in the workspace, from git status."""
    lines = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "."],
        cwd=steward._WORKING_DIR, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    tracked = {line[3:] for line in lines if not line.startswith("??")}
    untracked = {line[3:] for line in lines if line.startswith("??")}
    return tracked, untracked


@dataclass
class CheckReport:
    """One attempt's check results, routed by the edges after the checks."""

    attempt: int
    passed: bool
    summary: str
    output: str


@dataclass
class ReviewRequest:
    """Kyle's review of a checked attempt (serialised into checkpoints)."""

    prompt: str = ""
    summary: str = ""
    passed: bool = False
    attempt: int = 0
    changed: list[str] = field(default_factory=list)
    output: str = ""


@dataclass
class LoopResult:
    """The workflow's output: what was decided, and which files the attempt touched."""

    decision: str
    passed: bool
    attempts: int
    changed: list[str] = field(default_factory=list)
    summary: str = ""


class PrepareTask(Executor):
    """Records what was already changed in the workspace, then hands Steward the task."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def prepare(self, task: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        tracked, untracked = _changed_paths()
        ctx.set_state("task", task.strip())
        ctx.set_state("before_tracked", sorted(tracked))
        ctx.set_state("before_untracked", sorted(untracked))
        prompt = (
            "Make this change in the workspace, then stop and summarize what you changed. The gate's checks "
            f"run after you.\n\nTASK: {task.strip()}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


class RunChecks(Executor):
    """Runs the checks after each attempt and reports the result."""

    def __init__(self, id: str, checks: Sequence[Sequence[str]]) -> None:
        super().__init__(id=id)
        self._checks = [list(check) for check in checks]
        self._attempt = 0

    @handler
    async def run_checks(self, response: AgentExecutorResponse, ctx: WorkflowContext[CheckReport]) -> None:
        self._attempt += 1
        outputs: list[str] = []
        passed = True
        for check in self._checks:
            done = await asyncio.to_thread(
                subprocess.run, check, cwd=_REPO_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            outputs.append(f"$ {' '.join(check)}\n(exit {done.returncode})\n{(done.stdout + done.stderr)[-_OUTPUT_TAIL:]}")
            passed = passed and done.returncode == 0
        await ctx.send_message(
            CheckReport(self._attempt, passed, response.agent_response.text, "\n\n".join(outputs))
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"attempt": self._attempt}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._attempt = state.get("attempt", 0)


def needs_repair(report: Any) -> bool:
    """Edge condition: the checks failed and attempts are left."""
    return isinstance(report, CheckReport) and not report.passed and report.attempt < MAX_ATTEMPTS


def ready_for_review(report: Any) -> bool:
    """Edge condition: the checks passed, or the attempts are spent."""
    return isinstance(report, CheckReport) and (report.passed or report.attempt >= MAX_ATTEMPTS)


class AskForRepair(Executor):
    """Sends the failing checks back to Steward."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def ask(self, report: CheckReport, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        prompt = (
            f"The checks failed after attempt {report.attempt} of {MAX_ATTEMPTS}. Fix the cause, then stop and "
            f"summarize what you changed.\n\nCheck output:\n{report.output}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


class ReviewGateway(Executor):
    """Kyle's review: keep, drop, or guidance back to Steward (the sample's ReviewGateway)."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def on_report(self, report: CheckReport, ctx: WorkflowContext) -> None:
        tracked, untracked = _changed_paths()
        before = set(ctx.get_state("before_tracked") or []) | set(ctx.get_state("before_untracked") or [])
        await ctx.request_info(
            request_data=ReviewRequest(
                prompt="Reply 'keep', 'drop', or guidance for another attempt.",
                summary=report.summary,
                passed=report.passed,
                attempt=report.attempt,
                changed=sorted((tracked | untracked) - before),
                output=report.output,
            ),
            response_type=str,
        )

    @response_handler
    async def on_review(
        self, original_request: ReviewRequest, reply: str, ctx: WorkflowContext[AgentExecutorRequest, LoopResult]
    ) -> None:
        decision = reply.strip()
        if decision.lower() in {"keep", "drop"}:
            if decision.lower() == "drop":
                self._drop(ctx)
            await ctx.yield_output(
                LoopResult(
                    decision=decision.lower(), passed=original_request.passed, attempts=original_request.attempt,
                    changed=original_request.changed, summary=original_request.summary,
                )
            )
            return
        prompt = f"Kyle reviewed attempt {original_request.attempt}. Revise the change: {decision}"
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )

    def _drop(self, ctx: WorkflowContext[Any, Any]) -> None:
        """Put back what the attempt changed: tracked files to HEAD, new files removed; earlier changes stay."""
        tracked, untracked = _changed_paths()
        restore = sorted(tracked - set(ctx.get_state("before_tracked") or []))
        if restore:
            subprocess.run(
                ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", *restore],
                cwd=steward._WORKING_DIR, check=True,
            )
        for path in sorted(untracked - set(ctx.get_state("before_untracked") or [])):
            (steward._WORKING_DIR / path).unlink(missing_ok=True)


def create_workflow(agent: Any, checkpoint_storage: FileCheckpointStorage, checks: Sequence[Sequence[str]] = GATE_CHECKS) -> Workflow:
    """The loop's graph, the same for a new run and for a resume."""
    register_checkpoint_type(CheckReport)
    register_checkpoint_type(ReviewRequest)
    register_checkpoint_type(LoopResult)
    attempt = AgentExecutor(agent, id="steward")
    prepare = PrepareTask(id="prepare", agent_id="steward")
    checks_executor = RunChecks(id="checks", checks=checks)
    repair = AskForRepair(id="repair", agent_id="steward")
    review = ReviewGateway(id="review", agent_id="steward")
    return (
        WorkflowBuilder(
            # Each attempt is about four supersteps; this leaves room for MAX_ATTEMPTS and two reviews.
            max_iterations=40,
            start_executor=prepare,
            checkpoint_storage=checkpoint_storage,
            output_from=[review],
        )
        .add_edge(prepare, attempt)
        .add_edge(attempt, checks_executor)
        .add_edge(checks_executor, repair, condition=needs_repair)
        .add_edge(checks_executor, review, condition=ready_for_review)
        .add_edge(repair, attempt)
        .add_edge(review, attempt)  # Kyle's guidance loops back
        .build()
    )


def _answer(request_id: str, data: Any) -> Any:
    """Ask Kyle in the console: a tool approval (y/n) or the review (keep, drop or guidance)."""
    if isinstance(data, Content) and data.type == "function_approval_request" and data.function_call is not None:
        print(f"\n=== Approval: {data.function_call.name} {data.function_call.arguments} ===")
        return data.to_function_approval_response(approved=input("Approve? (y/n): ").strip().lower() == "y")
    if isinstance(data, ReviewRequest):
        print(f"\n=== Review: attempt {data.attempt}, checks {'passed' if data.passed else 'failed'} ===")
        print(data.summary, "\nChanged:", ", ".join(data.changed) or "(nothing)", "\n" + data.output[-1500:])
        return input(data.prompt + " ").strip()
    raise ValueError(f"Unexpected request {request_id}: {type(data).__name__}")


async def run_loop(workflow: Workflow, *, task: str | None = None, checkpoint_id: str | None = None) -> LoopResult:
    """Run until the review decides, answering each request in the console (the sample's interactive session)."""
    responses: dict[str, Any] | None = None
    while True:
        if responses:
            events = await workflow.run(responses=responses)
        elif task is not None:
            events = await workflow.run(task)
        else:
            events = await workflow.run(checkpoint_id=checkpoint_id)
        if outputs := events.get_outputs():
            return outputs[0]
        requests = events.get_request_info_events()
        if not requests:
            raise RuntimeError("The workflow stopped without a decision or a request.")
        responses = {request.request_id: _answer(request.request_id, request.data) for request in requests}


async def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(_REPO_DIR / ".env")
    resume = len(sys.argv) == 3 and sys.argv[1] == "--resume"
    if not resume and len(sys.argv) != 2:
        raise SystemExit(__doc__)
    storage = FileCheckpointStorage(storage_path=CHECKPOINT_DIR)
    async with AsyncExitStack() as stack:
        agent = await stack.enter_async_context(await steward.build_steward_agent(stack))
        workflow = create_workflow(agent, storage)
        if resume:
            result = await run_loop(workflow, checkpoint_id=sys.argv[2])
        else:
            result = await run_loop(workflow, task=sys.argv[1])
    print(f"\nDecision: {result.decision} after {result.attempts} attempt(s); checks {'passed' if result.passed else 'failed'}.")
    print("Changed:", ", ".join(result.changed) or "(nothing)")


if __name__ == "__main__":
    asyncio.run(main())
