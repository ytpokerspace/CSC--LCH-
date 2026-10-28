"""Core data validation for the ARAF research-planning prototype.

This module deliberately does not call external APIs or claim to verify novelty.
It validates that a research plan contains the fields needed for a testable study.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


EVIDENCE_STATUSES = {
    "measured",
    "literature_supported",
    "hypothesized",
    "unverified",
    "contradicted",
}


@dataclass
class Hypothesis:
    statement: str
    prediction: str
    independent_variables: list[str]
    dependent_variables: list[str]
    rejection_criterion: str


@dataclass
class Experiment:
    baseline: str
    controls: list[str]
    dataset: str
    method: str
    metrics: list[str]
    reproducibility_notes: list[str]


@dataclass
class ResearchPlan:
    title: str
    domain: str
    problem_statement: str
    objective: str
    success_criteria: list[str]
    hypotheses: list[Hypothesis]
    experiment: Experiment
    risks: list[str] = field(default_factory=list)
    constraints: dict[str, str] = field(default_factory=dict)
    claims: list[dict[str, str]] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPlan":
        """Build a plan from a JSON-compatible dictionary."""
        hypotheses = [Hypothesis(**item) for item in data.get("hypotheses", [])]
        experiment = Experiment(**data.get("experiment", {}))
        return cls(
            title=data.get("title", ""),
            domain=data.get("domain", ""),
            problem_statement=data.get("problem_statement", ""),
            objective=data.get("objective", ""),
            success_criteria=data.get("success_criteria", []),
            hypotheses=hypotheses,
            experiment=experiment,
            risks=data.get("risks", []),
            constraints=data.get("constraints", {}),
            claims=data.get("claims", []),
            scores=data.get("scores", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_plan(plan: ResearchPlan) -> list[str]:
    """Return validation errors; an empty list means structural checks passed."""
    errors: list[str] = []

    for field_name in ("title", "domain", "problem_statement", "objective"):
        if not getattr(plan, field_name).strip():
            errors.append(f"{field_name} must not be empty")

    if not plan.success_criteria:
        errors.append("at least one measurable success criterion is required")
    if not plan.hypotheses:
        errors.append("at least one hypothesis is required")

    for index, hypothesis in enumerate(plan.hypotheses, start=1):
        prefix = f"hypotheses[{index}]"
        for field_name in ("statement", "prediction", "rejection_criterion"):
            if not getattr(hypothesis, field_name).strip():
                errors.append(f"{prefix}.{field_name} must not be empty")
        if not hypothesis.independent_variables:
            errors.append(f"{prefix}.independent_variables must not be empty")
        if not hypothesis.dependent_variables:
            errors.append(f"{prefix}.dependent_variables must not be empty")

    experiment = plan.experiment
    for field_name in ("baseline", "dataset", "method"):
        if not getattr(experiment, field_name).strip():
            errors.append(f"experiment.{field_name} must not be empty")
    if not experiment.controls:
        errors.append("experiment.controls must not be empty")
    if not experiment.metrics:
        errors.append("experiment.metrics must not be empty")
    if not experiment.reproducibility_notes:
        errors.append("experiment.reproducibility_notes must not be empty")

    for index, claim in enumerate(plan.claims, start=1):
        status = claim.get("status", "")
        if status not in EVIDENCE_STATUSES:
            errors.append(
                f"claims[{index}].status must be one of: "
                + ", ".join(sorted(EVIDENCE_STATUSES))
            )
        if not claim.get("claim", "").strip():
            errors.append(f"claims[{index}].claim must not be empty")
        if status == "literature_supported" and not claim.get("source", "").strip():
            errors.append(
                f"claims[{index}] marked literature_supported must include a source"
            )

    for score_name, score in plan.scores.items():
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 10:
            errors.append(f"scores.{score_name} must be an integer from 1 to 10")

    return errors


def validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate input data and return a machine-readable report."""
    try:
        plan = ResearchPlan.from_dict(data)
    except (TypeError, KeyError) as exc:
        return {
            "valid": False,
            "errors": [f"invalid plan structure: {exc}"],
            "plan": None,
        }

    errors = validate_plan(plan)
    return {
        "valid": not errors,
        "errors": errors,
        "plan": plan.to_dict(),
        "notice": (
            "Structural validation only; this does not verify scientific truth, "
            "literature novelty, or experimental outcomes."
        ),
    }
