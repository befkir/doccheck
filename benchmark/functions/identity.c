uint64_t identity(uint64_t x) {
  uint64_t result;
  result = x;
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  identity(*x);
  return 0;
}
