from skillgen.analyze.prompt import (
    AnalysisRequest,
    build_analysis_prompt,
    build_route_listing_prompt,
)
from skillgen.config import Settings
from skillgen.model.route import RouteEntry
from skillgen.pipeline import prepare_route
from skillgen.workspace import Workspace

REQUEST = AnalysisRequest(
    route="/signup", skill="shop-signup", app_name="Shop", slice_files=("a.tsx", "b.tsx")
)
GOOD = {"has_form": False, "title": "x", "fields": []}


def test_build_analysis_prompt_lists_files_and_rules():
    prompt = build_analysis_prompt(REQUEST)
    assert "- a.tsx" in prompt and "inferred" in prompt and "Never copy real data" in prompt
    assert "probe" not in prompt.lower().split("rules for your answer")[0]


def test_build_analysis_prompt_includes_probe_and_truncation():
    request = AnalysisRequest(
        "/x", "s", "", ("a",), is_slice_truncated=True, probe_summary={"fields": []}
    )
    prompt = build_analysis_prompt(request)
    assert "cut at its size limit" in prompt and "What the browser saw on this page" in prompt


def test_build_route_listing_prompt_names_files():
    prompt = build_route_listing_prompt(
        "Shop",
        [("config/routes.rb", ["app/controllers/a.rb"], ["links to 1 file(s)"])],
        ["/signup"],
    )
    assert "- config/routes.rb  (links to 1 file(s))" in prompt
    assert "    → app/controllers/a.rb" in prompt
    assert "Already found (do not repeat them):\n- /signup" in prompt
    assert "start from the repository's entry points" in build_route_listing_prompt("Shop", [], [])


def test_build_analysis_prompt_explains_the_value_type():
    """The schema lists the valid types; the rules must say how to choose one.

    Without this an agent answers with the HTML control (radio, checkbox, select) and
    pays a round trip per rejected guess.
    """
    prompt = build_analysis_prompt(
        AnalysisRequest(route="/x", skill="a-x", app_name="A", slice_files=("a.vue",))
    )
    assert "- type: what the value is, never the HTML control." in prompt
    for value in ("long-text", "multi-enum", "rich-text", "boolean"):
        assert value in prompt
    assert "Never\n  radio, checkbox, select or textarea" in prompt


def test_prepare_route_writes_the_schema_into_the_prompt(tmp_path):
    """Whoever answers `prompt.md` by hand has no other way to know the contract."""
    (tmp_path / "Form.vue").write_text("<template><input name='a'></template>", encoding="utf-8")
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    entry = RouteEntry(route="/a", skill="shop-a", entry_files=("Form.vue",))
    prepare_route(workspace, Settings(app_name="Shop"), entry, None, None)
    prompt = (workspace.page_folder("shop-a") / "prompt.md").read_text(encoding="utf-8")
    assert "Answer with only a JSON object that matches this JSON schema:" in prompt
    # The parts the transcript showed an agent guessing at, one round trip each.
    for part in ('"has_form"', '"evidence"', '"quote"', '"multi-enum"', '"not_in"'):
        assert part in prompt


def test_build_analysis_prompt_sends_the_clickable_list_for_the_parts_behind_a_click():
    """A button is never a field, but one that opens part of the form is a view."""
    request = AnalysisRequest(
        "/x",
        "s",
        "",
        ("a",),
        probe_summary={
            "fields": [],
            "clickable": [{"label": "Add witness", "role": "button", "click": "#add"}],
        },
    )
    prompt = build_analysis_prompt(request)
    assert "`clickable` lists what a person can click" in prompt
    assert "Add witness" in prompt and "#add" in prompt
    assert "is never a field, but one that opens part of the form" in prompt


def test_build_analysis_prompt_says_nothing_about_the_page_without_a_capture():
    prompt = build_analysis_prompt(AnalysisRequest("/x", "s", "", ("a",)))
    assert "What the browser saw" not in prompt and "clickable" not in prompt
