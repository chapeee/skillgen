import pytest

from skillgen.errors import RouteError
from skillgen.model.route import RouteCandidate, RouteEntry, RouteTable
from skillgen.routes.merge import (
    check_skill_name,
    find_pattern_files,
    merge_routes,
    rename_route,
)


def test_merge_routes_names_and_dedupes():
    table = merge_routes(
        RouteTable(),
        [RouteCandidate("/a/", "x", ("f1",)), RouteCandidate("/a", "y", ("f2",))],
        "acme",
    )
    (entry,) = table.entries
    assert entry.route == "/a" and entry.skill == "acme-a"
    assert entry.sources == ("x", "y") and entry.entry_files == ("f1", "f2")


def test_merge_routes_keeps_locked_names_and_skips():
    old = RouteTable(
        (RouteEntry("/a", "mine", is_name_locked=True, is_skipped=True, has_form=True),)
    )
    (entry,) = merge_routes(old, [RouteCandidate("/a", "folder")], "acme").entries
    assert entry.skill == "mine" and entry.is_skipped and entry.has_form


def test_merge_routes_renames_unlocked_with_new_prefix():
    old = RouteTable((RouteEntry("/a", "old-a"),))
    assert merge_routes(old, [], "new").entries[0].skill == "new-a"


def test_merge_routes_makes_names_unique():
    table = merge_routes(
        RouteTable(), [RouteCandidate("/a-b", "x"), RouteCandidate("/a/b", "x")], "p"
    )
    assert sorted(e.skill for e in table.entries) == ["p-a-b", "p-a-b-2"]


def test_merge_routes_avoids_locked_name_clash():
    old = RouteTable((RouteEntry("/z", "p-a", is_name_locked=True),))
    table = merge_routes(old, [RouteCandidate("/a", "x")], "p")
    assert {e.route: e.skill for e in table.entries} == {"/a": "p-a-2", "/z": "p-a"}


def test_merge_routes_applies_globs_to_new_routes_only():
    old = RouteTable((RouteEntry("/admin/x", "p-admin-x"),))
    table = merge_routes(old, [RouteCandidate("/admin/y", "x")], "p", exclude=["admin/*"])
    assert [e.route for e in table.entries] == ["/admin/x"]


def test_rename_route_locks_and_validates():
    table = RouteTable((RouteEntry("/a", "p-a"), RouteEntry("/b", "p-b")))
    renamed = rename_route(table, "/a", "join-us")
    assert renamed.find("/a") == RouteEntry("/a", "join-us", is_name_locked=True)
    with pytest.raises(RouteError, match="already used"):
        rename_route(table, "/a", "p-b")
    with pytest.raises(RouteError, match="no route"):
        rename_route(table, "/nope", "x")


def test_check_skill_name_explains_rules():
    with pytest.raises(RouteError, match="lowercase"):
        check_skill_name("Join Us")


def test_merge_routes_keeps_open_steps():
    old = RouteTable((RouteEntry("/a", "mine", open_steps=("text:Page settings",)),))
    (entry,) = merge_routes(old, [RouteCandidate("/a", "folder")], "acme").entries
    assert entry.open_steps == ("text:Page settings",)


def test_rename_route_keeps_open_steps():
    old = RouteTable((RouteEntry("/a", "old-a", open_steps=("text:Page settings",)),))
    (entry,) = rename_route(old, "/a", "new-a").entries
    assert entry.skill == "new-a" and entry.open_steps == ("text:Page settings",)


PATTERNS = [
    RouteCandidate("/cms/locations/:level/:id", "folder", ("app/[level]/[id]/page.tsx",)),
    RouteCandidate("/cms/locations/template/:id", "folder", ("app/template/[id]/page.tsx",)),
    RouteCandidate("/cms/locations/:level", "folder", ("app/[level]/page.tsx",)),
]


def test_find_pattern_files_links_a_concrete_page_to_its_pattern():
    assert find_pattern_files("/cms/locations/states/134", PATTERNS) == (
        "app/[level]/[id]/page.tsx",
    )


def test_find_pattern_files_prefers_the_more_specific_pattern():
    assert find_pattern_files("/cms/locations/template/9", PATTERNS) == (
        "app/template/[id]/page.tsx",
    )


def test_find_pattern_files_guesses_nothing_when_two_patterns_tie():
    tied = [
        RouteCandidate("/a/:x/b", "folder", ("one.tsx",)),
        RouteCandidate("/a/b/:y", "folder", ("two.tsx",)),
    ]
    assert find_pattern_files("/a/b/b", tied) == ()


def test_find_pattern_files_finds_nothing_for_an_unknown_page():
    assert find_pattern_files("/nothing/here", PATTERNS) == ()


def test_merge_routes_replaces_saved_files_with_the_ones_found_now():
    old = RouteTable(
        entries=(
            RouteEntry(route="/a", skill="p-a", entry_files=("router.js",), sources=("user",)),
        )
    )
    (entry,) = merge_routes(old, [RouteCandidate("/a", "router:x", ("Page.vue",))], "p").entries
    assert entry.entry_files == ("Page.vue",)


def test_merge_routes_drops_a_stale_route_nothing_of_the_developers_depends_on():
    junk = RouteEntry(route="/color", skill="p-color", sources=("router:express",))
    kept = RouteEntry(route="/kept", skill="mine", sources=("router:express",), is_name_locked=True)
    made = RouteEntry(route="/made", skill="p-made", sources=("folder:x",), has_form=True)
    mine = RouteEntry(route="/mine", skill="p-mine", sources=("user",))
    table = merge_routes(RouteTable(entries=(junk, kept, made, mine)), [], "p")
    assert [entry.route for entry in table.entries] == ["/kept", "/made", "/mine"]


def test_merge_routes_drops_a_route_that_is_a_windows_path():
    mangled = RouteEntry(route="/C:/Program Files/Git/forms/x", skill="p-x", sources=("user",))
    assert merge_routes(RouteTable(entries=(mangled,)), [], "p").entries == ()
