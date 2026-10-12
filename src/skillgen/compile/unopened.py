"""What the live page offered that the code analysis never accounted for.

A page's fields and the parts behind a click are read from the code. The browser then
replays what that reading found. So anything the reading missed is never opened, and its
fields never reach the skill, with nothing to say so.

This compares the page the browser inventoried against the model built from the code and
names the difference: fields on the page that the model does not have, and controls that
look like they open part of the form but were never used as a step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from skillgen.model.page import PageModel
from skillgen.model.probe import ProbedPage

# A control that looks like it holds part of a form behind it, by role or by state.
OPENING_ROLES = frozenset({"tab", "summary", "menuitem"})
# Reported per page, so one noisy page cannot fill a run's output.
MAX_REPORTED = 8


@dataclass(frozen=True)
class MissedOnPage:
    """What the live page had that the model does not account for.

    Attributes:
        fields: Keys the page showed that the model has no field for.
        unopened: (label, step) for each control that looks like it opens part of the
            form and was never clicked.
    """

    fields: tuple[str, ...] = ()
    unopened: tuple[tuple[str, str], ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when the code reading accounted for everything the page offered."""
        return not self.fields and not self.unopened


def looks_like_an_opener(clickable: Mapping[str, object]) -> bool:
    """Tell whether a control looks like it holds part of the form behind it.

    The page's own chrome, a link away from it, and anything that would submit, reset
    or delete are all excluded: none of them opens part of this form, and clicking them
    costs either nothing or too much.

    Args:
        clickable: One entry from the page inventory.

    Returns:
        True when it is worth having opened.
    """
    if any(clickable.get(flag) for flag in ("chrome", "leaves", "risky", "disabled")):
        return False
    if not clickable.get("visible"):
        return False
    return bool(
        clickable.get("collapsed")
        or clickable.get("opens")
        or str(clickable.get("role", "")) in OPENING_ROLES
    )


def find_missed_on_page(
    page: PageModel, probe: ProbedPage, steps_used: Sequence[str] = ()
) -> MissedOnPage:
    """Compare what the browser saw with what the code reading produced.

    Args:
        page: The model built from the code.
        probe: What the browser inventoried on the live page.
        steps_used: Clicks the run already made, which need no reporting.

    Returns:
        The difference, bounded.
    """
    known = {spec.key for spec in page.fields}
    missed = tuple(probed.key for probed in probe.fields if probed.key not in known and probed.key)
    used = set(steps_used) | {step for view in page.views for step in view.enter}
    used |= set(page.open_steps)
    unopened = tuple(
        (str(item.get("label", "")), str(item.get("step", "")))
        for item in probe.clickables
        if looks_like_an_opener(item) and str(item.get("step", "")) not in used
    )
    return MissedOnPage(fields=missed[:MAX_REPORTED], unopened=unopened[:MAX_REPORTED])


def describe_missed(missed: MissedOnPage) -> list[str]:
    """Write the difference as lines a run can report.

    Args:
        missed: What the comparison found.

    Returns:
        One line per finding; empty when nothing was missed.
    """
    lines = []
    if missed.fields:
        lines.append(
            f"the live page shows {len(missed.fields)} field(s) the code reading did not "
            f"report: {', '.join(missed.fields)}"
        )
    for label, step in missed.unopened:
        lines.append(
            f'"{label}" looks like it opens part of the form and was never opened; '
            f"regenerate with --open {step} to include what is behind it"
        )
    return lines
