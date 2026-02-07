;; =========================
;; Ruby structure queries
;; =========================

(program) @unit.root

(class
  name: (constant) @def.class.name) @def.class

(method
  name: (identifier) @def.method.name) @def.method
