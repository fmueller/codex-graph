;; =========================
;; TSX structure queries
;; =========================

(program) @unit.root

(class_declaration
  name: (type_identifier) @def.class.name) @def.class

(function_declaration
  name: (identifier) @def.func.name) @def.func

(method_definition
  name: (property_identifier) @def.method.name) @def.method

(import_statement) @rel.imports
(import_statement
  source: (string
    (string_fragment) @use.import.path))

(jsx_self_closing_element
  name: (identifier) @use.jsx.name) @use.jsx

(jsx_attribute
  (property_identifier) @use.attr.name) @use.attr
