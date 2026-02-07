;; =========================
;; Ruby structure queries
;; =========================

(program) @unit.root

(class
  name: (constant) @def.class.name) @def.class

(module
  name: (constant) @def.module.name) @def.module

(method
  name: (identifier) @def.method.name) @def.method

(call
  method: (identifier) @use.import.name
  arguments: (argument_list
    (string (string_content) @use.import.path))) @rel.imports
(#match? @use.import.name "^require(_relative)?$")
