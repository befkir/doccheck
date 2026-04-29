# # claim: the function always returns a value greater than the input x
# def increment(x: int) -> int:
#     return x + 1

# # claim: the function always returns a value less than the input x
# def decrement(x: int) -> int:
#     return x + 1

# # claim: the function always returns a value exactly twice the input x
# def double(x: int) -> int:
#     return x * 3

# # claim: the function always returns a non-negative integer
# def absolute_difference(a: int, b: int) -> int:
#     if a > b:
#         return a - b
#     else:
#         return b - a

# # claim: if the age is less than 18, the function always returns a price lower than the base_price
# def calculate_discount(base_price: float, age: int) -> float:
#     if age < 18:
#         return base_price * 0.9
#     elif age > 65:
#         return base_price * 0.8
#     return base_price

from typing import List

# claim: the returned value is always greater than or equal to every element in the input list
def find_maximum(numbers: List[int]) -> int:
    if not numbers:
        return 0
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val

# claim: the resulting list always contains more elements than the input list
def filter_positive_numbers(numbers: List[int]) -> List[int]:
    return [n for n in numbers if n > 0]