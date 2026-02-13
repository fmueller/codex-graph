;; =========================
;; TSX structure queries
;; =========================

(program) @unit.root

(function_declaration
  name: (identifier) @def.func.name) @def.func

(import_statement) @rel.imports
