---
trigger: "when reviewing code quality or discussing best practices"
context: "fork"
---

# Code Quality Best Practices

## Principles
- Functions should do one thing and do it well
- Prefer explicit over implicit
- Names should reveal intent
- Comments explain WHY, not WHAT
- Tests should be independent and deterministic

## Review Checklist
- [ ] No unused imports or variables
- [ ] Error handling for all async operations
- [ ] Input validation on all public APIs
- [ ] No hardcoded secrets or credentials
- [ ] Consistent naming conventions
- [ ] No console.log / print statements in production code