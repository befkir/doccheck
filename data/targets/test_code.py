from typing import List, Dict, Any

# 1. Simple Math - Pass
# claim: the function always returns a value greater than the input x
def increment(x: int) -> int:
    return x + 1

# 2. Simple Math - Fail
# claim: the function always returns a value less than the input x
def decrement(x: int) -> int:
    return x + 1

# 3. Simple Math - Fail
# claim: the function always returns a value exactly twice the input x
def double(x: int) -> int:
    return x * 3

# 4. Logic with multiple inputs - Pass
# claim: the function always returns a non-negative integer
def absolute_difference(a: int, b: int) -> int:
    if a > b:
        return a - b
    else:
        return b - a

# 5. Strings - Pass
# claim: the returned string always starts with the prefix 'Hello '
def greet_user(name: str) -> str:
    return f"Hello {name}"

# 6. Strings - Fail
# claim: the returned string has the same length as the input string
def append_exclamation(text: str) -> str:
    return text + "!"

# 7. Lists - Pass with precondition
# claim: the returned value is always greater than or equal to every element in the input list
# precondition: len(numbers) > 0
def find_maximum(numbers: List[int]) -> int:
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val

# 8. Lists - Fail with precondition
# claim: the resulting list always contains more elements than the input list
# precondition: len(numbers) > 0
def filter_positive_numbers(numbers: List[int]) -> List[int]:
    return [n for n in numbers if n > 0]

# 9. Dictionaries - Pass
# claim: the returned dictionary always contains the key 'status' mapped to 'success'
def process_data(data: Dict[str, str]) -> Dict[str, str]:
    result = data.copy()
    result['status'] = 'success'
    return result

# 10. Math Preconditions - Pass
# claim: the returned value is strictly positive
# precondition: x > 0 and y > 0
def multiply_positives(x: int, y: int) -> int:
    return x * y

# 11. Division / Floats - Fail
# claim: dividing a number by itself always returns 1.0
# precondition: x != 0
def divide_by_self(x: float) -> float:
    # Fails for infinity or NaN, let's see if the system catches it, or simply let it be a basic math test
    return x / x

# 12. Complex list operations - Pass
# claim: the length of the returned list is exactly double the length of the input list
def duplicate_elements(items: List[int]) -> List[int]:
    result = []
    for item in items:
        result.append(item)
        result.append(item)
    return result