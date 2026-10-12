from skillgen.assets import find_data_folder
from skillgen.routes.folders import (
    build_folder_route,
    find_folder_routes,
    find_project_roots,
    list_folders,
)
from skillgen.routes.hintpacks import load_hint_packs
from tests.conftest import FIXTURES

PACKS = {p.id: p for p in load_hint_packs([find_data_folder("hintpacks")]).folders}


def test_build_folder_route_app_router():
    pack = PACKS["nextjs-app"]
    assert build_folder_route(["(account)", "register", "page.tsx"], pack) == "/register"
    assert (
        build_folder_route(["orders", "[orderId]", "return", "page.tsx"], pack)
        == "/orders/:orderId/return"
    )
    assert build_folder_route(["page.tsx"], pack) == "/"
    assert build_folder_route(["_private", "page.tsx"], pack) is None


def test_build_folder_route_file_router():
    pack = PACKS["nextjs-pages"]
    assert build_folder_route(["blog", "[slug].tsx"], pack) == "/blog/:slug"
    assert build_folder_route(["index.tsx"], pack) == "/"
    assert build_folder_route(["_app.tsx"], pack) is None


def test_build_folder_route_sveltekit():
    assert (
        build_folder_route(["items", "[id=integer]", "+page.svelte"], PACKS["sveltekit-routes"])
        == "/items/:id"
    )


def test_find_project_roots_needs_a_marker(tmp_path):
    pack = PACKS["nuxt-pages"]
    assert find_project_roots(tmp_path, pack, list_folders(tmp_path)) == []
    (tmp_path / "nuxt.config.ts").write_text("")
    assert find_project_roots(tmp_path, pack, list_folders(tmp_path)) == [tmp_path]


def test_find_project_roots_finds_an_app_deep_in_a_monorepo(tmp_path):
    app = tmp_path / "admin-side" / "dashboard"
    app.mkdir(parents=True)
    (app / "next.config.ts").write_text("")
    roots = find_project_roots(tmp_path, PACKS["nextjs-app"], list_folders(tmp_path))
    assert roots == [app]


def test_find_project_roots_skips_dependencies(tmp_path):
    hidden = tmp_path / "node_modules" / "some-lib"
    hidden.mkdir(parents=True)
    (hidden / "package.json").write_text("{}")
    assert find_project_roots(tmp_path, PACKS["nextjs-app"], list_folders(tmp_path)) == []


def write_page(folder, *parts):
    page = folder.joinpath(*parts)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("export default function Page() {}")


def test_find_folder_routes_finds_pages_of_an_app_in_a_monorepo(tmp_path):
    app = tmp_path / "admin-side" / "dashboard"
    app.mkdir(parents=True)
    (app / "next.config.ts").write_text("")
    write_page(app, "src", "app", "(admin)", "cms", "locations", "[level]", "[id]", "page.tsx")
    (found,) = find_folder_routes(tmp_path, [PACKS["nextjs-app"]])
    assert found.route == "/cms/locations/:level/:id"
    assert found.entry_files == (
        "admin-side/dashboard/src/app/(admin)/cms/locations/[level]/[id]/page.tsx",
    )


def test_find_folder_routes_ignores_a_components_pages_folder(tmp_path):
    # A folder named "pages" outside a Next.js project root is not a router.
    (tmp_path / "package.json").write_text("{}")
    write_page(tmp_path, "src", "components", "pages", "Hero.tsx")
    assert find_folder_routes(tmp_path, [PACKS["nextjs-pages"]]) == []


def test_find_folder_routes_finds_nothing_in_a_backend_app_folder(tmp_path):
    # A backend's own `app/` beside a package.json holds no page files.
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "package.json").write_text("{}")
    (backend / "app" / "Http").mkdir(parents=True)
    (backend / "app" / "Http" / "Controller.php").write_text("<?php")
    assert find_folder_routes(tmp_path, [PACKS["nextjs-app"]]) == []


def test_find_folder_routes_on_nextjs_fixture():
    candidates = find_folder_routes(FIXTURES / "nextjs-app", PACKS.values())
    routes = sorted(c.route for c in candidates)
    assert routes == ["/", "/contact", "/orders/:orderId/return", "/register"]
    contact = next(c for c in candidates if c.route == "/contact")
    assert (
        contact.entry_files == ("app/contact/page.tsx",) and contact.source == "folder:nextjs-app"
    )


def test_find_folder_routes_ignores_node_modules(tmp_path):
    (tmp_path / "app" / "node_modules" / "x").mkdir(parents=True)
    (tmp_path / "app" / "node_modules" / "x" / "page.tsx").write_text("")
    assert find_folder_routes(tmp_path, PACKS.values()) == []
