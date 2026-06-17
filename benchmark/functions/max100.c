uint64_t max100(uint64_t x) {
  uint64_t result;
  if (x > 100)
    result = x;
  else
    result = 100;
  return result;
}
