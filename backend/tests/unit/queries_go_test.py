"""Unit tests for Go tree-sitter queries."""

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


class TestGoDetailedQuerySourceFile:
    """Tests for source file root capture."""

    def test_captures_source_file_root(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = "package main"
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "unit.root" in captures


class TestGoDetailedQueryPackage:
    """Tests for package declaration captures."""

    def test_captures_package_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = "package main"
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.package" in captures
        assert "def.package.name" in captures
        assert "main" in captures["def.package.name"]


class TestGoDetailedQueryTypeDefinitions:
    """Tests for type definition captures."""

    def test_captures_struct_definition(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

type Person struct {
    Name string
    Age  int
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.struct" in captures
        assert "def.type.name" in captures
        assert "Person" in captures["def.type.name"]

    def test_captures_interface_definition(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

type Reader interface {
    Read(p []byte) (n int, err error)
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.interface" in captures
        assert "def.type.name" in captures
        assert "Reader" in captures["def.type.name"]

    def test_captures_type_alias(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

type MyInt int
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.type" in captures
        assert "def.type.name" in captures
        assert "MyInt" in captures["def.type.name"]


class TestGoDetailedQueryFunctionDefinitions:
    """Tests for function definition captures."""

    def test_captures_function_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.func" in captures
        assert "def.func.name" in captures
        assert "main" in captures["def.func.name"]

    def test_captures_method_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

type Person struct{}

func (p Person) Greet() string {
    return "Hello"
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "def.method" in captures
        assert "def.method.name" in captures
        assert "Greet" in captures["def.method.name"]


class TestGoDetailedQueryImports:
    """Tests for import captures."""

    def test_captures_single_import(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

import "fmt"
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "rel.imports" in captures
        assert "use.import.path" in captures
        assert '"fmt"' in captures["use.import.path"]

    def test_captures_grouped_imports(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

import (
    "fmt"
    "os"
)
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "rel.imports" in captures
        assert "use.import.path" in captures
        assert '"fmt"' in captures["use.import.path"]
        assert '"os"' in captures["use.import.path"]

    def test_captures_aliased_import(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

import f "fmt"
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "use.import.alias" in captures
        assert "use.import.path" in captures
        assert "f" in captures["use.import.alias"]

    def test_captures_dot_import(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

import . "fmt"
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "use.import.dot" in captures
        assert "use.import.path" in captures

    def test_captures_blank_import(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

import _ "net/http/pprof"
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "use.import.blank" in captures
        assert "use.import.path" in captures


class TestGoDetailedQueryCalls:
    """Tests for call captures."""

    def test_captures_simple_call(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    println("hello")
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "use.call" in captures
        assert "use.call.name" in captures
        assert "println" in captures["use.call.name"]

    def test_captures_method_call(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    obj.Method()
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "use.call.attrsite" in captures
        assert "use.call.recv" in captures
        assert "use.call.attr" in captures
        assert "obj" in captures["use.call.recv"]
        assert "Method" in captures["use.call.attr"]


class TestGoDetailedQueryAssignments:
    """Tests for assignment captures."""

    def test_captures_short_var_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    x := 1
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "stmt.assign.short" in captures
        assert "use.write.var" in captures
        assert "x" in captures["use.write.var"]

    def test_captures_assignment_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var x int

func main() {
    x = 1
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "stmt.assign" in captures

    def test_captures_increment_decrement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    x := 0
    x++
    x--
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "stmt.inc" in captures
        assert "stmt.dec" in captures


class TestGoDetailedQueryVariableDeclarations:
    """Tests for variable declaration captures."""

    def test_captures_var_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var x int
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "stmt.var" in captures
        assert "def.var.name" in captures
        assert "x" in captures["def.var.name"]

    def test_captures_const_declaration(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

const Pi = 3.14
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "stmt.const" in captures
        assert "def.const.name" in captures
        assert "Pi" in captures["def.const.name"]


class TestGoDetailedQueryControlFlow:
    """Tests for control flow captures."""

    def test_captures_if_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    if true {
    } else if false {
    } else {
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.if" in captures
        assert "ctrl.if.then" in captures
        assert "ctrl.elif" in captures
        assert "ctrl.else" in captures

    def test_captures_for_loop(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    for i := 0; i < 10; i++ {
        break
        continue
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.for" in captures
        assert "ctrl.break" in captures
        assert "ctrl.continue" in captures

    def test_captures_range_loop(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    items := []int{1, 2, 3}
    for _, v := range items {
        _ = v
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.for" in captures
        assert "ctrl.range" in captures

    def test_captures_switch_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    x := 1
    switch x {
    case 1:
    default:
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.switch" in captures
        assert "ctrl.case" in captures
        assert "ctrl.default" in captures

    def test_captures_select_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    ch := make(chan int)
    select {
    case <-ch:
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.select" in captures
        assert "ctrl.select.case" in captures

    def test_captures_labeled_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
Loop:
    for {
        break Loop
    }
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.label" in captures

    def test_captures_goto_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    goto End
End:
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.goto" in captures


class TestGoDetailedQueryDeferGo:
    """Tests for defer and go statement captures."""

    def test_captures_defer_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    defer cleanup()
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.defer" in captures

    def test_captures_go_statement(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    go worker()
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.go" in captures


class TestGoDetailedQueryPanicRecover:
    """Tests for panic/recover builtin captures."""

    def test_captures_panic(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    panic("error")
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "builtin.panic" in captures

    def test_captures_recover(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    defer func() {
        recover()
    }()
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "builtin.recover" in captures


class TestGoDetailedQueryReturn:
    """Tests for return statement captures."""

    def test_captures_return(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func foo() int {
    return 1
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "ctrl.return" in captures


class TestGoDetailedQuerySelectors:
    """Tests for selector/field access captures."""

    def test_captures_selector_expression(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    obj.field
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "use.attr" in captures
        assert "use.attr.recv" in captures
        assert "use.attr.name" in captures
        assert "obj" in captures["use.attr.recv"]
        assert "field" in captures["use.attr.name"]


class TestGoDetailedQueryTypeAssertions:
    """Tests for type assertion captures."""

    def test_captures_type_assertion(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    var i interface{} = "hello"
    _ = i.(string)
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "use.type.assert" in captures


class TestGoDetailedQueryCompositeLiterals:
    """Tests for composite literal captures."""

    def test_captures_composite_literal(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

type Person struct {
    Name string
}

func main() {
    p := Person{Name: "John"}
    _ = p
}
"""
        captures = get_captures_with_text(go_detailed_query, go_parser, source)
        assert "lit.composite" in captures
        assert "lit.composite.type" in captures
        assert "Person" in captures["lit.composite.type"]


class TestGoDetailedQueryLiterals:
    """Tests for literal captures."""

    def test_captures_string_literals(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var (
    s1 = "hello"
    s2 = `raw string`
)
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "lit.str" in captures
        assert "lit.str.raw" in captures

    def test_captures_numeric_literals(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var (
    i = 42
    f = 3.14
    c = 1i
)
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "lit.int" in captures
        assert "lit.float" in captures
        assert "lit.imaginary" in captures

    def test_captures_boolean_literals(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var (
    t = true
    f = false
)
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "lit.bool" in captures

    def test_captures_nil_literal(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var x *int = nil
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "lit.nil" in captures

    def test_captures_rune_literal(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

var r = 'a'
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "lit.rune" in captures


class TestGoDetailedQueryFunctionLiterals:
    """Tests for function literal captures."""

    def test_captures_func_literal(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    f := func() {}
    _ = f
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "def.func.anon" in captures


class TestGoDetailedQueryChannelOperations:
    """Tests for channel operation captures."""

    def test_captures_channel_send(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    ch := make(chan int)
    ch <- 1
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "chan.send" in captures

    def test_captures_make_builtin(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    ch := make(chan int)
    _ = ch
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "builtin.make" in captures

    def test_captures_new_builtin(self, go_detailed_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {
    p := new(int)
    _ = p
}
"""
        captures = get_capture_names(go_detailed_query, go_parser, source)
        assert "builtin.new" in captures


class TestGoHighLevelQuery:
    """Tests for the high-level Go query."""

    def test_captures_package(self, go_high_level_query: Query, go_parser: Parser) -> None:
        source = "package main"
        captures = get_captures_with_text(go_high_level_query, go_parser, source)
        assert "def.package" in captures
        assert "def.package.name" in captures
        assert "main" in captures["def.package.name"]

    def test_captures_function(self, go_high_level_query: Query, go_parser: Parser) -> None:
        source = """
package main

func main() {}
"""
        captures = get_captures_with_text(go_high_level_query, go_parser, source)
        assert "def.func" in captures
        assert "def.func.name" in captures
        assert "main" in captures["def.func.name"]

    def test_captures_struct(self, go_high_level_query: Query, go_parser: Parser) -> None:
        source = """
package main

type Person struct{}
"""
        captures = get_captures_with_text(go_high_level_query, go_parser, source)
        assert "def.struct" in captures
        assert "def.type.name" in captures
        assert "Person" in captures["def.type.name"]

    def test_captures_imports(self, go_high_level_query: Query, go_parser: Parser) -> None:
        source = """
package main

import "fmt"
"""
        captures = get_capture_names(go_high_level_query, go_parser, source)
        assert "rel.imports" in captures
        assert "use.import.path" in captures
