"""AST node to CodeUnit mapper for Nomi.

This module provides utilities to map tree-sitter AST nodes to CodeUnit models,
extracting signatures, bodies, docstrings, and other metadata.
"""

from typing import Optional, Tuple

from tree_sitter import Node

from nomi.discovery.language_detector import Language
from nomi.storage.models import CodeUnit, UnitKind


class NodeMapper:
    """Maps tree-sitter AST nodes to CodeUnit models.

    This class provides methods to extract structured information from AST nodes
    and convert them into CodeUnit representations.
    """

    def __init__(self, language: Language) -> None:
        """Initialize the node mapper.

        Args:
            language: The programming language being parsed.
        """
        self.language = language

    def map_function_node(self, node: Node, source_bytes: bytes, file_path: str) -> CodeUnit:
        """Map a function definition node to a CodeUnit.

        Args:
            node: The function definition AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.

        Returns:
            A CodeUnit representing the function.
        """
        name = self._extract_node_name(node, source_bytes)
        signature = self.extract_signature(node, source_bytes)
        body = self.extract_body(node, source_bytes)
        docstring = self.extract_docstring(node, source_bytes)
        byte_range = self._get_byte_range(node)
        line_range = self._get_line_range(node)
        unit_id = self.generate_unit_id(file_path, name)

        return CodeUnit(
            id=unit_id,
            unit_kind=UnitKind.FUNCTION,
            file_path=file_path,
            byte_range=byte_range,
            line_range=line_range,
            signature=signature,
            body=body,
            docstring=docstring,
            language=self.language.value,
        )

    def map_class_node(self, node: Node, source_bytes: bytes, file_path: str) -> CodeUnit:
        """Map a class definition node to a CodeUnit.

        Args:
            node: The class definition AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.

        Returns:
            A CodeUnit representing the class.
        """
        name = self._extract_node_name(node, source_bytes)
        signature = self.extract_signature(node, source_bytes)
        body = self.extract_body(node, source_bytes)
        docstring = self.extract_docstring(node, source_bytes)
        byte_range = self._get_byte_range(node)
        line_range = self._get_line_range(node)
        unit_id = self.generate_unit_id(file_path, name)

        return CodeUnit(
            id=unit_id,
            unit_kind=UnitKind.CLASS,
            file_path=file_path,
            byte_range=byte_range,
            line_range=line_range,
            signature=signature,
            body=body,
            docstring=docstring,
            language=self.language.value,
        )

    def map_method_node(self, node: Node, source_bytes: bytes, file_path: str, class_name: str) -> CodeUnit:
        """Map a method definition node to a CodeUnit.

        Args:
            node: The method definition AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.
            class_name: The name of the containing class.

        Returns:
            A CodeUnit representing the method.
        """
        name = self._extract_node_name(node, source_bytes)
        signature = self.extract_signature(node, source_bytes)
        body = self.extract_body(node, source_bytes)
        docstring = self.extract_docstring(node, source_bytes)
        byte_range = self._get_byte_range(node)
        line_range = self._get_line_range(node)
        unit_id = self.generate_unit_id(file_path, f"{class_name}.{name}")

        return CodeUnit(
            id=unit_id,
            unit_kind=UnitKind.METHOD,
            file_path=file_path,
            byte_range=byte_range,
            line_range=line_range,
            signature=signature,
            body=body,
            docstring=docstring,
            language=self.language.value,
        )

    def map_interface_node(self, node: Node, source_bytes: bytes, file_path: str) -> CodeUnit:
        """Map an interface definition node to a CodeUnit.

        Args:
            node: The interface definition AST node.
            source_bytes: The source code as bytes.
            file_path: Absolute path to the source file.

        Returns:
            A CodeUnit representing the interface.
        """
        name = self._extract_node_name(node, source_bytes)
        signature = self.extract_signature(node, source_bytes)
        body = self.extract_body(node, source_bytes)
        byte_range = self._get_byte_range(node)
        line_range = self._get_line_range(node)
        unit_id = self.generate_unit_id(file_path, name)

        return CodeUnit(
            id=unit_id,
            unit_kind=UnitKind.INTERFACE,
            file_path=file_path,
            byte_range=byte_range,
            line_range=line_range,
            signature=signature,
            body=body,
            language=self.language.value,
        )

    def extract_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract the signature (declaration without body) from a node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The signature as a string.
        """
        if self.language == Language.PYTHON:
            return self._extract_python_signature(node, source_bytes)
        elif self.language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
            return self._extract_typescript_signature(node, source_bytes)
        elif self.language == Language.GO:
            return self._extract_go_signature(node, source_bytes)
        else:
            # Default: return the full node text
            return self._get_node_text(node, source_bytes)

    def extract_body(self, node: Node, source_bytes: bytes) -> str:
        """Extract the body from a node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The body as a string.
        """
        body_node = self._find_body_node(node)
        if body_node:
            return self._get_node_text(body_node, source_bytes)
        return ""

    def extract_docstring(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extract the docstring from a node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The docstring if found, None otherwise.
        """
        if self.language == Language.PYTHON:
            return self._extract_python_docstring(node, source_bytes)
        elif self.language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
            return self._extract_js_ts_docstring(node, source_bytes)
        elif self.language == Language.GO:
            return self._extract_go_docstring(node, source_bytes)
        return None

    def generate_unit_id(self, file_path: str, symbol_name: str) -> str:
        """Generate a unique identifier for a code unit.

        Args:
            file_path: Absolute path to the source file.
            symbol_name: The name of the symbol.

        Returns:
            A unique identifier string.
        """
        # Create a deterministic ID based on file path and symbol name
        normalized_path = file_path.replace("\\", "/")
        return f"{normalized_path}:{symbol_name}"

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """Get the text content of a node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The node text as a string.
        """
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _get_byte_range(self, node: Node) -> Tuple[int, int]:
        """Get the byte range of a node.

        Args:
            node: The AST node.

        Returns:
            Tuple of (start_byte, end_byte).
        """
        return (node.start_byte, node.end_byte)

    def _get_line_range(self, node: Node) -> Tuple[int, int]:
        """Get the line range of a node.

        Args:
            node: The AST node.

        Returns:
            Tuple of (start_line, end_line), 1-indexed.
        """
        return (node.start_point.row + 1, node.end_point.row + 1)

    def _extract_node_name(self, node: Node, source_bytes: bytes) -> str:
        """Extract the name from a definition node.

        Args:
            node: The AST node.
            source_bytes: The source code as bytes.

        Returns:
            The name of the defined symbol.
        """
        # Look for identifier child
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source_bytes)

        # Language-specific name extraction
        if self.language == Language.PYTHON:
            return self._extract_python_name(node, source_bytes)
        elif self.language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
            return self._extract_js_ts_name(node, source_bytes)
        elif self.language == Language.GO:
            return self._extract_go_name(node, source_bytes)

        return "unknown"

    def _find_body_node(self, node: Node) -> Optional[Node]:
        """Find the body child node within a definition node.

        Args:
            node: The parent AST node.

        Returns:
            The body node if found, None otherwise.
        """
        body_types = {"block", "suite", "class_body", "interface_body", "enum_body", "struct_body"}

        for child in node.children:
            if child.type in body_types:
                return child
            # Check for block-like structures
            if "body" in child.type or child.type.endswith("_block"):
                return child

        return None

    # Python-specific extraction methods

    def _extract_python_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract Python function/class signature."""
        # For Python, we want everything up to the colon, excluding the body
        parts = []
        for child in node.children:
            if child.type == "block":
                break
            parts.append(self._get_node_text(child, source_bytes))
        return "".join(parts).strip()

    def _extract_python_docstring(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extract Python docstring from function/class."""
        body_node = self._find_body_node(node)
        if not body_node or not body_node.children:
            return None

        # First statement in body might be a docstring
        first_stmt = body_node.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                return self._get_node_text(expr, source_bytes).strip("\"'")
        return None

    def _extract_python_name(self, node: Node, source_bytes: bytes) -> str:
        """Extract name from Python node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source_bytes)
        return "unknown"

    # TypeScript/JavaScript-specific extraction methods

    def _extract_typescript_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract TypeScript/JavaScript function/class signature."""
        parts = []
        for child in node.children:
            if child.type in {"statement_block", "class_body", "interface_body"}:
                break
            parts.append(self._get_node_text(child, source_bytes))
        return "".join(parts).strip()

    def _extract_js_ts_docstring(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extract JSDoc comment from TypeScript/JavaScript node."""
        # Look for comment before the node
        # This is a simplified version - full implementation would need
        # access to the tree's root to find preceding comments
        return None

    def _extract_js_ts_name(self, node: Node, source_bytes: bytes) -> str:
        """Extract name from TypeScript/JavaScript node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source_bytes)
            # For methods: property_identifier
            if child.type == "property_identifier":
                return self._get_node_text(child, source_bytes)
        return "unknown"

    # Go-specific extraction methods

    def _extract_go_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract Go function/method signature."""
        parts = []
        for child in node.children:
            if child.type == "block":
                break
            parts.append(self._get_node_text(child, source_bytes))
        return "".join(parts).strip()

    def _extract_go_docstring(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extract Go comment from function/method."""
        # Go comments are not part of the AST, would need external handling
        return None

    def _extract_go_name(self, node: Node, source_bytes: bytes) -> str:
        """Extract name from Go node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source_bytes)
            # For method receivers
            if child.type == "field_identifier":
                return self._get_node_text(child, source_bytes)
        return "unknown"
