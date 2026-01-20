;; =========================
;; Go structure queries
;; =========================

;; Root / source file
(source_file) @unit.root

;; -------------------------
;; Package declaration
;; -------------------------
(package_clause
  (package_identifier) @def.package.name) @def.package

;; -------------------------
;; Struct / interface definitions (type declarations)
;; -------------------------
(type_declaration
  (type_spec
    name: (type_identifier) @def.type.name
    type: (struct_type))) @def.struct

(type_declaration
  (type_spec
    name: (type_identifier) @def.type.name
    type: (interface_type))) @def.interface

;; Generic type alias / named type
(type_declaration
  (type_spec
    name: (type_identifier) @def.type.name)) @def.type

;; -------------------------
;; Function / method definitions
;; -------------------------
(function_declaration
  name: (identifier) @def.func.name) @def.func

(method_declaration
  name: (field_identifier) @def.method.name
  receiver: (parameter_list
    (parameter_declaration
      type: (_) @def.method.recv.type))) @def.method

;; -------------------------
;; Imports
;; -------------------------
(import_declaration) @rel.imports

;; Single import: import "fmt"
(import_declaration
  (import_spec
    path: (interpreted_string_literal) @use.import.path))

;; Grouped imports: import ( "fmt" ; "os" )
(import_declaration
  (import_spec_list
    (import_spec
      path: (interpreted_string_literal) @use.import.path)))

;; Aliased imports: import f "fmt"
(import_declaration
  (import_spec
    name: (package_identifier) @use.import.alias
    path: (interpreted_string_literal) @use.import.path))

(import_declaration
  (import_spec_list
    (import_spec
      name: (package_identifier) @use.import.alias
      path: (interpreted_string_literal) @use.import.path)))

;; Dot imports: import . "fmt"
(import_declaration
  (import_spec
    name: (dot) @use.import.dot
    path: (interpreted_string_literal) @use.import.path))

;; Blank imports: import _ "net/http/pprof"
(import_declaration
  (import_spec
    name: (blank_identifier) @use.import.blank
    path: (interpreted_string_literal) @use.import.path))

;; =========================
;; Calls & instantiation
;; =========================

;; Generic calls (coarse)
(call_expression) @use.call

;; Simple callee identifiers: f(...)
(call_expression
  function: (identifier) @use.call.name)

;; Method/selector calls: obj.method(...)
(call_expression
  function: (selector_expression
    operand: (identifier) @use.call.recv
    field: (field_identifier) @use.call.attr)) @use.call.attrsite

;; Package-qualified calls: pkg.Func(...)
(call_expression
  function: (selector_expression
    operand: (identifier) @use.call.pkg
    field: (field_identifier) @use.call.func))

;; =========================
;; Assignments
;; =========================

;; Short variable declaration: x := value
(short_var_declaration) @stmt.assign.short

(short_var_declaration
  left: (expression_list
    (identifier) @use.write.var))

;; Assignment statement: x = value
(assignment_statement) @stmt.assign

(assignment_statement
  left: (expression_list
    (identifier) @use.write.var))

;; Increment/decrement: x++, x--
(inc_statement) @stmt.inc
(dec_statement) @stmt.dec

;; =========================
;; Variable declarations
;; =========================

(var_declaration) @stmt.var

(var_declaration
  (var_spec
    name: (identifier) @def.var.name))

(const_declaration) @stmt.const

(const_declaration
  (const_spec
    name: (identifier) @def.const.name))

;; =========================
;; Control flow: branches
;; =========================

(if_statement) @ctrl.if

(if_statement
  consequence: (block) @ctrl.if.then)

(if_statement
  alternative: (block) @ctrl.else)

(if_statement
  alternative: (if_statement) @ctrl.elif)

;; Switch statements
(expression_switch_statement) @ctrl.switch
(type_switch_statement) @ctrl.switch.type

(expression_case) @ctrl.case
(type_case) @ctrl.case.type
(default_case) @ctrl.default

;; Select (channel operations)
(select_statement) @ctrl.select
(communication_case) @ctrl.select.case

;; =========================
;; Control flow: loops
;; =========================

(for_statement) @ctrl.for

;; Range loops: for k, v := range collection
(for_statement
  (range_clause) @ctrl.range)

(break_statement) @ctrl.break
(continue_statement) @ctrl.continue

;; Labeled statements
(labeled_statement
  label: (label_name) @ctrl.label)

(goto_statement
  (label_name) @ctrl.goto)

;; =========================
;; Error handling & panics
;; =========================

(defer_statement) @ctrl.defer
(go_statement) @ctrl.go

;; Panic/recover are just function calls but commonly used for error handling
(call_expression
  function: (identifier) @builtin.panic
  (#eq? @builtin.panic "panic"))

(call_expression
  function: (identifier) @builtin.recover
  (#eq? @builtin.recover "recover"))

;; =========================
;; Return statements
;; =========================

(return_statement) @ctrl.return

;; =========================
;; Fallthrough (switch specific)
;; =========================

(fallthrough_statement) @ctrl.fallthrough

;; =========================
;; Selector / field access
;; =========================

(selector_expression
  operand: (identifier) @use.attr.recv
  field: (field_identifier) @use.attr.name) @use.attr

;; =========================
;; Type assertions and conversions
;; =========================

(type_assertion) @use.type.assert

(type_conversion_expression) @use.type.conv

;; =========================
;; Composite literals (struct/map/slice instantiation)
;; =========================

(composite_literal) @lit.composite

(composite_literal
  type: (type_identifier) @lit.composite.type)

(composite_literal
  type: (qualified_type
    package: (package_identifier) @lit.composite.pkg
    name: (type_identifier) @lit.composite.type))

;; =========================
;; Literals
;; =========================

(interpreted_string_literal) @lit.str
(raw_string_literal) @lit.str.raw
(rune_literal) @lit.rune
(int_literal) @lit.int
(float_literal) @lit.float
(imaginary_literal) @lit.imaginary
(true) @lit.bool
(false) @lit.bool
(nil) @lit.nil

;; =========================
;; Function literals (closures)
;; =========================

(func_literal) @def.func.anon

;; =========================
;; Channel operations
;; =========================

(send_statement) @chan.send
(receive_statement) @chan.recv

;; Make/new builtin calls
(call_expression
  function: (identifier) @builtin.make
  (#eq? @builtin.make "make"))

(call_expression
  function: (identifier) @builtin.new
  (#eq? @builtin.new "new"))
