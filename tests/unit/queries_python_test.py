"""Unit tests for Python tree-sitter queries."""

from tree_sitter import Parser, Query, QueryCursor


def get_capture_names(query: Query, parser: Parser, source: str) -> set[str]:
    """Parse source and return all capture names found."""
    tree = parser.parse(source.encode("utf-8"))
    cursor = QueryCursor(query)
    captures: set[str] = set()
    for _, matched_captures in cursor.matches(tree.root_node):
        captures.update(matched_captures.keys())
    return captures


def get_captures_with_text(query: Query, parser: Parser, source: str) -> dict[str, list[str]]:
    """Parse source and return capture names mapped to their matched text."""
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    cursor = QueryCursor(query)
    result: dict[str, list[str]] = {}
    for _, matched_captures in cursor.matches(tree.root_node):
        for cap_name, nodes in matched_captures.items():
            if cap_name not in result:
                result[cap_name] = []
            for node in nodes:
                text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
                result[cap_name].append(text)
    return result


class TestPythonDetailedQueryModuleRoot:
    """Tests for module root capture."""

    def test_captures_module_root(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "x = 1"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "unit.root" in captures


class TestPythonDetailedQueryClassDefinitions:
    """Tests for class definition captures."""

    def test_captures_class_definition(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
class MyClass:
    pass
"""
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "def.class" in captures
        assert "def.class.name" in captures
        assert "MyClass" in captures["def.class.name"]

    def test_captures_multiple_classes(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
class First:
    pass

class Second:
    pass
"""
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "MyClass" not in captures.get("def.class.name", [])
        assert "First" in captures["def.class.name"]
        assert "Second" in captures["def.class.name"]


class TestPythonDetailedQueryFunctionDefinitions:
    """Tests for function definition captures."""

    def test_captures_function_definition(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def my_function():
    pass
"""
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "def.func" in captures
        assert "def.func.name" in captures
        assert "my_function" in captures["def.func.name"]

    def test_captures_method_definition(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
class MyClass:
    def my_method(self):
        pass
"""
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "def.func.name" in captures
        assert "my_method" in captures["def.func.name"]

    def test_captures_async_function(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
async def async_func():
    pass
"""
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "def.func.name" in captures
        assert "async_func" in captures["def.func.name"]


class TestPythonDetailedQueryImports:
    """Tests for import captures."""

    def test_captures_simple_import(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "import os"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "rel.imports" in captures
        assert "use.import.module" in captures
        assert "os" in captures["use.import.module"]

    def test_captures_import_from(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "from pathlib import Path"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "rel.imports" in captures
        assert "use.import.module" in captures
        assert "pathlib" in captures["use.import.module"]

    def test_captures_aliased_import(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "import numpy as np"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "use.import.module" in captures
        assert "use.import.alias" in captures
        assert "numpy" in captures["use.import.module"]
        assert "np" in captures["use.import.alias"]

    def test_captures_relative_import(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "from . import module"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "rel.imports" in captures
        assert "use.import.relative" in captures


class TestPythonDetailedQueryCalls:
    """Tests for call captures."""

    def test_captures_simple_call(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "print('hello')"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "use.call" in captures
        assert "use.call.name" in captures
        assert "print" in captures["use.call.name"]

    def test_captures_method_call(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "obj.method()"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "use.call.attrsite" in captures
        assert "use.call.recv" in captures
        assert "use.call.attr" in captures
        assert "obj" in captures["use.call.recv"]
        assert "method" in captures["use.call.attr"]


class TestPythonDetailedQueryAssignments:
    """Tests for assignment captures."""

    def test_captures_simple_assignment(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "x = 1"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "stmt.assign" in captures
        assert "use.write.var" in captures
        assert "x" in captures["use.write.var"]

    def test_captures_augmented_assignment(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "x += 1"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "stmt.assign.aug" in captures
        assert "use.write.var" in captures


class TestPythonDetailedQueryControlFlow:
    """Tests for control flow captures."""

    def test_captures_if_statement(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
if True:
    pass
elif False:
    pass
else:
    pass
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.if" in captures
        assert "ctrl.elif" in captures
        assert "ctrl.else" in captures

    def test_captures_for_loop(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
for i in range(10):
    pass
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.for" in captures

    def test_captures_while_loop(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
while True:
    break
    continue
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.while" in captures
        assert "ctrl.break" in captures
        assert "ctrl.continue" in captures

    def test_captures_comprehensions(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
a = [x for x in range(10)]
b = {x for x in range(10)}
c = {x: x for x in range(10)}
d = (x for x in range(10))
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.comp.list" in captures
        assert "ctrl.comp.set" in captures
        assert "ctrl.comp.dict" in captures
        assert "ctrl.genexpr" in captures


class TestPythonDetailedQueryExceptions:
    """Tests for exception handling captures."""

    def test_captures_try_except(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
try:
    pass
except Exception:
    pass
finally:
    pass
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.try" in captures
        assert "ctrl.catch" in captures
        assert "ctrl.finally" in captures

    def test_captures_raise(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "raise ValueError('error')"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.throw" in captures


class TestPythonDetailedQueryWithStatement:
    """Tests for with statement captures."""

    def test_captures_with_statement(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
with open('file') as f:
    pass
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.with" in captures


class TestPythonDetailedQueryAsyncAwait:
    """Tests for async/await captures."""

    def test_captures_await(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
async def foo():
    await bar()
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "async.await" in captures

    def test_captures_yield(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def gen():
    yield 1
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "async.yield" in captures

    def test_captures_return(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def foo():
    return 1
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.return" in captures

    def test_captures_pass(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def foo():
    pass
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "ctrl.pass" in captures


class TestPythonDetailedQueryScopeStatements:
    """Tests for scope-related statement captures."""

    def test_captures_assert(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "assert True"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "assert" in captures

    def test_captures_global(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def foo():
    global x
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "scope.global" in captures

    def test_captures_nonlocal(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = """
def outer():
    x = 1
    def inner():
        nonlocal x
"""
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "scope.nonlocal" in captures


class TestPythonDetailedQueryAttributes:
    """Tests for attribute access captures."""

    def test_captures_attribute_access(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "obj.attr"
        captures = get_captures_with_text(python_detailed_query, python_parser, source)
        assert "use.attr" in captures
        assert "use.attr.recv" in captures
        assert "use.attr.name" in captures
        assert "obj" in captures["use.attr.recv"]
        assert "attr" in captures["use.attr.name"]


class TestPythonDetailedQueryLiterals:
    """Tests for literal captures."""

    def test_captures_string_literal(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = '"hello"'
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "lit.str" in captures

    def test_captures_integer_literal(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "42"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "lit.int" in captures

    def test_captures_float_literal(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "3.14"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "lit.float" in captures

    def test_captures_boolean_literals(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "True and False"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "lit.bool" in captures

    def test_captures_none_literal(self, python_detailed_query: Query, python_parser: Parser) -> None:
        source = "None"
        captures = get_capture_names(python_detailed_query, python_parser, source)
        assert "lit.none" in captures


class TestPythonHighLevelQuery:
    """Tests for the high-level Python query."""

    def test_captures_class_definition(self, python_high_level_query: Query, python_parser: Parser) -> None:
        source = """
class MyClass:
    pass
"""
        captures = get_captures_with_text(python_high_level_query, python_parser, source)
        assert "def.class" in captures
        assert "def.class.name" in captures
        assert "MyClass" in captures["def.class.name"]

    def test_captures_function_definition(self, python_high_level_query: Query, python_parser: Parser) -> None:
        source = """
def my_function():
    pass
"""
        captures = get_captures_with_text(python_high_level_query, python_parser, source)
        assert "def.func" in captures
        assert "def.func.name" in captures
        assert "my_function" in captures["def.func.name"]

    def test_captures_imports(self, python_high_level_query: Query, python_parser: Parser) -> None:
        source = """
import os
from pathlib import Path
"""
        captures = get_capture_names(python_high_level_query, python_parser, source)
        assert "rel.imports" in captures
        assert "use.import.module" in captures
