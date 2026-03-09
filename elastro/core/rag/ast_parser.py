"""
Abstract Syntax Tree (AST) parser utilizing tree-sitter for Graph RAG Code Flow Mapping.
Supports polyglot analysis of Python, Go, JavaScript, TypeScript, and Vue.
"""

import os
import tree_sitter
from typing import Dict, List, Set, Tuple

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
                "vue": Language(tsts.language_typescript()) 
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

    def parse_file(self, file_path: str, content: str) -> Dict[str, List[str]]:
        """
        Parses raw code to extract the deterministic call graph.
        Returns explicit function definitions and external call expressions.
        """
        ext = os.path.splitext(file_path)[1]
        lang = self._determine_language(ext)
        
        if lang not in self.parsers:
            return {"functions_defined": [], "functions_called": []}
            
        parser = self.parsers[lang]
        tree = parser.parse(content.encode('utf-8'))
        
        funcs_defined: Set[str] = set()
        funcs_called: Set[str] = set()
        
        # We manually traverse to avoid huge compiled regex TS Queries (keeps it extremely fast)
        self._traverse_tree(tree.root_node, lang, content.encode('utf-8'), funcs_defined, funcs_called)
        
        return {
            "functions_defined": sorted(list(funcs_defined)),
            "functions_called": sorted(list(funcs_called))
        }

    def _traverse_tree(self, node: tree_sitter.Node, lang: str, source: bytes, defined: Set[str], called: Set[str]) -> None:
        """Recursive AST Walk for unified Graph routing rules."""
        node_type = node.type
        
        # 1. Catch Function Definitions
        if lang == "python" and node_type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                defined.add(source[name_node.start_byte:name_node.end_byte].decode('utf-8'))
                
        elif lang == "go" and node_type in ["function_declaration", "method_declaration"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                defined.add(source[name_node.start_byte:name_node.end_byte].decode('utf-8'))
                
        elif lang in ["javascript", "typescript", "vue"]:
            if node_type in ["function_declaration", "method_definition"]:
                name_node = node.child_by_field_name("name")
                if name_node:
                    defined.add(source[name_node.start_byte:name_node.end_byte].decode('utf-8'))
            # Arrow functions often attached to variable_declarator
            if node_type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                val_node = node.child_by_field_name("value")
                if name_node and val_node and val_node.type == "arrow_function":
                    defined.add(source[name_node.start_byte:name_node.end_byte].decode('utf-8'))

        # 2. Catch Call Expressions (The "Graph RAG" Links)
        # Tree-sitter universally identifies function execution as 'call_expression'
        if node_type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                # We want to extract the full chained attribute map, e.g "db_session.query.filter.first"
                # rather than just "first" or the full messy syntax tree text.
                call_text = self._extract_call_chain(func_node, source)
                
                # Filter out standard library noise and wildly long chunks
                ignore_list = {
                    "print", "len", "range", "str", "int", "list", "dict", "set", "super",
                    "append", "fmt.Println", "console.log", "console.error", "require"
                }

                if call_text and call_text not in ignore_list and len(call_text) < 60 and '\n' not in call_text:
                    called.add(call_text)

        # 3. Recurse down AST
        for child in node.children:
            self._traverse_tree(child, lang, source, defined, called)

    def _extract_call_chain(self, node: tree_sitter.Node, source: bytes) -> str:
        """Recursively builds pure string representation of chained object method calls."""
        if node.type == "identifier":
            return source[node.start_byte:node.end_byte].decode('utf-8')
        elif node.type == "attribute":
            obj_node = node.child_by_field_name("object")
            attr_node = node.child_by_field_name("attribute")
            if obj_node and attr_node:
                obj_str = self._extract_call_chain(obj_node, source)
                attr_str = source[attr_node.start_byte:attr_node.end_byte].decode('utf-8')
                return f"{obj_str}.{attr_str}"
        elif node.type == "call":
            # Nested call expression logic (e.g. inside an attribute chain)
            func_node = node.child_by_field_name("function")
            if func_node:
                return self._extract_call_chain(func_node, source)
            
        # Fallback to pure text extraction
        return source[node.start_byte:node.end_byte].decode('utf-8').strip()
