uint64_t clamp50(uint64_t x) {
  uint64_t result;
  if (x > 50) {
    result = 50;
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
  clamp50(*x);
  return 0;
}
