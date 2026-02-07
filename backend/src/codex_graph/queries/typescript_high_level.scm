;; =========================
;; TypeScript structure queries
;; =========================

(program) @unit.root

(interface_declaration
  name: (type_identifier) @def.interface.name) @def.interface

(function_declaration
  name: (identifier) @def.func.name) @def.func

(import_statement) @rel.imports
