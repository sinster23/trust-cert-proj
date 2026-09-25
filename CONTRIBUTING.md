# Contributing to Credence

## General Rule

Each team member is responsible for their assigned module.

Do not modify another member's module unless the change has been discussed
with the integration lead.

## Branches

Create a separate branch for your work.

Example:

feature/authentication
feature/authorization
feature/cryptography
feature/database
feature/integrity

Do not directly push feature work to the main branch.

## Commits

Use clear commit messages.

Examples:

feat: add user login
feat: add role authorization
feat: add digital signature service
fix: validate certificate input
test: add authentication tests

## Pull Requests

Before creating a pull request:

1. Test your implementation.
2. Make sure existing tests still pass.
3. Make sure secrets are not committed.
4. Update documentation if required.
5. Clearly describe what was implemented.

The integration lead reviews and tests the module before merging it.

## Module Boundaries

Do not implement functionality belonging to another module.

Follow the module-specific README provided for your assigned task.