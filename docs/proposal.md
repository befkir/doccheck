# DocCheck proposal

DocCheck verifies natural-language claims about C* functions by translating each claim into a formal violation condition, injecting a generated `main()` harness, compiling with Selfie/starc, symbolically executing with rotor, and solving the generated SMT-LIB2 file with Z3.

Conceptually, a claim becomes an assertion. Practically, because C* has no `assert()`, DocCheck checks the negation of the assertion:

```text
assert(P) fails  ⇔  violation_expr = not P is reachable
```

The generated `main()` returns `1` exactly when `violation_expr` holds. Rotor/Z3 then decide whether such an execution exists.
