import sys
import ast

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)
    adapters = ['AdminsAdapter', 'AlliancesAdapter', 'AllianceSettingsAdapter', 'AllianceMembersAdapter', 'AllianceMonitoringAdapter', 'ServerAllianceAdapter', 'AutoRedeemMembersAdapter', 'AutoRedeemChannelsAdapter', 'AutoRedeemSettingsAdapter', 'WelcomeChannelAdapter']
    
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            is_async_func = isinstance(node, ast.AsyncFunctionDef)
            
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id in adapters:
                        adapter = child.func.value.id
                        method = child.func.attr
                        
                        # Within async functions, calls MUST have _async suffix to avoid blocking
                        if is_async_func and not method.endswith('_async'):
                            # Some methods like get_all() might not have async equivalents, but we want to catch the main ones
                            issues.append(f"Line {child.lineno} in {node.name} (async): {adapter}.{method}() called synchronously")
                            
                        # If it has _async, it MUST be awaited
                        if is_async_func and method.endswith('_async'):
                            # Check if the Call is inside an Await node
                            parent = getattr(child, 'parent_node', None)
                            # AST doesn't have parent links by default, let's do a simpler check:
                            # We can just look at Await nodes and see if their values are these calls
                            pass

    # simpler parent linking
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent_node = node

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id in adapters:
                        adapter = child.func.value.id
                        method = child.func.attr
                        
                        if not method.endswith('_async'):
                            issues.append(f"Line {child.lineno} in {node.name} (async): {adapter}.{method}() called synchronously")
                        else:
                            # It IS async. Is it awaited?
                            parent = getattr(child, 'parent_node', None)
                            if not isinstance(parent, ast.Await):
                                # It could be inside an assignment, subscript, etc. We need to check ancestors up to the statement level
                                curr = child
                                is_awaited = False
                                while curr is not None and not isinstance(curr, ast.stmt):
                                    if isinstance(curr, ast.Await):
                                        is_awaited = True
                                        break
                                    curr = getattr(curr, 'parent_node', None)
                                
                                if not is_awaited:
                                    issues.append(f"Line {child.lineno} in {node.name} (async): {adapter}.{method}() is not awaited")

    if issues:
        print(f"Issues found in {filepath}:")
        for i in sorted(list(set(issues))):
            print(i)
        sys.exit(1)
    else:
        print(f"No blocking adapter calls found in {filepath}!")
        sys.exit(0)

if __name__ == '__main__':
    check_file(sys.argv[1])
