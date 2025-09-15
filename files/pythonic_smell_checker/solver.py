# check_smells.py (v2 - context-aware magic numbers)
import ast
import sys

# --- Smell Thresholds ---
MAX_LINE_LENGTH = 99
MAX_PARAMS = 5
MAX_COMPLEXITY = 5
ALLOWED_MAGIC_NUMBERS = {0, 1, -1}

class SmellVisitor(ast.NodeVisitor):
    """
    An AST visitor that traverses the code to find smells, with a focus on
    the context of where numbers are used.
    """
    def __init__(self):
        self.smells = 0
        self.stats = {
            "long_params": 0,
            "high_complexity": 0,
        }
        # Use a set to store unique locations of magic numbers to avoid double counting
        self.magic_number_locations = set()

    def _check_node_for_magic_number(self, node):
        """Helper to check if a node is a problematic magic number."""
        if (isinstance(node, ast.Constant) and 
            isinstance(node.value, (int, float)) and 
            node.value not in ALLOWED_MAGIC_NUMBERS):
                # Add a tuple of (line, col, value) to the set
                location_tuple = (node.lineno, node.col_offset, node.value)
                if location_tuple not in self.magic_number_locations:
                    print(f"SMELL (Magic Number): Found '{node.value}' used in logic at line {node.lineno}.")
                    self.magic_number_locations.add(location_tuple)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Checks for long parameter lists and high complexity per function."""
        # 1. Check for long parameter list
        num_params = len(node.args.args)
        if num_params > MAX_PARAMS:
            print(f"SMELL (Long Params): Function '{node.name}' has {num_params} parameters.")
            self.smells += 1
            self.stats["long_params"] += 1

        # 2. Check for high cyclomatic complexity
        complexity = 1
        for sub_node in ast.walk(node):
            if isinstance(sub_node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler)):
                complexity += 1
        
        if complexity > MAX_COMPLEXITY:
            print(f"SMELL (High Complexity): Function '{node.name}' has complexity of {complexity}.")
            self.smells += 1
            self.stats["high_complexity"] += 1

        self.generic_visit(node)

    # --- Context-Aware Magic Number Checks ---

    def visit_Compare(self, node: ast.Compare):
        """Catches numbers in comparisons like `if x > 1000`."""
        for comparator in node.comparators:
            self._check_node_for_magic_number(comparator)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        """Catches numbers in binary operations like `x * 100`."""
        self._check_node_for_magic_number(node.left)
        self._check_node_for_magic_number(node.right)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        """Catches numbers in augmented assignments like `x += 0.1`."""
        self._check_node_for_magic_number(node.value)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Catches numbers passed as arguments to functions."""
        # We check this to find things like print("="*30) which is a BinOp,
        # but this visitor could be extended for direct literal args too.
        self.generic_visit(node)


def analyze_file(filepath):
    """
    Analyzes a Python file for several code smells and returns the total count.
    """
    total_smells = 0
    with open(filepath, 'r') as f:
        source_code = f.read()
        lines = source_code.splitlines()

    # Smell 1: Long Line Length
    long_lines_count = 0
    for i, line in enumerate(lines):
        if len(line) > MAX_LINE_LENGTH:
            print(f"SMELL (Long Line): Line {i+1} has {len(line)} characters.")
            long_lines_count += 1
    total_smells += long_lines_count
    
    try:
        tree = ast.parse(source_code)
        visitor = SmellVisitor()
        visitor.visit(tree)
        # Add the counts from the AST visitor
        total_smells += visitor.smells
        magic_number_count = len(visitor.magic_number_locations)
        total_smells += magic_number_count
        
        print("\n--- AST Analysis Summary ---")
        print(f"Functions with too many params: {visitor.stats['long_params']}")
        print(f"Functions with high complexity: {visitor.stats['high_complexity']}")
        print(f"Contextual magic numbers found: {magic_number_count}")
        print("----------------------------\n")

    except SyntaxError as e:
        print(f"Error parsing the Python file: {e}")
        return None

    return total_smells


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_smells.py <path_to_main.py>")
        sys.exit(1)
        
    target_file = sys.argv[1]
    
    print(f"--- Analyzing {target_file} for code smells ---\n")
    final_count = analyze_file(target_file)
    
    if final_count is not None:
        print(f"\n--- Final Result ---")
        print(f"SMELL_COUNT={final_count}")