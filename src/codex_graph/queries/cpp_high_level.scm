;; =========================
;; C++ structure queries
;; =========================

(translation_unit) @unit.root

(class_specifier
  name: (type_identifier) @def.class.name) @def.class

(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.func.name)) @def.func

(preproc_include) @rel.imports
