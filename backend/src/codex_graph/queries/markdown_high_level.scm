;; =========================
;; Markdown structure queries
;; =========================

(document) @unit.root

(atx_heading
  heading_content: (inline) @def.heading) @def.heading

(list_item) @def.list.item
