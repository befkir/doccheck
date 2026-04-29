import libcst as cst

def inject_assertion(source_code: str, assertion_code: str, target_func_sig: str, target_func_name: str) -> str:
    """
    Transforms the code into a format CrossHair cannot ignore.
    It wraps the target function and checks the logic as a post-condition.
    """
    # 1. Extract the logic from the assertion (e.g., '__return__ < x')
    # We remove 'assert ' prefix if present
    condition = assertion_code.replace("assert ", "").strip()

    # 2. Reconstruct the code to use a 'post-condition' wrapper
    # This is more robust than manual AST injection for CrossHair
    checker_name = f"crosshair_checker_{target_func_name}"
    checker_sig = target_func_sig.replace(f"def {target_func_name}(", f"def {checker_name}(")

    # Extract argument names to pass to the original function
    # e.g. from `x: int, y: int=0` -> `x, y`
    # simple extraction by taking what's between '(' and ')' and splitting by ','
    # then taking the first part before ':' or '='
    args_str = target_func_sig.split('(', 1)[1].split(')')[0]
    arg_names = []
    if args_str.strip():
        for arg in args_str.split(','):
            arg_name = arg.split(':')[0].split('=')[0].strip()
            if arg_name:
                arg_names.append(arg_name)
    call_args = ", ".join(arg_names)

    # We create a 'checker' function that CrossHair will analyze
    # This format forces CrossHair to bind the return value of the logic to the condition
    instrumented_template = f"""
{source_code}

{checker_sig}
    '''
    pre: True
    post: {condition}
    '''
    # We call your actual function logic here
    _ = {target_func_name}({call_args})
    return _
"""
    return instrumented_template