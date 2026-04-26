uint64_t const42(uint64_t x) {
  uint64_t result;
  result = 42;
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  const42(*x);
  return 0;
}
