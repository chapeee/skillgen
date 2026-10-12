---
title: Module map
description: Every module in src/skillgen, what it does, and its key functions and constants.
toc_max_heading_level: 2
---

# Module map

A reference to every module in `src/skillgen/`, taken from the source. Each public function
has a Google-style docstring in the code; this page is the map, the code is the detail.

## Top level

| Module | Role | Key names |
| --- | --- | --- |
| `__init__.py` | Package constants | `TOOL_NAME = "skillgendev"`, `__version__` |
| `cli.py` | Command line; the only module that prints | `main`, `build_parser`, `HANDLERS`, `emit`, `Reply`, `EXIT_OK/FAILED/ERROR/NEEDS`, `command_<name>` |
| `pipeline.py` | Per-route orchestration | `discover_routes`, `prepare_route`, `analyze_route`, `finish_route`, `write_skill`, `fingerprint_request`, `measure_page_model`, `write_index`, `ask_claude_for_routes` |
| `handoff.py` | The next step a stopped run hands over | `NextStep`, `build_next_step`, `format_command` |
| `workspace.py` | `.skillgendev/` paths and atomic file access | `Workspace`, `find_workspace_root`, `write_text_atomically`, `GITIGNORE_LINES` |
| `config.py` | `config.json` | `Settings`, `SliceSettings`, `Environment`, `AnalyzerKind`, `check_app_url` |
| `assets.py` | Shipped data in a wheel or checkout | `find_data_folder`, `read_fill_engine`, `read_index_template` |
| `export.py` | Exports, manifests, plugin layouts | `export_skills`, `export_chatgpt_plugin`, `check_export_safety`, `build_manifest`, `PLUGIN_AUTHOR` |
| `logs.py` | Run logs | `start_logging`, `list_logs`, `KEPT_LOGS = 30` |
| `errors.py` | Exceptions and needs | `SkillgenError` and subclasses, `Need`, `ActionNeededError` |

## `analyze/`

| Module | Role | Key names |
| --- | --- | --- |
| `prompt.py` | The prompt Claude Code receives for one route, and for listing routes | `PROMPT_VERSION = 3`, `AnalysisRequest`, `build_analysis_prompt`, `build_route_listing_prompt` |
| `runner.py` | Headless Claude Code, a file Claude wrote, or a replay | `ClaudeCodeAnalyzer`, `FileAnalyzer`, `ReplayAnalyzer`, `build_claude_command`, `READ_ONLY_TOOLS`, `is_limit_reached` |

## `graph/`

| Module | Role | Key names |
| --- | --- | --- |
| `codegraph.py` | File-level code graph built with Graphify, with a staleness snapshot | `CodeGraph`, `build_code_graph`, `find_graph_staleness`, `find_route_nodes` |
| `connections.py` | Graphify's own `explain` and `path`, through its command line | `GraphifyGraph`, `explain_node`, `find_path` |
| `hubs.py` | Ranks files that probably declare routes (pure) | `rank_router_candidates`, `RouterHint` |
| `slice.py` | Page slices and change impact (pure) | `slice_page`, `find_affected_files`, `find_stale_skills`, `resolve_component` |

## `routes/`

| Module | Role | Key names |
| --- | --- | --- |
| `hintpacks.py` | Loads YAML hint packs | `load_hint_packs`, `FolderPack`, `RouterPack` |
| `folders.py` | Routes from folder-routing packs, monorepo roots | `find_folder_routes`, `find_project_roots` |
| `astgrep.py` | Routes declared in code, through ast-grep | `find_declared_routes`, `run_ast_grep`, `is_in_skipped_folder` |
| `merge.py` | Merges candidates into `routes.json`, keeping developer edits | `merge_routes`, `rename_route`, `find_pattern_files`, `check_skill_name` |
| `naming.py` | Skill names and descriptions under the Agent Skills rules | `build_skill_name`, `is_valid_name`, `build_description`, `MAX_NAME_LENGTH = 64` |
| `paths.py` | One canonical route shape | `normalize_route`, `match_route`, `check_route_text`, `is_route_wanted` |

## `model/`

