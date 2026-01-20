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
