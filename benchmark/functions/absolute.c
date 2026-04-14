uint64_t absolute(uint64_t x) {
  uint64_t result;
  if (x < 0) {
    result = -x;
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
  absolute(*x);
  return 0;
}
