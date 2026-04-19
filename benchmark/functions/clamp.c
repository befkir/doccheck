uint64_t clamp(uint64_t x) {
  uint64_t result;
  if (x > 100) {
    result = 100;
  } else {
    result = x;
  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  clamp(*x);
  return 0;
}
