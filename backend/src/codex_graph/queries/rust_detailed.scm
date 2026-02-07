;; =========================
;; Rust structure queries
;; =========================

(source_file) @unit.root

(struct_item
  name: (type_identifier) @def.struct.name) @def.struct

(enum_item
  name: (type_identifier) @def.enum.name) @def.enum

(function_item
  name: (identifier) @def.func.name) @def.func

(impl_item
  type: (type_identifier) @def.impl.name) @def.impl

(use_declaration) @rel.imports
(use_declaration
  argument: (scoped_identifier) @use.import.path)
(use_declaration
  argument: (identifier) @use.import.name)
