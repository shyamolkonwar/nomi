;; Tree-sitter queries for Go AST extraction
;; Nomi - Local Context Engine

;; query: function
(function_declaration
  name: (identifier) @function.name
  parameters: (parameter_list) @function.params
  result: (_)? @function.return
  body: (block) @function.body) @function.def

;; query: method
(method_declaration
  receiver: (parameter_list) @method.receiver
  name: (field_identifier) @method.name
  parameters: (parameter_list) @method.params
  result: (_)? @method.return
  body: (block) @method.body) @method.def

;; query: interface
(interface_type
  (method_elem) @interface.method) @interface.def

(type_declaration
  (type_spec
    name: (type_identifier) @interface.name
    type: (interface_type))) @interface.decl

;; query: struct
(type_declaration
  (type_spec
    name: (type_identifier) @struct.name
    type: (struct_type
      (field_declaration_list) @struct.fields))) @struct.def

;; query: import
(import_declaration) @import
(import_spec) @import.spec
(import_spec_list) @import.list

;; query: package
(package_clause) @package

;; query: const
(const_declaration
  (const_spec
    name: (identifier) @const.name
    type: (_)? @const.type
    value: (_)? @const.value)) @const.def

;; query: var
(var_declaration
  (var_spec
    name: (identifier) @var.name
    type: (_)? @var.type
    value: (_)? @var.value)) @var.def

;; query: type_alias
(type_declaration
  (type_spec
    name: (type_identifier) @type.name
    type: (_)? @type.value)) @type.def

;; query: init_function
(function_declaration
  name: (identifier) @init.name (#eq? @init.name "init")
  body: (block) @init.body) @init.def

;; query: main_function
(function_declaration
  name: (identifier) @main.name (#eq? @main.name "main")
  body: (block) @main.body) @main.def
