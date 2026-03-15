"""Code skeletonization for token reduction.

This module provides functionality to strip implementation bodies from code
while preserving signatures, docstrings, and structural information.
"""

import re
from typing import List

from nomi.core.context.context_bundle import CodeUnitSkeleton
from nomi.discovery.language_detector import Language
from nomi.storage.models import CodeUnit


class Skeletonizer:
    """Creates skeletonized versions of code units for token reduction.

    Skeletonization removes implementation bodies while preserving:
    - Function/class signatures
    - Docstrings (optional)
    - Import statements
    - Type annotations
    - Decorators

    This typically reduces token count by 75-90% while maintaining
    enough context for AI agents to understand code structure.
    """

    def __init__(self, preserve_docstrings: bool = True):
        """Initialize the skeletonizer.

        Args:
            preserve_docstrings: Whether to preserve docstrings in skeletons
        """
        self.preserve_docstrings = preserve_docstrings

    def skeletonize_unit(self, unit: CodeUnit, keep_docstring: bool = True) -> CodeUnitSkeleton:
        """Create a skeleton from a single CodeUnit.

        Args:
            unit: The code unit to skeletonize
            keep_docstring: Whether to include docstring in skeleton

        Returns:
            CodeUnitSkeleton with body removed
        """
        docstring = unit.docstring if (keep_docstring and self.preserve_docstrings) else None

        return CodeUnitSkeleton(
            id=unit.id,
            unit_kind=unit.unit_kind.value,
            signature=unit.signature,
            file_path=unit.file_path,
            line_range=unit.line_range,
            docstring=docstring,
        )

    def skeletonize_units(self, units: List[CodeUnit]) -> List[CodeUnitSkeleton]:
        """Batch skeletonize multiple code units.

        Args:
            units: List of code units to skeletonize

        Returns:
            List of CodeUnitSkeleton objects
        """
        return [self.skeletonize_unit(unit) for unit in units]

    def skeletonize_file(self, file_path: str, units: List[CodeUnit]) -> str:
        """Generate skeletonized file content from multiple units.

        Args:
            file_path: Path to the source file
            units: Code units from the file to include in skeleton

        Returns:
            Skeletonized file content as string
        """
        if not units:
            return ""

        lines = []
        sorted_units = sorted(units, key=lambda u: u.line_range[0])

        for unit in sorted_units:
            skeleton = self.skeletonize_unit(unit)
            lines.append(skeleton.signature)
            if skeleton.docstring:
                lines.append(f'    """{skeleton.docstring}"""')
            lines.append("    ...")
            lines.append("")

        return "\n".join(lines)

    def preserve_signatures_only(self, source_code: str, language: Language) -> str:
        """Remove all implementation bodies, keep only signatures.

        Args:
            source_code: Original source code
            language: Programming language of the code

        Returns:
            Skeletonized code with bodies replaced by "..."
        """
        if language == Language.PYTHON:
            return self._skeletonize_python(source_code)
        elif language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
            return self._skeletonize_typescript(source_code)
        elif language == Language.GO:
            return self._skeletonize_go(source_code)
        else:
            return self._skeletonize_generic(source_code)

    def _skeletonize_python(self, source: str) -> str:
        """Skeletonize Python code.

        Keeps:
        - Import statements
        - Class/function definitions (signatures)
        - Decorators
        - Docstrings (if preserve_docstrings is True)
        - Type annotations

        Replaces:
        - Function bodies with "..."
        - Class method bodies with "..."

        Args:
            source: Python source code

        Returns:
            Skeletonized Python code
        """
        lines = source.split("\n")
        result_lines = []
        in_function_or_class = False
        base_indent = 0
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            if not stripped:
                if not in_function_or_class:
                    result_lines.append(line)
                i += 1
                continue

            current_indent = len(line) - len(stripped)

            if stripped.startswith(("def ", "class ", "async def ")):
                in_function_or_class = True
                base_indent = current_indent
                result_lines.append(line)
                i += 1

                if self.preserve_docstrings and i < len(lines):
                    next_line = lines[i].lstrip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        result_lines.append(lines[i])
                        i += 1
                        while i < len(lines) and not lines[i].strip().endswith(next_line[0:3]):
                            result_lines.append(lines[i])
                            i += 1
                        if i < len(lines):
                            result_lines.append(lines[i])
                            i += 1
                continue

            if stripped.startswith("@"):
                if not in_function_or_class or current_indent == base_indent:
                    result_lines.append(line)
                i += 1
                continue

            if stripped.startswith(("import ", "from ")):
                result_lines.append(line)
                i += 1
                continue

            if in_function_or_class:
                if current_indent <= base_indent and stripped:
                    in_function_or_class = False
                    result_lines.append(line)
                elif current_indent > base_indent:
                    pass
            else:
                result_lines.append(line)

            i += 1

        return "\n".join(result_lines)

    def _skeletonize_typescript(self, source: str) -> str:
        """Skeletonize TypeScript/JavaScript code.

        Keeps:
        - Import/export statements
        - Interface/type definitions
        - Function signatures
        - Class definitions with method signatures
        - Decorators

        Replaces:
        - Function bodies with "{ ... }"
        - Method implementations with "{ ... }"

        Args:
            source: TypeScript/JavaScript source code

        Returns:
            Skeletonized TypeScript code
        """
        lines = source.split("\n")
        result_lines = []
        brace_count = 0
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            if not stripped:
                if brace_count == 0:
                    result_lines.append(line)
                i += 1
                continue

            if stripped.startswith(("import ", "export ", "from ")):
                result_lines.append(line)
                i += 1
                continue

            if stripped.startswith("@"):
                result_lines.append(line)
                i += 1
                continue

            if re.match(r"^(interface|type|enum|declare)\s+", stripped):
                result_lines.append(line)
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    result_lines.append(next_line)
                    if "}" in next_line and next_line.count("}") > next_line.count("{"):
                        break
                    i += 1
                i += 1
                continue

            func_match = re.match(
                r"^((?:async\s+)?(?:function\s+)?[\w$]*\s*\([^)]*\)\s*(?::\s*\w+)?\s*)",
                stripped,
            )
            method_match = re.match(
                r"^((?:async\s+)?(?:private\s+|public\s+|protected\s+|static\s+)?[\w$]+\s*\([^)]*\)\s*(?::\s*\w+)?\s*)",
                stripped,
            )

            if func_match or method_match:
                result_lines.append(line)

                if "{" in stripped:
                    brace_count = stripped.count("{") - stripped.count("}")
                i += 1

                if self.preserve_docstrings and i < len(lines):
                    next_stripped = lines[i].lstrip()
                    if next_stripped.startswith("/**") or next_stripped.startswith("/*"):
                        while i < len(lines):
                            result_lines.append(lines[i])
                            if "*/" in lines[i]:
                                i += 1
                                break
                            i += 1

                if brace_count > 0 or (i < len(lines) and "{" in lines[i]):
                    result_lines.append("    ...")
                    while i < len(lines) and brace_count > 0:
                        brace_count += lines[i].count("{") - lines[i].count("}")
                        i += 1
                else:
                    if i < len(lines) and lines[i].strip() == "{":
                        result_lines.append(lines[i])
                        i += 1
                        result_lines.append("    ...")
                        brace_count = 1
                        while i < len(lines) and brace_count > 0:
                            brace_count += lines[i].count("{") - lines[i].count("}")
                            if brace_count == 0:
                                result_lines.append(lines[i])
                            i += 1

                continue

            if brace_count == 0:
                result_lines.append(line)

            i += 1

        return "\n".join(result_lines)

    def _skeletonize_go(self, source: str) -> str:
        """Skeletonize Go code.

        Keeps:
        - Import statements
        - Package declarations
        - Type definitions (structs, interfaces)
        - Function signatures
        - Method signatures

        Replaces:
        - Function bodies with "{ ... }"
        - Method bodies with "{ ... }"

        Args:
            source: Go source code

        Returns:
            Skeletonized Go code
        """
        lines = source.split("\n")
        result_lines = []
        brace_count = 0
        in_func = False
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            if not stripped:
                if brace_count == 0:
                    result_lines.append(line)
                i += 1
                continue

            if stripped.startswith(("package ", "import ")):
                result_lines.append(line)
                i += 1
                continue

            if stripped.startswith("import ("):
                result_lines.append(line)
                i += 1
                while i < len(lines) and not lines[i].strip() == ")":
                    result_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    result_lines.append(lines[i])
                    i += 1
                continue

            type_match = re.match(r"^(type\s+\w+\s+(?:struct|interface)\s*)", stripped)
            if type_match:
                result_lines.append(line)
                i += 1
                while i < len(lines):
                    result_lines.append(lines[i])
                    if lines[i].strip() == "}":
                        break
                    i += 1
                i += 1
                continue

            func_match = re.match(
                r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\([^)]*\)(?:\s*\([^)]*\))?\s*(?:\w+)?",
                stripped,
            )

            if func_match:
                in_func = True
                result_lines.append(line)

                if "{" in stripped:
                    brace_count = stripped.count("{") - stripped.count("}")
                i += 1

                if self.preserve_docstrings and i < len(lines):
                    if stripped.startswith("//"):
                        while i < len(lines) and lines[i].strip().startswith("//"):
                            result_lines.append(lines[i])
                            i += 1

                if brace_count == 0:
                    while i < len(lines) and "{" not in lines[i]:
                        result_lines.append(lines[i])
                        i += 1
                    if i < len(lines):
                        brace_count += lines[i].count("{") - lines[i].count("}")
                        result_lines.append(lines[i])
                        i += 1

                result_lines.append("    ...")

                while i < len(lines) and brace_count > 0:
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    if brace_count == 0:
                        result_lines.append(lines[i])
                    i += 1

                in_func = False
                continue

            if brace_count == 0 and not in_func:
                result_lines.append(line)

            i += 1

        return "\n".join(result_lines)

    def _skeletonize_generic(self, source: str) -> str:
        """Generic skeletonization for unsupported languages.

        Uses simple heuristics to remove blocks between braces.

        Args:
            source: Source code in any language

        Returns:
            Skeletonized code with bodies replaced
        """
        lines = source.split("\n")
        result_lines = []
        brace_count = 0

        for line in lines:
            stripped = line.lstrip()

            if not stripped:
                if brace_count == 0:
                    result_lines.append(line)
                continue

            if brace_count == 0:
                if stripped.endswith("{") or "{" in stripped:
                    result_lines.append(line)
                    brace_count += stripped.count("{") - stripped.count("}")
                    if brace_count > 0:
                        result_lines.append("    ...")
                else:
                    result_lines.append(line)
            else:
                brace_count += stripped.count("{") - stripped.count("}")
                if brace_count == 0:
                    result_lines.append(line)

        return "\n".join(result_lines)

    def calculate_skeleton_tokens(self, unit: CodeUnit, chars_per_token: float = 4.0) -> int:
        """Estimate token count for a skeletonized unit.

        Args:
            unit: The code unit to estimate
            chars_per_token: Characters per token ratio

        Returns:
            Estimated token count
        """
        skeleton = self.skeletonize_unit(unit)
        content = skeleton.signature
        if skeleton.docstring:
            content += f'"""{skeleton.docstring}"""'
        return int(len(content) / chars_per_token)
