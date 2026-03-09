import tree_sitter_python
from tree_sitter import Parser

parser = Parser(tree_sitter_python.LANGUAGE)

code = b"""
def my_func():
    print("Hello world")
    target_c.get('auth', {})
"""

tree = parser.parse(code)
root_node = tree.root_node

for child in root_node.children:
    print(child.type, child.text.decode('utf-8'))
