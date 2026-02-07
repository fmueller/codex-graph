;; =========================
;; JavaScript structure queries
;; =========================

(program) @unit.root

(class_declaration
  name: (identifier) @def.class.name) @def.class

(function_declaration
  name: (identifier) @def.func.name) @def.func

(method_definition
  name: (property_identifier) @def.method.name) @def.method

(import_statement) @rel.imports
(import_statement
  source: (string
    (string_fragment) @use.import.path))

(call_expression) @use.call
(call_expression
  function: (identifier) @use.call.name)

(member_expression
  object: (identifier) @use.attr.recv
  property: (property_identifier) @use.attr.name) @use.attr
