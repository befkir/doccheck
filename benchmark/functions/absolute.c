uint64_t absolute(uint64_t x) {
  if (x < 0)
    x = 0 - x;

  return x;
}
