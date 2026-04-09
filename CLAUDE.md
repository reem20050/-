# CLAUDE.md - AI Assistant Guide

> Instructions for AI assistants working with the `reem20050/-` repository.

## Project Overview

**Repository:** reem20050/-
**Status:** Empty / newly initialized
**Last Updated:** 2026-04-09

This repository is freshly created and contains no source code, configuration files, or documentation beyond this file. It is a blank slate awaiting its first project setup.

## Repository Structure

```
/
├── CLAUDE.md          # This file - AI assistant guide
└── .git/              # Git repository metadata
```

No source code, tests, build configuration, or other files exist yet.

## Technology Stack

Not yet determined. No `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, or any other dependency/build file is present.

## Development Workflow

### Getting Started

```bash
# Clone the repository
git clone https://github.com/reem20050/-.git
cd -
```

### Branching Convention

The repository uses feature branches with the pattern `claude/<description>`. There is no `main` or `master` branch — the initial commit lives directly on feature branches.

Existing branches:
- `claude/add-claude-documentation-XWjVG`
- `claude/claude-md-ml6sii2bjfqykh6n-3kRgl`

Both branches point to the same single commit.

## Code Conventions

No conventions are established yet since no code exists. When the project is set up, update this section with:

- Language-specific style guide
- Naming conventions for files, variables, and functions
- Formatting / linting tool configuration
- Import ordering rules

### Git Workflow

- Use descriptive commit messages
- Create feature branches for new work
- Keep commits atomic and focused
- Do not commit secrets (API keys, passwords, `.env` files)

## Testing

No test framework is configured. When tests are added, document:

- How to run the full test suite
- How to run a single test
- Test file naming and placement conventions

## Important Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI assistant guide (this file) |

No other files exist in the repository.

## AI Assistant Instructions

### Current State Awareness

This repository is empty. Any task will involve creating files from scratch rather than modifying existing code. There are no established patterns to follow yet.

### When Setting Up the Project

1. Ask or confirm what language/framework the project will use
2. Initialize the appropriate project structure (e.g., `npm init`, `cargo init`, etc.)
3. Set up linting and formatting from the start
4. Add a `.gitignore` appropriate for the chosen stack
5. Create a `README.md` with basic project info
6. Update this `CLAUDE.md` to reflect the chosen stack and conventions

### General Guidelines

1. **Before making changes:**
   - Read relevant source files to understand context
   - Check existing patterns and conventions
   - Review related tests if they exist

2. **When implementing features:**
   - Follow established patterns in the codebase
   - Write tests for new functionality
   - Update documentation as needed

3. **When fixing bugs:**
   - Understand the root cause before fixing
   - Add regression tests when appropriate
   - Keep changes focused on the fix

### Things to Avoid

- Don't introduce new patterns without discussion
- Don't modify code style in unchanged files
- Don't commit sensitive data (API keys, passwords, tokens)
- Don't skip tests or linting checks
- Don't add placeholder/boilerplate content that doesn't reflect reality

## Contributing

1. Create a feature branch from the base branch
2. Make changes following the conventions above
3. Ensure all tests pass (when tests exist)
4. Submit a pull request with a clear description
