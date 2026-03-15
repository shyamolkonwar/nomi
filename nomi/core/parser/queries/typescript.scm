;; Tree-sitter queries for TypeScript/JavaScript AST extraction
;; Nomi - Local Context Engine

;; query: function
(function_declaration
  name: (identifier) @function.name
  parameters: (formal_parameters) @function.params
  return_type: (type_annotation)? @function.return
  body: (statement_block) @function.body) @function.def

;; query: arrow_function
(arrow_function
  parameters: (formal_parameters) @arrow.params
  return_type: (type_annotation)? @arrow.return
  body: (_) @arrow.body) @arrow.def

;; query: function_expression
(function_expression
  name: (identifier)? @func_expr.name
  parameters: (formal_parameters) @func_expr.params
  body: (statement_block) @func_expr.body) @func_expr.def

;; query: class
(class_declaration
  name: (type_identifier) @class.name
  type_parameters: (type_parameters)? @class.type_params
  heritage: (class_heritage)? @class.heritage
  body: (class_body) @class.body) @class.def

;; query: method
(method_definition
  name: (property_identifier) @method.name
  parameters: (formal_parameters) @method.params
  return_type: (type_annotation)? @method.return
  body: (statement_block) @method.body) @method.def

;; query: interface
(interface_declaration
  name: (type_identifier) @interface.name
  type_parameters: (type_parameters)? @interface.type_params
  body: (object_type) @interface.body) @interface.def

;; query: type_alias
(type_alias_declaration
  name: (type_identifier) @type.name
  type_parameters: (type_parameters)? @type.params
  value: (_) @type.value) @type.def

;; query: import
(import_statement) @import
(import_clause) @import.clause
(namespace_import) @import.namespace
(named_imports) @import.named

;; query: export
(export_statement) @export
(export_clause) @export.clause

;; query: variable
(lexical_declaration
  (variable_declarator
    name: (identifier) @var.name
    type: (type_annotation)? @var.type
    value: (_)? @var.value)) @var.def

;; query: async_function
(async_function_declaration
  name: (identifier) @async_function.name
  parameters: (formal_parameters) @async_function.params
  body: (statement_block) @async_function.body) @async_function.def

;; query: generator_function
(generator_function_declaration
  name: (identifier) @generator.name
  parameters: (formal_parameters) @generator.params
  body: (statement_block) @generator.body) @generator.def
