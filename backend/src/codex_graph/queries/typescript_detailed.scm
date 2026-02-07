;; =========================
;; TypeScript structure queries
;; =========================

(program) @unit.root

(interface_declaration
  name: (type_identifier) @def.interface.name) @def.interface

(type_alias_declaration
  name: (type_identifier) @def.type.name) @def.type

(function_declaration
  name: (identifier) @def.func.name) @def.func

(class_declaration
  name: (type_identifier) @def.class.name) @def.class

(import_statement) @rel.imports
(import_statement
  source: (string
    (string_fragment) @use.import.path))
