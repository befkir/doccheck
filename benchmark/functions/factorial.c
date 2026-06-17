uint64_t factorial(uint64_t x) {
  uint64_t result;
  uint64_t i;
  result = 1;
  i = 1;
  while (i <= x) {
    result = result * i;
    i = i + 1;
  }
  return result;
}
