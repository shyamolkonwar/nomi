;; Tree-sitter queries for Python AST extraction
;; Nomi - Local Context Engine

;; query: function
(function_definition
  name: (identifier) @function.name
  parameters: (parameters) @function.params
  return_type: (type)? @function.return
  body: (block) @function.body) @function.def

;; query: class
(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list)? @class.bases
  body: (block) @class.body) @class.def

;; query: method
;; Methods are function_definitions within class bodies
;; They are extracted separately by the extractor

;; query: import
(import_statement) @import
(import_from_statement) @import

;; query: decorator
(decorator) @decorator

;; query: async_function
(async_function_definition
  name: (identifier) @async_function.name
  parameters: (parameters) @async_function.params
  body: (block) @async_function.body) @async_function.def

;; query: lambda
(lambda) @lambda

;; query: assignment
(assignment
  left: (identifier) @assignment.name
  right: (_) @assignment.value) @assignment

;; query: augmented_assignment
(augmented_assignment
  left: (identifier) @aug_assign.name
  right: (_) @aug_assign.value) @aug_assign

;; query: global
(global_statement) @global

;; query: nonlocal
(nonlocal_statement) @nonlocal
