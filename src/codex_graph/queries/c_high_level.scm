;; =========================
;; C structure queries
;; =========================

(translation_unit) @unit.root

(struct_specifier
  name: (type_identifier) @def.struct.name) @def.struct

(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.func.name)) @def.func

(preproc_include) @rel.imports
