uint64_t square(uint64_t x) {
  uint64_t result;
  result = x * x;
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  square(*x);
  return 0;
}
