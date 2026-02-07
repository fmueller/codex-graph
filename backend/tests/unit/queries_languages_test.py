"""Unit tests for query availability across supported languages."""

from pathlib import Path
from typing import cast

import pytest
from tree_sitter import Parser, Query, QueryCursor
from tree_sitter_language_pack import SupportedLanguage, get_language, get_parser


def _get_capture_names(query: Query, parser: Parser, source: str) -> set[str]:
    tree = parser.parse(source.encode("utf-8"))
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    if isinstance(captures, dict):
        return set(captures.keys())
    return {capture_name for _, capture_name in captures}


@pytest.mark.parametrize(
    ("language", "source", "expected_detailed", "expected_high"),
    [
        (
            "c",
            "#include <stdio.h>\nstruct Foo { int x; };\nint add(int a,int b){return a+b;}",
            {
                "unit.root",
                "def.struct",
                "def.struct.name",
                "def.func",
                "def.func.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.struct", "def.func", "rel.imports"},
        ),
        (
            "cpp",
            "#include <vector>\nclass Foo { public: void bar(){} };\nint add(int a,int b){return a+b;}",
            {
                "unit.root",
                "def.class",
                "def.class.name",
                "def.func",
                "def.func.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.class", "def.func", "rel.imports"},
        ),
        (
            "csharp",
            "using System.Text; namespace Demo { class Foo { void Bar() {} } }",
            {
                "unit.root",
                "def.namespace",
                "def.namespace.name",
                "def.class",
                "def.class.name",
                "def.method",
                "def.method.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.class", "def.method", "rel.imports"},
        ),
        (
            "css",
            '@import "base.css";\n.button { color: red; }',
            {"unit.root", "rel.imports", "use.import.path", "def.rule", "def.selector", "def.selector.name"},
            {"unit.root", "def.rule", "rel.imports"},
        ),
        (
            "html",
            '<div class="x"><span>Hi</span></div>',
            {"unit.root", "def.tag", "def.tag.name", "use.attr", "use.attr.name"},
            {"unit.root", "def.tag", "def.tag.name"},
        ),
        (
            "java",
            "import java.util.List; class Foo { void bar(){} } interface Baz {}",
            {
                "unit.root",
                "def.class",
                "def.class.name",
                "def.interface",
                "def.interface.name",
                "def.method",
                "def.method.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.class", "def.method", "rel.imports"},
        ),
        (
            "javascript",
            'import x from "y"; class Foo { bar(){} } function baz(){} obj.method(); foo();',
            {
                "unit.root",
                "def.class",
                "def.class.name",
                "def.func",
                "def.func.name",
                "def.method",
                "def.method.name",
                "rel.imports",
                "use.import.path",
                "use.call",
                "use.call.name",
                "use.attr",
            },
            {"unit.root", "def.class", "def.func", "rel.imports"},
        ),
        (
            "json",
            '{"name": "demo", "items": [1,2]}',
            {"unit.root", "def.pair", "def.key.name", "def.array"},
            {"unit.root", "def.pair", "def.key.name"},
        ),
        (
            "markdown",
            "# Title\n\n- Item",
            {"unit.root", "def.heading", "def.list.item"},
            {"unit.root", "def.heading", "def.list.item"},
        ),
        (
            "ruby",
            'require "json"\nclass Foo; def bar; end; end',
            {
                "unit.root",
                "def.class",
                "def.class.name",
                "def.method",
                "def.method.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.class", "def.method"},
        ),
        (
            "rust",
            "use std::io; struct Foo { x: i32 } enum Kind { A } fn bar() {}",
            {
                "unit.root",
                "def.struct",
                "def.struct.name",
                "def.enum",
                "def.enum.name",
                "def.func",
                "def.func.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.struct", "def.func", "rel.imports"},
        ),
        (
            "toml",
            '[package]\nname = "demo"',
            {"unit.root", "def.table", "def.table.name", "def.pair", "def.key.name"},
            {"unit.root", "def.table", "def.table.name"},
        ),
        (
            "tsx",
            'import React from "react"; export function App(){ return <div className="x" /> }',
            {
                "unit.root",
                "def.func",
                "def.func.name",
                "rel.imports",
                "use.import.path",
                "use.jsx",
                "use.jsx.name",
                "use.attr",
                "use.attr.name",
            },
            {"unit.root", "def.func", "rel.imports"},
        ),
        (
            "typescript",
            'import x from "y"; interface Foo { x: string } type Bar = { y: number }; function baz(){}',
            {
                "unit.root",
                "def.interface",
                "def.interface.name",
                "def.type",
                "def.type.name",
                "def.func",
                "def.func.name",
                "rel.imports",
                "use.import.path",
            },
            {"unit.root", "def.interface", "def.func", "rel.imports"},
        ),
        (
            "yaml",
            "key: value\nlist:\n  - item",
            {"unit.root", "def.pair", "def.key.name", "def.list.item"},
            {"unit.root", "def.pair", "def.key.name"},
        ),
    ],
)
def test_queries_capture_structure(
    language: str, source: str, expected_detailed: set[str], expected_high: set[str]
) -> None:
    queries_dir = Path(__file__).parent.parent.parent / "src" / "codex_graph" / "queries"
    detailed_path = queries_dir / f"{language}_detailed.scm"
    high_level_path = queries_dir / f"{language}_high_level.scm"

    assert detailed_path.exists()
    assert high_level_path.exists()

    language_obj = get_language(cast(SupportedLanguage, language))
    parser = get_parser(cast(SupportedLanguage, language))

    detailed_query = Query(language_obj, detailed_path.read_text(encoding="utf-8"))
    high_level_query = Query(language_obj, high_level_path.read_text(encoding="utf-8"))

    detailed_captures = _get_capture_names(detailed_query, parser, source)
    high_level_captures = _get_capture_names(high_level_query, parser, source)

    assert expected_detailed.issubset(detailed_captures)
    assert expected_high.issubset(high_level_captures)
