;; =========================
;; Rust structure queries
;; =========================

(source_file) @unit.root

(struct_item
  name: (type_identifier) @def.struct.name) @def.struct

(function_item
  name: (identifier) @def.func.name) @def.func

(use_declaration) @rel.imports
