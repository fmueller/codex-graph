;; =========================
;; C# structure queries
;; =========================

(compilation_unit) @unit.root

(class_declaration
  name: (identifier) @def.class.name) @def.class

(method_declaration
  name: (identifier) @def.method.name) @def.method

(using_directive) @rel.imports
