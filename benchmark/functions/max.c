uint64_t max(uint64_t x, uint64_t b) {
  uint64_t result;
  if (x > b) {
    result = x;
  } else {
    result = b;
  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  max(*x, 42);
  return 0;
}