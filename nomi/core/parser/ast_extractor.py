"""AST extraction module for Nomi.

This module provides utilities to extract CodeUnits from parsed ASTs
using tree-sitter queries for various programming languages.
"""

import logging
from pathlib import Path
from typing import List, Optional

from tree_sitter import Tree, Node, Query

from nomi.core.parser.engine import TreeSitterEngine
from nomi.core.parser.node_mapper import NodeMapper
from nomi.discovery.language_detector import Language
from nomi.storage.models import CodeUnit

logger = logging.getLogger(__name__)


class ASTExtractor:
    """Extracts CodeUnits from AST trees using tree-sitter queries.

    This class provides methods to extract functions, classes, methods,
    imports, and other code units from parsed source files.
    """

    def __init__(self, engine: Optional[TreeSitterEngine] = None) -> None:
        """Initialize the AST extractor.

        Args:
            engine: Optional TreeSitterEngine instance. If not provided,
                   a new one will be created.
        """
        self.engine = engine or TreeSitterEngine()
        self._query_cache: dict[Language, dict[str, Query]] = {}
        self._load_queries()

    def _load_queries(self) -> None:
        """Load tree-sitter query files for supported languages."""
        queries_dir = Path(__file__).parent / "queries"

        for language in Language:
            if language == Language.UNKNOWN:
                continue

            query_file = queries_dir / f"{language.value}.scm"
            if query_file.exists():
                try:
                    query_text = query_file.read_text()
                    self._query_cache[language] = self._parse_query_file(language, query_text)
                except Exception as e:
                    logger.warning(f"Failed to load queries for {language.value}: {e}")

    def _parse_query_file(self, language: Language, query_text: str) -> dict[str, Query]:
        """Parse a query file and create Query objects.

        Args:
            language: The language for the queries.
            query_text: The query file content.

        Returns:
            Dictionary mapping query names to Query objects.
        """
        queries = {}
        ts_language = self.engine._languages.get(language)

        if not ts_language:
            return queries

        # Parse named queries from the file
        current_name = None
        current_lines = []

        for line in query_text.split("\n"):
            stripped = line.strip()

            # Check for query name comment: ;; query: name
            if stripped.startswith(";; query:"):
                # Save previous query if exists
                if current_name and current_lines:
                    query_str = "\n".join(current_lines)
                    try:
                        queries[current_name] = Query(ts_language, query_str)
                    except Exception as e:
                        logger.warning(f"Failed to parse query '{current_name}': {e}")

                current_name = stripped.replace(";; query:", "").strip()
                current_lines = []
            elif current_name:
                current_lines.append(line)

        # Save last query
        if current_name and current_lines:
            query_str = "\n".join(current_lines)
            try:
                queries[current_name] = Query(ts_language, query_str)
            except Exception as e:
                logger.warning(f"Failed to parse query '{current_name}': {e}")

        return queries

    def extract_from_file(self, file_path: str, language: Language) -> List[CodeUnit]:
        """Extract all CodeUnits from a source file.

        Args:
            file_path: Absolute path to the source file.
            language: The programming language of the file.

        Returns:
            List of extracted CodeUnits.
        """
        tree = self.engine.parse_file(file_path, language)
        if not tree:
            logger.warning(f"Failed to parse file: {file_path}")
            return []

        path = Path(file_path)
        try:
            source_bytes = path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        return self.extract_from_tree(tree, source_bytes, file_path, language)

    def extract_from_tree(self, tree: Tree, source_bytes: bytes, file_path: str, language: Language) -> List[CodeUnit]:
        """Extract all CodeUnits from a parsed AST tree.

        Args:
            tree: The parsed syntax tree.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of extracted CodeUnits.
        """
        units = []

        # Extract functions
        units.extend(self.extract_functions(tree, source_bytes, file_path, language))

        # Extract classes
        units.extend(self.extract_classes(tree, source_bytes, file_path, language))

        # Extract methods (already included in class extraction for most languages)
        # units.extend(self.extract_methods(tree, source_bytes, file_path, language))

        return units

    def extract_functions(self, tree: Tree, source_bytes: bytes, file_path: str, language: Language) -> List[CodeUnit]:
        """Extract function definitions from an AST tree.

        Args:
            tree: The parsed syntax tree.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of function CodeUnits.
        """
        functions = []
        mapper = NodeMapper(language)
        root_node = tree.root_node

        # Use query if available
        query = self._get_query(language, "function")
        if query:
            captures = query.captures(root_node)
            for node, capture_name in captures:
                if "def" in capture_name or "definition" in capture_name:
                    try:
                        code_unit = mapper.map_function_node(node, source_bytes, file_path)
                        functions.append(code_unit)
                    except Exception as e:
                        logger.warning(f"Failed to map function node: {e}")
        else:
            # Fallback: manual traversal
            functions = self._extract_functions_manual(root_node, source_bytes, file_path, language)

        return functions

    def extract_classes(self, tree: Tree, source_bytes: bytes, file_path: str, language: Language) -> List[CodeUnit]:
        """Extract class definitions from an AST tree.

        Args:
            tree: The parsed syntax tree.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of class CodeUnits (including methods as dependencies).
        """
        classes = []
        mapper = NodeMapper(language)
        root_node = tree.root_node

        # Use query if available
        query = self._get_query(language, "class")
        if query:
            captures = query.captures(root_node)
            for node, capture_name in captures:
                if "def" in capture_name or "definition" in capture_name:
                    try:
                        code_unit = mapper.map_class_node(node, source_bytes, file_path)
                        classes.append(code_unit)

                        # Also extract methods within this class
                        methods = self._extract_methods_from_class(node, source_bytes, file_path, language, mapper)
                        classes.extend(methods)
                    except Exception as e:
                        logger.warning(f"Failed to map class node: {e}")
        else:
            # Fallback: manual traversal
            classes = self._extract_classes_manual(root_node, source_bytes, file_path, language)

        return classes

    def extract_methods(self, tree: Tree, source_bytes: bytes, file_path: str, language: Language) -> List[CodeUnit]:
        """Extract method definitions from an AST tree.

        Note: For most languages, methods are extracted as part of class extraction.
        This method extracts standalone methods (e.g., Go methods with receivers).

        Args:
            tree: The parsed syntax tree.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of method CodeUnits.
        """
        methods = []
        mapper = NodeMapper(language)
        root_node = tree.root_node

        # Use query if available
        query = self._get_query(language, "method")
        if query:
            captures = query.captures(root_node)
            for node, capture_name in captures:
                if "def" in capture_name:
                    try:
                        # For standalone methods, we need to determine the receiver class
                        class_name = self._extract_receiver_class(node, source_bytes)
                        code_unit = mapper.map_method_node(node, source_bytes, file_path, class_name)
                        methods.append(code_unit)
                    except Exception as e:
                        logger.warning(f"Failed to map method node: {e}")

        return methods

    def extract_imports(self, tree: Tree, source_bytes: bytes, file_path: str, language: Language) -> List[str]:
        """Extract import statements from an AST tree.

        Args:
            tree: The parsed syntax tree.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of imported module/package names.
        """
        imports = []
        root_node = tree.root_node

        # Use query if available
        query = self._get_query(language, "import")
        if query:
            captures = query.captures(root_node)
            for node, capture_name in captures:
                import_text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                imports.append(import_text)
        else:
            # Fallback: manual extraction
            imports = self._extract_imports_manual(root_node, source_bytes, language)

        return imports

    def _get_query(self, language: Language, query_name: str) -> Optional[Query]:
        """Get a cached query for a language.

        Args:
            language: The programming language.
            query_name: The name of the query.

        Returns:
            The Query object if found, None otherwise.
        """
        language_queries = self._query_cache.get(language, {})
        return language_queries.get(query_name)

    def _extract_methods_from_class(
        self,
        class_node: Node,
        source_bytes: bytes,
        file_path: str,
        language: Language,
        mapper: NodeMapper,
    ) -> List[CodeUnit]:
        """Extract methods from within a class node.

        Args:
            class_node: The class definition AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.
            mapper: The NodeMapper instance.

        Returns:
            List of method CodeUnits.
        """
        methods = []
        class_name = self._get_node_name(class_node, source_bytes)

        # Find the body node
        body_node = None
        for child in class_node.children:
            if child.type in {"block", "suite", "class_body", "body"}:
                body_node = child
                break

        if not body_node:
            return methods

        # Look for method definitions in the body
        for child in body_node.children:
            if self._is_method_definition(child, language):
                try:
                    code_unit = mapper.map_method_node(child, source_bytes, file_path, class_name)
                    methods.append(code_unit)
                except Exception as e:
                    logger.warning(f"Failed to map method node: {e}")

        return methods

    def _extract_receiver_class(self, node: Node, source_bytes: bytes) -> str:
        """Extract the receiver class name for a method.

        Args:
            node: The method AST node.
            source_bytes: The source code as bytes.

        Returns:
            The receiver class name.
        """
        # Look for receiver parameter (common in Go, Rust)
        for child in node.children:
            if child.type == "parameter_list":
                for param in child.children:
                    if param.type == "parameter_declaration":
                        # Check for receiver type
                        for subchild in param.children:
                            if subchild.type in {
                                "pointer_type",
                                "type_identifier",
                                "qualified_type",
                            }:
                                return source_bytes[subchild.start_byte:subchild.end_byte].decode(
                                    "utf-8", errors="replace"
                                )
        return "unknown"

    def _is_method_definition(self, node: Node, language: Language) -> bool:
        """Check if a node is a method definition.

        Args:
            node: The AST node to check.
            language: The programming language.

        Returns:
            True if the node is a method definition.
        """
        method_types = {
            "function_definition",
            "method_definition",
            "method_declaration",
        }
        return node.type in method_types

    def _get_node_name(self, node: Node, source_bytes: bytes) -> str:
        """Extract the name from a definition node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The name of the defined symbol.
        """
        for child in node.children:
            if child.type == "identifier":
                return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        return "unknown"

    def _extract_functions_manual(
        self, node: Node, source_bytes: bytes, file_path: str, language: Language
    ) -> List[CodeUnit]:
        """Manually extract functions by traversing the AST.

        Args:
            node: The current AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of function CodeUnits.
        """
        functions = []
        mapper = NodeMapper(language)

        # Check if current node is a function
        function_types = {
            "function_definition",
            "function_declaration",
            "arrow_function",
        }

        if node.type in function_types:
            try:
                code_unit = mapper.map_function_node(node, source_bytes, file_path)
                functions.append(code_unit)
            except Exception as e:
                logger.warning(f"Failed to map function node: {e}")

        # Recursively check children
        for child in node.children:
            functions.extend(self._extract_functions_manual(child, source_bytes, file_path, language))

        return functions

    def _extract_classes_manual(
        self, node: Node, source_bytes: bytes, file_path: str, language: Language
    ) -> List[CodeUnit]:
        """Manually extract classes by traversing the AST.

        Args:
            node: The current AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            language: The programming language.

        Returns:
            List of class CodeUnits.
        """
        classes = []
        mapper = NodeMapper(language)

        # Check if current node is a class
        class_types = {
            "class_definition",
            "class_declaration",
            "struct_type",
        }

        if node.type in class_types:
            try:
                code_unit = mapper.map_class_node(node, source_bytes, file_path)
                classes.append(code_unit)

                # Extract methods
                methods = self._extract_methods_from_class(node, source_bytes, file_path, language, mapper)
                classes.extend(methods)
            except Exception as e:
                logger.warning(f"Failed to map class node: {e}")

        # Recursively check children
        for child in node.children:
            classes.extend(self._extract_classes_manual(child, source_bytes, file_path, language))

        return classes

    def _extract_imports_manual(self, node: Node, source_bytes: bytes, language: Language) -> List[str]:
        """Manually extract imports by traversing the AST.

        Args:
            node: The current AST node.
            source_bytes: The source code as bytes.
            language: The programming language.

        Returns:
            List of import statements.
        """
        imports = []

        # Check if current node is an import
        import_types = {
            "import_statement",
            "import_from_statement",
            "import_declaration",
            "source_file_clause",
        }

        if node.type in import_types:
            import_text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            imports.append(import_text)

        # Recursively check children
        for child in node.children:
            imports.extend(self._extract_imports_manual(child, source_bytes, language))

        return imports
