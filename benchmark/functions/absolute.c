uint64_t absolute(uint64_t x) {
  uint64_t result;
  if (x < 0)
    result = -x;
  else
    result = x;
  return result;
}
