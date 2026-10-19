# Migration and deletion checklist

The legacy repositories must NOT be deleted until the following are independently verified:

1. Rotate the leaked Dosiyo Discord bot token.
2. Audit legacy Git history for secrets before importing any history into a public repository.
3. Export an offline copy of both legacy repositories, including Git history.
4. Make a separate backup of Takoyaki's SQLite database (not in public Git).
5. Stop the old bot and migrate its SQLite data using a tested backup/restore procedure.
6. Verify slash commands, permissions, voice playback, stock, attendance and logging in a test Discord server.
7. Ensure CI passes, review and merge the draft PR, and enable main branch protection.
8. Only then consider deleting legacy repositories through GitHub settings.

**Current status:** Code migration is untested; database migration and history preservation have not been completed.
