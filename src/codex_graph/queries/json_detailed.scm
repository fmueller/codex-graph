;; =========================
;; JSON structure queries
;; =========================

(document) @unit.root

(object) @def.object

(pair
  key: (string
    (string_content) @def.key.name)) @def.pair

(array) @def.array
