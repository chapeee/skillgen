import pytest

from skillgen.errors import RouteError
from skillgen.routes.naming import (
    MAX_DESCRIPTION_LENGTH,
    build_description,
    build_skill_name,
    find_route_params,
    is_valid_name,
    make_unique_names,
    slugify,
    slugify_route,
    trim_name,
)


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ("/developer/kyc", "acme-developer-kyc"),
        ("/individual/account", "acme-individual-account"),
        ("/projects/:id/edit", "acme-projects-edit"),
        ("/blog/[slug]", "acme-blog"),
        ("/users/{userId}/settings", "acme-users-settings"),
        ("/", "acme-home"),
        ("/Sign_Up", "acme-sign-up"),
    ],
)
def test_build_skill_name_follows_pattern(route, expected):
    assert build_skill_name("Acme", route) == expected


def test_build_skill_name_is_at_most_64_characters():
    name = build_skill_name("A very long application name", "/" + "/".join(["segment"] * 20))
    assert len(name) <= 64
    assert is_valid_name(name)


def test_build_skill_name_uses_home_when_route_is_only_parameters():
    assert build_skill_name("", "/:id") == "home"


def test_build_skill_name_rejects_name_without_letters(monkeypatch):
    monkeypatch.setattr("skillgen.routes.naming.slugify_route", lambda route: "")
    with pytest.raises(RouteError):
        build_skill_name("", "/x")


def test_slugify_drops_non_ascii_and_punctuation():
    assert slugify("Développeur — KYC!") == "d-veloppeur-kyc"


def test_slugify_route_returns_home_for_root():
    assert slugify_route("/") == "home"


@pytest.mark.parametrize(
    ("route", "params"),
    [
        ("/projects/:id/edit", ["id"]),
        ("/blog/[...slug]", ["slug"]),
        ("/users/<int:user_id>", ["user_id"]),
        ("/a/{org}/{repo}", ["org", "repo"]),
        ("/static/page", []),
    ],
)
def test_find_route_params_finds_every_spelling(route, params):
    assert find_route_params(route) == params


def test_trim_name_cuts_at_hyphen():
    assert trim_name("alpha-beta-gamma", 12) == "alpha-beta"


def test_make_unique_names_adds_numeric_suffix():
    assert make_unique_names(["a-b", "a-b", "c", "a-b"]) == ["a-b", "a-b-2", "c", "a-b-3"]


def test_is_valid_name_rejects_double_hyphen_and_uppercase():
    assert not is_valid_name("a--b")
    assert not is_valid_name("Abc")
    assert not is_valid_name("-abc")
    assert is_valid_name("abc-123")


def test_build_description_follows_template():
    text = build_description(
        "Developer KYC", "/developer/kyc", "Acme Admin", ["Business details", "Bank account"]
    )
    assert text == (
        "Fills the Developer KYC form at /developer/kyc in Acme Admin: business details and "
        "bank account. Use when asked to fill in, complete or submit the Developer KYC form "
        "in Acme Admin."
    )


def test_build_description_drops_topics_to_fit():
    topics = [f"Topic number {i} with a long label" for i in range(30)]
    text = build_description("Big", "/big", "App", topics)
    assert len(text) <= MAX_DESCRIPTION_LENGTH
    assert "Use when asked to" in text
