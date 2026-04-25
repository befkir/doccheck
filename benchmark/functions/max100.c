uint64_t max100(uint64_t x) {
  uint64_t result;
  if (x > 100) {
    result = x;
  } else {
    result = 100;
  }
  return result;
}
uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  max100(*x);
  return 0;
}
