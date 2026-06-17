uint64_t clamp(uint64_t x) {
  uint64_t result;
  if (x > 100)
    result = 100;
  else
    result = x;
  return result;
}
