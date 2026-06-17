uint64_t clamp50(uint64_t x) {
  uint64_t result;
  if (x > 50)
    result = 50;
  else
    result = x;
  return result;
}
