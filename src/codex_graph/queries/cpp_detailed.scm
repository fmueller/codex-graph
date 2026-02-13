;; =========================
;; C++ structure queries
;; =========================

(translation_unit) @unit.root

(namespace_definition
  name: (namespace_identifier) @def.namespace.name) @def.namespace

(class_specifier
  name: (type_identifier) @def.class.name) @def.class

(struct_specifier
  name: (type_identifier) @def.struct.name) @def.struct

(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.func.name)) @def.func

(function_definition
  declarator: (function_declarator
    declarator: (field_identifier) @def.method.name)) @def.method

(preproc_include) @rel.imports
(preproc_include
  path: (system_lib_string) @use.import.path)
(preproc_include
  path: (string_literal) @use.import.path)
