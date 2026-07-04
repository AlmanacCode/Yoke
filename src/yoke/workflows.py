"""Yoke-owned workflow orchestration."""

from __future__ import annotations

from yoke.models import Agent, Harness, Step, StepResult, Workflow, WorkflowRun
from yoke.options import WorkflowOptions


async def run_workflow(
    harness: Harness,
    workflow: Workflow,
    prompt: str,
    options: WorkflowOptions,
) -> WorkflowRun:
    """Run a workflow over provider harness calls.

    This is deliberately provider-neutral orchestration. It does not claim the
    provider has a native workflow primitive.
    """

    results: list[StepResult] = []
    outputs: dict[str, str] = {}
    for step in workflow.steps:
        missing = [name for name in step.depends_on if name not in outputs]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"workflow step {step.name!r} has unmet dependencies: {names}")
        step_harness = harness_for_step(harness, step)
        rendered = render_prompt(step, prompt, outputs)
        run = await step_harness.run(rendered)
        output = run.output or ""
        outputs[step.name] = output
        results.append(StepResult(step=step.name, run=run))
    final = results[-1].run.output if results else None
    return WorkflowRun(
        workflow=workflow.name,
        steps=tuple(results),
        output=final,
    )


def harness_for_step(harness: Harness, step: Step) -> Harness:
    """Return the harness used for a workflow step."""

    if step.agent in ("", "main", "root"):
        return harness
    try:
        agent = harness.agent.subagents[step.agent]
    except KeyError as exc:
        raise ValueError(f"workflow step {step.name!r} references unknown agent {step.agent!r}") from exc
    return harness.model_copy(update={"agent": merge_agent(harness.agent, agent)})


def merge_agent(root: Agent, child: Agent) -> Agent:
    """Fill small child-agent gaps from the root agent."""

    return child.model_copy(
        update={
            "model": child.model or root.model,
            "effort": child.effort or root.effort,
        }
    )


def render_prompt(step: Step, prompt: str, outputs: dict[str, str]) -> str:
    """Render a workflow step prompt with simple context."""

    context = {"input": prompt, **outputs}
    try:
        return step.prompt.format(**context)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(
            f"workflow step {step.name!r} prompt references unknown value {missing!r}"
        ) from exc
