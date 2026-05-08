import sys
import os

# Ensure we can import from the pipeline directory
sys.path.insert(0, os.getcwd())

from pipeline.pipeline import check

source = """
uint64_t halve(uint64_t x) {
  uint64_t result;
  result = x / 2;
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(8);
  *x = 0;
  read(0, x, 8);
  halve(*x);
  return 0;
}
"""

# The claim "output is always smaller than input" means result < x.
# Violation is result >= x.
res = check(source, "output is always smaller than input", "halve", kmax=50)
print("\nFINAL RESULT DICT:")
print(res)
