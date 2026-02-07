;; =========================
;; YAML structure queries
;; =========================

(stream) @unit.root

(block_mapping_pair
  key: (_) @def.key.name) @def.pair

(block_sequence_item) @def.list.item
