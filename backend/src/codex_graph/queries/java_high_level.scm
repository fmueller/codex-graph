;; =========================
;; Java structure queries
;; =========================

(program) @unit.root

(class_declaration
  name: (identifier) @def.class.name) @def.class

(method_declaration
  name: (identifier) @def.method.name) @def.method

(import_declaration) @rel.imports
