from skillgen import TOOL_NAME
from skillgen.analyze.runner import is_limit_reached
from skillgen.handoff import (
    build_next_step,
    find_root_arguments,
    format_command,
    with_flag,
    without_flag,
)

COMMAND = ["generate", "--route", "/apply", "--name", "acme-apply", "--xy", "--json"]


def test_format_command_quotes_only_what_a_shell_would_change():
    assert format_command(["generate", "--route", "/a/b"]) == f"{TOOL_NAME} generate --route /a/b"
    assert (
        format_command(["--open", "text:Page settings"])
        == f"{TOOL_NAME} --open 'text:Page settings'"
    )
    assert format_command(["--root", "C:\\work\\app"]) == f"{TOOL_NAME} --root 'C:\\work\\app'"
    assert format_command(["--open", 'a[title="x"]']) == f"{TOOL_NAME} --open 'a[title=\"x\"]'"


def test_with_flag_adds_a_flag_once():
    assert with_flag(["generate"], "--overwrite") == ["generate", "--overwrite"]
    assert with_flag(["generate", "--overwrite"], "--overwrite") == ["generate", "--overwrite"]
    assert with_flag(["generate"], "--url", "<url>") == ["generate", "--url", "<url>"]
    assert with_flag(["generate", "--url=http://x"], "--url", "<url>") == [
        "generate",
        "--url=http://x",
    ]


def test_find_root_arguments_repeats_the_root():
    assert find_root_arguments(["generate", "--root", "app"]) == ["--root", "app"]
    assert find_root_arguments(["generate", "--root=app"]) == ["--root", "app"]
    assert find_root_arguments(["generate"]) == []


def test_build_next_step_hands_the_analysis_to_the_agent():
    step = build_next_step(
        "analysis", "not signed in", COMMAND, prompt="p/prompt.md", write="p/analysis.json"
    )
    assert step.action == "analyse" and step.ask == ""
    assert (step.prompt, step.write) == ("p/prompt.md", "p/analysis.json")
    assert step.then == f"{TOOL_NAME} " + " ".join(COMMAND)


def test_build_next_step_asks_for_the_address():
    step = build_next_step("url", "", COMMAND)
    assert step.action == "ask" and "address" in step.ask and step.run == ""
    assert step.then.endswith("--url '<url>'")


def test_build_next_step_offers_a_sign_in_and_recreates_the_written_skill():
    step = build_next_step(
        "login", "http://localhost:3000/apply", [*COMMAND, "--root", "app"], has_written=True
    )
    assert "sign in" in step.ask
    assert step.run == f"{TOOL_NAME} login --url http://localhost:3000/apply --root app"
    assert step.then.endswith("--root app --overwrite")


def test_build_next_step_offers_the_chromium_download():
    step = build_next_step("chromium", "", COMMAND)
    assert step.run == f"{TOOL_NAME} doctor --fix" and "--overwrite" not in step.then


def test_build_next_step_asks_before_overwriting():
    step = build_next_step("overwrite", "acme-apply", COMMAND)
    assert "acme-apply" in step.ask and step.then.endswith("--overwrite")


def test_without_flag_removes_every_value():
    assert without_flag(["g", "--open", "a", "--open=b", "--xy"], "--open") == ["g", "--xy"]


def test_build_next_step_asks_what_opens_the_form():
    step = build_next_step("open", "http://x/a", [*COMMAND, "--open", "#gone"], has_written=True)
    assert "hidden" in step.ask and "#gone" not in step.then
    assert step.then.endswith("--overwrite --open 'text:<label>'")


# The message a real run hit when the maintainer's Claude account was out of session.
LIMIT_REASON = (
    "Claude Code failed on /forms/employee-onboarding: You've hit your session limit "
    "· resets 8:40pm (Asia/Kolkata)"
)


def test_is_limit_reached_spots_every_wording_including_session_limit():
    assert is_limit_reached(LIMIT_REASON)
    for wording in ("usage limit", "Rate limit exceeded", "out of credit", "429 Too Many Requests"):
        assert is_limit_reached(wording)
    assert not is_limit_reached("no such file or directory")
    assert not is_limit_reached("the analysis did not match its schema")


def test_build_next_step_for_a_limit_says_wait_rather_than_do_it_by_hand():
    """A limit resets on its own, so waiting is the cheap answer.

    Handing the route over instead makes the agent read the code and write the analysis
    by hand, which spends much more of the same limit.
    """
    step = build_next_step("limit", LIMIT_REASON, ["generate", "--route", "/x", "--json"])
    assert step.action == "ask" and step.need == "limit"
    assert "wait until then and run the same command again" in step.ask
    assert "Do not write the analysis by hand" in step.ask
    assert step.then == f"{TOOL_NAME} generate --route /x --json"
    # Nothing for the agent to write: that is what the analysis need is for.
    assert step.prompt == "" and step.write == ""