| Module | Role | Key names |
| --- | --- | --- |
| `page.py` | The page model | `PageModel`, `FieldSpec`, `Strategy`, `ValueType`, `Condition`, `View`, `Layout`, `SubmitSpec` |
| `facts.py` | Sources and evidence | `Source`, `Provenance`, `Evidence` |
| `confidence.py` | Confidence arithmetic | `combine_confidence`, `cap_conflict`, `INCLUSION_THRESHOLD = 0.7`, `CONFLICT_CAP = 0.5` |
| `route.py` | `routes.json` and `questions.json` entries | `RouteEntry`, `RouteTable`, `Question` |
| `serialize.py` | `page.json` to and from the model | `page_to_dict`, `page_from_dict` |
| `probe.py` | What the probe saw, as plain data | `ProbedPage`, `ProbedField` |

## `compile/`

| Module | Role | Key names |
| --- | --- | --- |
| `merge.py` | Analysis + probe + answers → page model | `build_page_model`, `merge_open_steps`, `merge_views`, `is_risky_step` |
| `fields.py` | Merges one field | `assess_field`, `build_field`, `collect_questions` |
| `assess.py` | Decides one fact and applies answers | `assess_fact`, `apply_answer` |
| `layout.py` | Attaches measurements as a layout | `build_layout`, `carry_layout` |
| `unopened.py` | What the live page had that the model missed | `find_missed_on_page` |

## `generate/`

| Module | Role | Key names |
| --- | --- | --- |
| `skill_md.py` | Renders `SKILL.md` and `references/fill.md` | `render_skill_md`, `render_fill_reference`, `BODY_TOKEN_BUDGET = 5000` |
| `inline_setter.py` | The setter `SKILL.md` carries | `build_inline_setter`, `render_engine`, `choose_landmarks`, `STATUSES`, `LAYOUT_STATES` |
| `fill_script.py` | `scripts/fill.js` | `build_fill_script`, `find_forbidden_syntax`, `MAX_SCRIPT_BYTES = 48000` |
| `fill_engine.js` | The shared fallback engine | |
| `locators.py` | `references/locators.md` | `render_locators` |
| `manual_steps.py` | `references/manual-steps.md` | `render_manual_steps` |
| `layout_reference.py` | `references/layout.json` | `render_layout_reference` |
| `examples.py` | Synthetic example values from constraints | `build_example_values` |
| `evals.py` | `evals/evals.json` | `build_evals` |
| `folder.py` | All files of one skill, in memory | `build_skill_files`, `fit_skill_text` |
| `bundle.py` | Many page skills into one skill | `build_bundle_files`, `build_entry_skill_md` |
| `user_rules.py` | The user block and `check:` annotations | `extract_user_block`, `parse_check`, `append_user_rule` |
| `index_page.py`, `index_template.html` | `skills-index.json` and `.html` | `build_index_data`, `render_index_html` |

## `probe/`

| Module | Role | Key names |
| --- | --- | --- |
| `runner.py` | Playwright: probe, measure, login | `probe_route`, `measure_page_layout`, `find_xy_need`, `save_login`, `CAPTURE_VIEWPORT` |
| `extract.js` | In-page extraction of fields and clickables | |
| `measure.js` | Measures a skill's own selectors | |
| `classify.py` | Raw controls → probed fields (pure) | `classify`, `describe_shape` |
| `capture.py` | Saves and reads probe captures | `probed_page_to_dict` |
| `journal.py` | What discovery already learnt about a page | `Journal`, `record_state`, `read_journal` |

## `validate/`, `drift/`, `schema/`

| Module | Role | Key names |
| --- | --- | --- |
| `validate/spec.py` | Agent Skills spec checks | `check_skill_md`, `check_skill_files`, `check_fill_script`, `MAX_BODY_LINES = 500` |
| `validate/model_checks.py` | Page model consistency | `check_page_model`, `find_cycle` |
| `validate/scan.py` | Secret and personal-data scan | `scan_files`, `SAFE_EMAIL_DOMAINS`, `SAFE_PHONE` |
| `drift/check.py` | Stale skills after code changes | `find_drift`, `list_changed_files`, `IMPACT_DEPTH = 2` |
| `drift/diff.py` | Semantic diff of two page models (pure) | `diff_pages`, `Change` |
| `schema/` | JSON schemas and one validator | `validate_document`, `find_schema_problems` |
