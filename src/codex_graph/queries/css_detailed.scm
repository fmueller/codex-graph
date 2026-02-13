;; =========================
;; CSS structure queries
;; =========================

(stylesheet) @unit.root

(import_statement) @rel.imports
(import_statement
  (string_value
    (string_content) @use.import.path))

(rule_set) @def.rule

(rule_set
  (selectors
    (class_selector
      (class_name
        (identifier) @def.selector.name)))) @def.selector

(declaration
  (property_name) @use.property.name) @use.property
