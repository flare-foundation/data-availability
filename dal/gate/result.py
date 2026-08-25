"""What a gate answers.

Three outcomes, and the distinction between the last two is the one the existing
implementations do not draw: a *refusal* means the origin produced something
wrong, which is a bug or an attack and must be alarmed; a *failure* means we
could not tell, which is retryable. Storing them the same way is how a
persistent forgery looks like a flaky network.
"""

from dataclasses import dataclass

__all__ = ["Admitted", "Refused", "Verdict"]


@dataclass(frozen=True, slots=True)
class Admitted:
    """The artifact passed its gate. ``raw`` is what must be stored, verbatim."""

    key: bytes
    raw: bytes

    ok = True


@dataclass(frozen=True, slots=True)
class Refused:
    """The origin produced something inadmissible. Terminal, and worth an alarm."""

    reason: str

    ok = False


Verdict = Admitted | Refused
