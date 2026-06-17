uint64_t clamp10(uint64_t x) {
  uint64_t result;
  if (x > 10)
    result = 10;
  else
    result = x;
  return result;
}
