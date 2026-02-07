;; =========================
;; HTML structure queries
;; =========================

(document) @unit.root

(element
  (start_tag
    (tag_name) @def.tag.name)) @def.tag

(attribute
  (attribute_name) @use.attr.name) @use.attr
