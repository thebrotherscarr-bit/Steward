# Sample Project Review

The **sample-project** is a minimal example that demonstrates basic inventory handling for the Steward project. It includes:

- A simple `Item` dataclass.
- Functions to compute order totals with optional percentage discounts and to list low‑stock items.
- Unit tests that validate both functionalities, including a bug fix for percentage discounts.

**Strengths**:
- Clear, concise implementation.
- Good test coverage for edge cases.
- Easy to extend for more complex inventory logic.

**Areas for improvement**:
- Add type hints for lists in function signatures for better static analysis.
- Consider handling negative or non‑numeric discounts gracefully.
- Document the expected units for `unit_price` and `quantity`.

Overall, a solid foundation for experimenting with inventory logic within the Steward project.
