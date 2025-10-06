;; =========================
;; Python structure queries
;; =========================

;; Root / module
(module) @unit.root

;; -------------------------
;; Class definitions
;; -------------------------
(class_definition
  (identifier) @def.class.name) @def.class

;; -------------------------
;; Function / method definitions
;; -------------------------
(function_definition
  (identifier) @def.func.name) @def.func

;; -------------------------
;; Imports
;; -------------------------
(import_statement) @rel.imports
(import_from_statement) @rel.imports

;; import X, Y as Z
(import_statement
  (dotted_name) @use.import.module)

(import_statement
  (aliased_import
    (dotted_name) @use.import.module
    (identifier) @use.import.alias))

;; from .pkg.subpkg import A, B as C
(import_from_statement
  (relative_import) @use.import.relative)

;; Module path in "from ... import ..."
(import_from_statement
  (dotted_name) @use.import.module)

;; Aliased imported names: from ... import A as C (A may be dotted)
(import_from_statement
  (aliased_import
    (dotted_name) @use.import.name
    (identifier) @use.import.alias))

;; Non-aliased imported names: from ... import A, B (names are dotted_name)
(import_from_statement
  (dotted_name) @use.import.name)
