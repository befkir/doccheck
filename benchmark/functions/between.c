uint64_t between(uint64_t x) {
  uint64_t result;
  if (x >= 10)
    if (x <= 100)
      result = 1;
    else
      result = 0;
  else
    result = 0;
  return result;
}
