"""
Abstract Syntax Tree (AST) parser utilizing tree-sitter for Graph RAG Code Flow Mapping.
Supports polyglot analysis of Python, Go, JavaScript, TypeScript, and Vue.
Implements Semantic Chunking and Signature Extraction.
"""

import os
import tree_sitter
from typing import Dict, List, Set, Any


class ASTParser:
    def __init__(self):
        self.parsers: Dict[str, tree_sitter.Parser] = {}
        self._initialize_parsers()

    def _initialize_parsers(self) -> None:
        """Loads natively compiled tree-sitter language capsules."""
        try:
            from tree_sitter import Language, Parser
            import tree_sitter_python as tsp
            import tree_sitter_go as tsg
            import tree_sitter_javascript as tsjs
            import tree_sitter_typescript as tsts

            # v0.25+ API natively imports .language() as PyCapsule pointers
            self.langs = {
                "python": Language(tsp.language()),
                "go": Language(tsg.language()),
                "javascript": Language(tsjs.language()),
                "typescript": Language(tsts.language_typescript()),
                # Vue uses specialized HTML embedding, but for script logic, TS/JS parser handles it well
                "vue": Language(tsts.language_typescript()),
            }

            for lang_name, lang_obj in self.langs.items():
                parser = Parser()
                parser.language = lang_obj
                self.parsers[lang_name] = parser

        except ImportError as e:
            # Degrade gracefully if tree-sitter is missing during testing/CI
            print(f"Graph RAG AST Parser initialization warning: {e}")
            pass

    def _determine_language(self, ext: str) -> str:
        ext = ext.lower()
        if ext == ".py":
            return "python"
        elif ext == ".go":
            return "go"
        elif ext in [".js", ".jsx"]:
            return "javascript"
        elif ext in [".ts", ".tsx"]:
            return "typescript"
        elif ext == ".vue":
            return "vue"
        return "unsupported"

    def parse_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """
        Parses raw code and extracts semantic chunks (functions/classes) with deterministic call graphs.
        """
        ext = os.path.splitext(file_path)[1]
        lang = self._determine_language(ext)

        if lang not in self.parsers:
            return [
                {
                    "chunk_type": "file",
                    "name": "module",
                    "content": content,
                    "functions_defined": [],
                    "functions_called": [],
                }
            ]

        parser = self.parsers[lang]
        source = content.encode("utf-8")
        tree = parser.parse(source)

        chunks: List[Dict[str, Any]] = []

        self._extract_chunks(tree.root_node, lang, source, chunks)

        # If no semantic chunks were found, fallback to parsing the whole file as a single module chunk
        if not chunks:
            called: Set[str] = set()
            self._traverse_for_calls(tree.root_node, lang, source, called)
            chunks.append(
                {
                    "chunk_type": "file",
                    "name": "module",
                    "content": content,
                    "functions_defined": [],
                    "functions_called": sorted(list(called)),
                }
            )

        return chunks

    def _extract_chunks(
        self,
        node: tree_sitter.Node,
        lang: str,
        source: bytes,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Recursive AST Walk for semantic chunking."""
        node_type = node.type

        is_chunk = False
        chunk_name = ""
        chunk_type = ""

        if lang == "python":
            if node_type in ["function_definition", "class_definition"]:
                is_chunk = True
                chunk_type = "function" if "function" in node_type else "class"
                name_node = node.child_by_field_name("name")
                if name_node:
                    chunk_name = source[
                        name_node.start_byte : name_node.end_byte
                    ].decode("utf-8")

        elif lang == "go":
            if node_type in [
                "function_declaration",
                "method_declaration",
                "type_declaration",
            ]:
                is_chunk = True
                chunk_type = (
                    "function"
                    if "function" in node_type or "method" in node_type
                    else "class"
                )
                name_node = node.child_by_field_name("name")
                if name_node:
                    chunk_name = source[
                        name_node.start_byte : name_node.end_byte
                    ].decode("utf-8")

        elif lang in ["javascript", "typescript", "vue"]:
            if node_type in [
                "function_declaration",
                "method_definition",
                "class_declaration",
            ]:
                is_chunk = True
                chunk_type = (
                    "function"
                    if "function" in node_type or "method" in node_type
                    else "class"
                )
                name_node = node.child_by_field_name("name")
                if name_node:
                    chunk_name = source[
                        name_node.start_byte : name_node.end_byte
                    ].decode("utf-8")
            elif node_type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                val_node = node.child_by_field_name("value")
                if name_node and val_node and val_node.type == "arrow_function":
                    is_chunk = True
                    chunk_type = "function"
                    chunk_name = source[
                        name_node.start_byte : name_node.end_byte
                    ].decode("utf-8")

        if is_chunk:
            called: Set[str] = set()
            # Traverse specifically inside this chunk's boundaries to extract calls
            self._traverse_for_calls(node, lang, source, called)

            # To ensure proper context window, extract the source of just this node
            chunk_content = source[node.start_byte : node.end_byte].decode("utf-8")

            chunks.append(
                {
                    "chunk_type": chunk_type,
                    "name": chunk_name or "anonymous",
                    "content": chunk_content,
                    "functions_defined": [chunk_name] if chunk_name else [],
                    "functions_called": sorted(list(called)),
                }
            )

        # Continue recursing to find nested functions/classes (e.g., methods inside a class)
        for child in node.children:
            self._extract_chunks(child, lang, source, chunks)

    def _traverse_for_calls(
        self, node: tree_sitter.Node, lang: str, source: bytes, called: Set[str]
    ) -> None:
        """Extracts call chains including their parameters/arguments for exact signature mapping."""
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                call_text = self._extract_call_chain(func_node, source)

                ignore_list = {
                    "print",
                    "len",
                    "range",
                    "str",
                    "int",
                    "list",
                    "dict",
                    "set",
                    "super",
                    "append",
                    "fmt.Println",
                    "console.log",
                    "console.error",
                    "require",
                    "getattr",
                    "setattr",
                    "hasattr",
                    "isinstance",
                    "type",
                }

                if call_text and call_text not in ignore_list:
                    # Signature Extraction: Pull the arguments as well
                    args_node = node.child_by_field_name("arguments")
                    if args_node:
                        args_text = source[
                            args_node.start_byte : args_node.end_byte
                        ].decode("utf-8")
                        # Sanitize whitespace/newlines
                        args_text = " ".join(args_text.split())
                        if len(args_text) < 60:
                            call_text = f"{call_text}{args_text}"

                    if len(call_text) < 120 and "\n" not in call_text:
                        called.add(call_text)

        for child in node.children:
            self._traverse_for_calls(child, lang, source, called)

    def _extract_call_chain(self, node: tree_sitter.Node, source: bytes) -> str:
        """Recursively builds pure string representation of chained object method calls."""
        if node.type == "identifier":
            return source[node.start_byte : node.end_byte].decode("utf-8")
        elif node.type == "attribute":
            obj_node = node.child_by_field_name("object")
            attr_node = node.child_by_field_name("attribute")
            if obj_node and attr_node:
                obj_str = self._extract_call_chain(obj_node, source)
                attr_str = source[attr_node.start_byte : attr_node.end_byte].decode(
                    "utf-8"
                )
                return f"{obj_str}.{attr_str}"
        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                return self._extract_call_chain(func_node, source)

        return source[node.start_byte : node.end_byte].decode("utf-8").strip()
