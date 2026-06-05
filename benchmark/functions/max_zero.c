uint64_t max_zero(uint64_t x) {
  uint64_t result;
  if (x > 0) {
    result = x;
  } else {
    result = 0;
  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  max_zero(*x);
  return 0;
}
