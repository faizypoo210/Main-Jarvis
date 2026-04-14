"""Routing precedence for briefing vs unified intake (no I/O)."""

from __future__ import annotations

from voice.routing_precedence import should_defer_briefing_to_freeform_intake


def test_github_issues_summarize_blockers_defers_to_intake() -> None:
    assert should_defer_briefing_to_freeform_intake(
        "Check my active GitHub issues and summarize blockers"
    )


def test_look_through_prs_defers() -> None:
    assert should_defer_briefing_to_freeform_intake("Look through my PRs and note risks")


def test_summarize_inbox_defers() -> None:
    assert should_defer_briefing_to_freeform_intake("Summarize my inbox")


def test_whats_happening_operator_briefing_not_deferred() -> None:
    assert not should_defer_briefing_to_freeform_intake("What is going on right now?")


def test_what_needs_attention_not_deferred() -> None:
    assert not should_defer_briefing_to_freeform_intake("What needs my attention?")


def test_read_that_again_repeat_does_not_match_defer() -> None:
    assert not should_defer_briefing_to_freeform_intake("read that again")


def test_compose_blocked_no_bare_blockers_word() -> None:
    """Regression: bare 'blockers' must not match RE_WHATS_BLOCKED (briefing_voice)."""
    import re

    from voice.briefing_voice import RE_WHATS_BLOCKED

    assert not RE_WHATS_BLOCKED.search("summarize blockers on the project")
    assert RE_WHATS_BLOCKED.search("what is blocked")


def main() -> None:
    test_github_issues_summarize_blockers_defers_to_intake()
    test_look_through_prs_defers()
    test_summarize_inbox_defers()
    test_whats_happening_operator_briefing_not_deferred()
    test_what_needs_attention_not_deferred()
    test_read_that_again_repeat_does_not_match_defer()
    test_compose_blocked_no_bare_blockers_word()
    print("routing_precedence tests: ok")


if __name__ == "__main__":
    main()
