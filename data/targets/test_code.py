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

# 13. Nested Data Structures - Pass
# claim: the returned list contains only the 'id' values from each dictionary in the input list
def get_user_ids(users: List[Dict[str, Any]]) -> List[int]:
    return [user['id'] for user in users if 'id' in user]

# 14. Complex Logic with Multi-step validation - Fail
# claim: the function returns the final price after applying a 10% discount if the user is a member and the price is over 100, otherwise it returns the original price
def calculate_membership_price(price: float, is_member: bool) -> float:
    if is_member and price >= 100:
        return price * 0.9
    return price

# 15. Advanced List Operations - Pass
# claim: the returned list contains all elements from the input list that are even, sorted in ascending order
def get_sorted_evens(numbers: List[int]) -> List[int]:
    evens = [n for n in numbers if n % 2 == 0]
    evens.sort()
    return evens

# 16. Dictionary Transformation - Pass
# claim: the returned dictionary has keys and values swapped from the input dictionary
# precondition: len(set(d.values())) == len(d)
def invert_dictionary(d: Dict[str, int]) -> Dict[int, str]:
    return {v: k for k, v in d.items()}

# 17. Algorithmic Logic - Pass
# claim: the returned list is a merge of two sorted lists and is itself sorted
# precondition: all(l1[i] <= l1[i+1] for i in range(len(l1)-1)) and all(l2[i] <= l2[i+1] for i in range(len(l2)-1))
def merge_sorted_lists(l1: List[int], l2: List[int]) -> List[int]:
    result = []
    i = j = 0
    while i < len(l1) and j < len(l2):
        if l1[i] < l2[j]:
            result.append(l1[i])
            i += 1
        else:
            result.append(l2[j])
            j += 1
    result.extend(l1[i:])
    result.extend(l2[j:])
    return result