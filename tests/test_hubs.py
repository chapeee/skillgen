from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.hubs import rank_router_candidates, score_file

GRAPH = CodeGraph(
    files=(
        "config/routes.rb",
        "app/a.rb",
        "app/b.rb",
        "app/c.rb",
        "lib/util.rb",
        "test/routes_test.rb",
        "Pages/X.cshtml",
    ),
    edges=(
        ("config/routes.rb", "app/a.rb", "references"),
        ("config/routes.rb", "app/b.rb", "references"),
        ("config/routes.rb", "app/c.rb", "references"),
        ("app/a.rb", "lib/util.rb", "calls"),
        ("test/routes_test.rb", "app/a.rb", "calls"),
        ("test/routes_test.rb", "app/b.rb", "calls"),
        ("test/routes_test.rb", "app/c.rb", "calls"),
    ),
    routes=(("/x", "Pages/X.cshtml"),),
)


def test_rank_router_candidates_prefers_named_hubs_and_skips_tests():
    hints = rank_router_candidates(GRAPH)
    assert [hint.file for hint in hints] == ["Pages/X.cshtml", "config/routes.rb"]
    assert hints[1].links == ("app/a.rb", "app/b.rb", "app/c.rb")
    assert "Graphify found routes in it" in hints[0].reasons


def test_rank_router_candidates_respects_limit():
    assert len(rank_router_candidates(GRAPH, limit=1)) == 1


def test_score_file_combines_fan_out_and_name():
    assert score_file("src/router.ts", 2, has_route_nodes=False)[0] == 7
    assert score_file("src/thing.ts", 0, has_route_nodes=False) == (0.0, [])
