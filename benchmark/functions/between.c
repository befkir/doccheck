uint64_t between(uint64_t x) {
  uint64_t result;
  if (x >= 10) {
    if (x <= 100) {
      result = 1;
    } else {
      result = 0;
    }
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
  between(*x);
  return 0;
}
