---
trigger: "when creating database migrations or modifying schema"
context: "fork"
---

# Database Migration Skill

## Rules
1. Every migration MUST have a corresponding rollback
2. Use timestamped filenames: YYYYMMDD_HHMMSS_description.sql
3. Never use DROP TABLE in production -- use soft deletes
4. Always add NOT NULL constraints with DEFAULT values
5. Create indexes for any column used in WHERE or JOIN

## Migration Template
See operations/migration-template.sql for the standard format.

## Testing Requirements
- Run migration forward AND backward before committing
- Verify with: `psql -f migration.sql && psql -f rollback.sql`
- Check for data loss with: SELECT COUNT(*) before and after