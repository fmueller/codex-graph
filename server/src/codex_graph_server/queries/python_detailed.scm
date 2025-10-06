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

;; =========================
;; Calls & instantiation
;; =========================

;; Generic calls (coarse)
(call) @use.call

;; Simple callee identifiers: f(...)
(call
  (identifier) @use.call.name)

;; Attribute calls: obj.method(...)
(call
  (attribute
    (identifier) @use.call.recv
    (identifier) @use.call.attr)) @use.call.attrsite

;; =========================
;; Assignments (coarse, fieldless to avoid incompat)
;; =========================

(assignment) @stmt.assign
(augmented_assignment) @stmt.assign.aug

;; Try to catch very simple LHS identifiers (best-effort, safe)
(assignment
  (identifier) @use.write.var)
(augmented_assignment
  (identifier) @use.write.var)

;; =========================
;; Control flow: branches
;; =========================

(if_statement) @ctrl.if
(elif_clause) @ctrl.elif
(else_clause) @ctrl.else

;; (match_statement) / (case_clause) removed for compatibility

;; =========================
;; Control flow: loops & comps
;; =========================

(for_statement) @ctrl.for
(while_statement) @ctrl.while

(list_comprehension)       @ctrl.comp.list
(set_comprehension)        @ctrl.comp.set
(dictionary_comprehension) @ctrl.comp.dict
(generator_expression)     @ctrl.genexpr

(break_statement)    @ctrl.break
(continue_statement) @ctrl.continue

;; =========================
;; Exceptions
;; =========================

(try_statement)     @ctrl.try
(except_clause)     @ctrl.catch
(finally_clause)    @ctrl.finally
(raise_statement)   @ctrl.throw

;; =========================
;; Resource & context guards
;; =========================

(with_statement) @ctrl.with

;; =========================
;; Async / coroutine markers (older grammar)
;; =========================

(await)             @async.await
(yield)             @async.yield
(return_statement)  @ctrl.return
(pass_statement)    @ctrl.pass

;; =========================
;; Assertions & scope hints
;; =========================

(assert_statement)  @assert
(global_statement)  @scope.global
(nonlocal_statement) @scope.nonlocal

;; =========================
;; Simple member/attribute use
;; =========================

(attribute
  (identifier) @use.attr.recv
  (identifier) @use.attr.name) @use.attr

;; =========================
;; Optional: literals of interest
;; =========================

(string)  @lit.str
(integer) @lit.int
(float)   @lit.float
(true)    @lit.bool
(false)   @lit.bool
(none)    @lit.none
