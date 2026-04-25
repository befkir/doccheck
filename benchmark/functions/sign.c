uint64_t sign(uint64_t x) {
  uint64_t result;
  if (x == 0) {
    result = 0;
  } else {
    result = 1;
  }
  return result;
}
uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  sign(*x);
  return 0;
}
