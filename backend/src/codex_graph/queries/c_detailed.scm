;; =========================
;; C structure queries
;; =========================

(translation_unit) @unit.root

;; Structs / enums / typedefs
(struct_specifier
  name: (type_identifier) @def.struct.name) @def.struct

(enum_specifier
  name: (type_identifier) @def.enum.name) @def.enum

(type_definition
  declarator: (type_identifier) @def.type.name) @def.type

;; Function definitions
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.func.name)) @def.func

;; Imports
(preproc_include) @rel.imports
(preproc_include
  path: (system_lib_string) @use.import.path)
(preproc_include
  path: (string_literal) @use.import.path)
