# Programming Foundations - Loops and Accumulators Quick Reference
*PrepWise Synthetic Demo Material - Exam Revision Aid*

## 1. Loop Invariants and Guarantees
An invariant is a condition that is true before and after every iteration of a loop.
- **While-loop guard**: Evaluated before each iteration. If false on first entry, the body executes zero times.
- **Off-by-one avoidance**:
  - `range(n)` produces `[0, 1, ..., n-1]` (exactly `n` elements).
  - `range(a, b)` produces `b - a` elements.
  - Slicing `items[start:stop]` includes index `start` up to but excluding `stop`.

## 2. Accumulator Pattern Invariant Rules
- **Sum**: Initialized to `0`. `total += item`
- **Product**: Initialized to `1`. `product *= item`
- **Counter / Frequency**: Initialized to `0`. `count += 1`
- **Collection Collector**: Initialized to `[]`. `collected.append(item)`

## 3. Common Confusion: `while` vs `for`
- Use `for` when iterating over known collections or bounded sequences (`range`).
- Use `while` when termination depends on a runtime condition or sentinel value.
