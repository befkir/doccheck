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

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  factorial(*x);
  return 0;
}
