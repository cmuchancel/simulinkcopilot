# Deterministic Grammar Notes

Supported core constructs:

- equations separated by newlines
- `+`, `-`, `*`, `/`, `^`
- implicit multiplication
- grouping with `()` and `{}`
- `\dot{x}`, `\ddot{x}`
- normalized higher-order derivatives via `\deriv{n}{x}`
- `\frac{...}{...}`
- indexed symbols such as `x_1`, `k_12`
- unary minus in grouped and nested expressions

Pre-normalization support:

- `\left` and `\right`
- `\frac{dx}{dt}`
- `\frac{d^3 x}{dt^3}`

Unsupported by design:

- fuzzy parsing
- ambiguous mixed derivative notation
- derivatives with respect to variables other than `t`
- arbitrary LaTeX environments
- unrecognized LaTeX commands
- plain multi-letter identifiers that would conflict with implicit multiplication
