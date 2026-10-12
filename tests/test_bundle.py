"""Several page skills bundled into one skill folder with a single `SKILL.md`."""

from skillgen.assets import read_fill_engine
from skillgen.generate.bundle import (
    PageEntry,
    build_bundle_description,
    build_bundle_files,
    build_entry_skill_md,
    build_page_files,
    describe_page,
    read_frontmatter_value,
    retarget_support_paths,
    summarize_description,
)
from skillgen.generate.folder import build_skill_files
from skillgen.routes.naming import MAX_DESCRIPTION_LENGTH
from skillgen.validate.spec import check_skill_files, check_skill_md
from tests.helpers import load_bench_page, load_wizard_page


def bench_files() -> dict[str, str]:
    return build_skill_files(load_bench_page(), read_fill_engine())


def wizard_files() -> dict[str, str]:
    return build_skill_files(load_wizard_page(), read_fill_engine())


def test_read_frontmatter_value_reads_top_level_and_nested_keys():
    frontmatter = 'name: a\ndescription: "b"\nmetadata:\n  route: "/x"'
    assert read_frontmatter_value(frontmatter, "description") == "b"
    assert read_frontmatter_value(frontmatter, "route") == "/x"
    assert read_frontmatter_value(frontmatter, "missing") == ""


def test_summarize_description_keeps_what_is_on_the_page():
    description = (
        "Fills the Apply form at /apply in Bench: applicant, organisation and location. "
        "Use when asked to fill in, complete or submit the Apply form in Bench."
    )
    assert summarize_description(description) == "applicant, organisation and location"


def test_summarize_description_cuts_at_a_word():
    summary = summarize_description("X: " + " ".join(["word"] * 60))
    assert len(summary) <= 161 and summary.endswith("…") and "wor…" not in summary


def test_describe_page_reads_the_title_route_and_summary():
    entry = describe_page("bench-apply", bench_files()["SKILL.md"])
    assert entry == PageEntry(
        skill="bench-apply",
        title="Bench application",
        route="/apply",
        summary="applicant, organisation, location, preferences and statement",
    )


def test_retarget_support_paths_moves_a_pages_own_files():
    text = "read `scripts/fill.js` and `references/layout.json`"
    assert retarget_support_paths(text, "bench-apply") == (
        "read `scripts/bench-apply/fill.js` and `references/bench-apply/layout.json`"
    )


def test_retarget_support_paths_leaves_other_text_alone():
    assert retarget_support_paths("no paths here; scripts/ alone", "x") == (
        "no paths here; scripts/ alone"
    )


def test_build_page_files_puts_the_body_in_its_own_folder():
    files = build_page_files("bench-apply", bench_files())
    assert "SKILL.md" not in files
    assert files["references/bench-apply/page.md"].startswith("# Bench application — /apply")
    assert "scripts/bench-apply/fill.js" in files
    assert "references/bench-apply/locators.md" in files


def test_build_page_files_drops_developer_test_files():
    assert not any("evals" in path for path in build_page_files("bench-apply", bench_files()))


def test_build_bundle_files_holds_exactly_one_skill_md():
    files = build_bundle_files("acme", "Acme", {"bench-apply": bench_files()})
    assert [path for path in files if path.endswith("SKILL.md")] == ["SKILL.md"]


def test_build_bundle_files_keeps_every_pages_content():
    pages = {"bench-apply": bench_files(), "bench-wizard": wizard_files()}
    files = build_bundle_files("acme", "Acme", pages)
    for skill in pages:
        assert files[f"references/{skill}/page.md"]
        assert files[f"scripts/{skill}/fill.js"]
    assert "`references/bench-wizard/page.md`" in files["SKILL.md"]


def test_build_bundle_files_passes_the_skill_spec_checks():
    files = build_bundle_files("acme", "Acme", {"bench-apply": bench_files()})
    assert check_skill_files(files, "acme") == []


def test_build_entry_skill_md_names_its_folder_and_its_pages():
    pages = [PageEntry("one", "One", "/one", "a"), PageEntry("two", "Two", "/two", "b")]
    text = build_entry_skill_md("acme", "Acme", pages, "Built for X; needs access to Y.")
    assert check_skill_md(text, "acme") == []
    assert 'compatibility: "Built for X; needs access to Y."' in text
    assert '  pages: "2"' in text
    assert text.index("`references/one/page.md`") < text.index("`references/two/page.md`")


def test_build_entry_skill_md_leaves_out_an_empty_compatibility_line():
    text = build_entry_skill_md("acme", "Acme", [PageEntry("one", "One", "/one", "a")])
    assert "compatibility:" not in text


def test_build_bundle_description_fits_the_limit_and_says_how_many_are_left():
    pages = [PageEntry(f"p{n}", f"Page number {n}", f"/page/number/{n}", "x") for n in range(20)]
    description = build_bundle_description("Acme", pages)
    assert len(description) <= MAX_DESCRIPTION_LENGTH and "more" in description


def test_build_bundle_description_names_one_page_even_when_long():
    page = PageEntry("p", "P" * 400, "/p", "x")
    assert "P" * 400 in build_bundle_description("Acme", [page])
