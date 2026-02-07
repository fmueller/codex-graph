;; =========================
;; Java structure queries
;; =========================

(program) @unit.root

(class_declaration
  name: (identifier) @def.class.name) @def.class

(interface_declaration
  name: (identifier) @def.interface.name) @def.interface

(method_declaration
  name: (identifier) @def.method.name) @def.method

(import_declaration) @rel.imports
(import_declaration
  (scoped_identifier) @use.import.path)
