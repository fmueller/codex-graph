;; =========================
;; C# structure queries
;; =========================

(compilation_unit) @unit.root

(namespace_declaration
  name: (identifier) @def.namespace.name) @def.namespace

(class_declaration
  name: (identifier) @def.class.name) @def.class

(interface_declaration
  name: (identifier) @def.interface.name) @def.interface

(method_declaration
  name: (identifier) @def.method.name) @def.method

(using_directive) @rel.imports
(using_directive
  (qualified_name) @use.import.path)
(using_directive
  (identifier) @use.import.path)
