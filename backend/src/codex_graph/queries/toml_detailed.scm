;; =========================
;; TOML structure queries
;; =========================

(document) @unit.root

(table
  (bare_key) @def.table.name) @def.table

(pair
  (bare_key) @def.key.name) @def.pair
