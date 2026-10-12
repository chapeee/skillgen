import pytest

from skillgen.errors import RouteError
from skillgen.routes.paths import (
    check_route_text,
    is_route_wanted,
    match_route,
    normalize_route,
    normalize_segment,
    strip_quotes,
)


@pytest.mark.parametrize(
    ("raw", "route"),
    [
        ("'/signup'", "/signup"),
        ('"contact/"', "/contact"),
        ("/users/{id}/edit", "/users/:id/edit"),
        ("/account/<int:account_id>/edit", "/account/:account_id/edit"),
        ("/blog/[...slug]", "/blog/:slug"),
        ("/a/$id?x=1#top", "/a/:id"),
        ("", "/"),
        ("./x", "/x"),
    ],
)
def test_normalize_route_handles_every_spelling(raw, route):
    assert normalize_route(raw) == route


def test_strip_quotes_only_matching_pair():
    assert strip_quotes("'a\"") == "'a\""
    assert strip_quotes("`a`") == "a"


def test_normalize_segment_leaves_plain_segments():
    assert normalize_segment("edit") == "edit"


def test_is_route_wanted_applies_globs():
    assert is_route_wanted("/developer/kyc", ["developer/*"], [])
    assert not is_route_wanted("/admin/x", ["developer/*"], [])
    assert not is_route_wanted("/developer/kyc", [], ["/developer/*"])
    assert is_route_wanted("/anything", [], [])


@pytest.mark.parametrize(
    ("pattern", "route", "expected"),
    [
        ("/cms/locations/:level/:id", "/cms/locations/states/134", 2),
        ("/cms/locations/template/:id", "/cms/locations/template/9", 3),
        ("/cms/locations/:level", "/cms/locations/states/134", None),
        ("/users/:id", "/teams/7", None),
        ("/", "/", 1),
    ],
)
def test_match_route(pattern, route, expected):
    assert match_route(pattern, route) == expected


@pytest.mark.parametrize(
    "route", ["/C:/Program Files/Git/forms/employee-onboarding", "C:\\work\app", "d:/x"]
)
def test_check_route_text_refuses_a_windows_path(route):
    with pytest.raises(RouteError, match="MSYS_NO_PATHCONV=1"):
        check_route_text(route)


def test_check_route_text_accepts_routes_and_skill_names():
    check_route_text("/forms/employee-onboarding")
    check_route_text("formtest-employee-onboarding")
