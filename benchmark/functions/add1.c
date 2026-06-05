uint64_t add1(uint64_t x) {
  uint64_t result;
  result = x + 1;
  return result;
}
uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  add1(*x);
  return 0;
}
