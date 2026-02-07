;; =========================
;; JavaScript structure queries
;; =========================

(program) @unit.root

(class_declaration
  name: (identifier) @def.class.name) @def.class

(function_declaration
  name: (identifier) @def.func.name) @def.func

(import_statement) @rel.imports
