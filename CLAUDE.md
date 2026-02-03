# CLAUDE.md - AI Assistant Guide

> This file provides guidance for AI assistants working with this repository.

## Project Overview

**Repository:** reem20050/-
**Status:** Newly initialized repository
**Last Updated:** 2026-02-03

<!-- TODO: Update this section when the project is set up -->
This repository is currently being set up. Update this section with:
- Project name and description
- Primary purpose and goals
- Target users/audience

## Repository Structure

```
/
├── CLAUDE.md          # This file - AI assistant guide
└── .git/              # Git repository metadata
```

<!-- TODO: Update the structure as files are added -->
<!-- Example structure for a typical project:
├── src/               # Source code
├── tests/             # Test files
├── docs/              # Documentation
├── config/            # Configuration files
├── scripts/           # Build/deployment scripts
├── package.json       # Dependencies (Node.js)
└── README.md          # Project documentation
-->

## Technology Stack

<!-- TODO: Update when technologies are chosen -->
- **Language:** TBD
- **Framework:** TBD
- **Build Tool:** TBD
- **Testing:** TBD

## Development Workflow

### Getting Started

```bash
# Clone the repository
git clone <repository-url>

# Navigate to project directory
cd -

# Install dependencies (update based on project type)
# npm install        # Node.js
# pip install -r requirements.txt  # Python
# bundle install     # Ruby
```

### Common Commands

<!-- TODO: Add actual commands when the project is set up -->
| Command | Description |
|---------|-------------|
| `npm start` | Start development server |
| `npm test` | Run tests |
| `npm run build` | Build for production |
| `npm run lint` | Run linter |

## Code Conventions

### General Guidelines

1. **Code Style**
   - Follow the project's established coding style
   - Use meaningful variable and function names
   - Keep functions small and focused

2. **Comments**
   - Write self-documenting code when possible
   - Add comments for complex logic
   - Keep comments up-to-date with code changes

3. **Git Workflow**
   - Use descriptive commit messages
   - Create feature branches for new work
   - Keep commits atomic and focused

### File Naming

<!-- TODO: Define naming conventions -->
- Use lowercase with hyphens for file names (e.g., `my-component.js`)
- Use PascalCase for component files (e.g., `MyComponent.tsx`)
- Use camelCase for utility files (e.g., `helpers.js`)

## Testing

### Running Tests

```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- path/to/test
```

### Test Conventions

- Place test files next to source files or in a `tests/` directory
- Name test files with `.test.` or `.spec.` suffix
- Write descriptive test names that explain the expected behavior

## Important Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI assistant guide (this file) |
| `README.md` | Project documentation |
| `package.json` | Dependencies and scripts |
| `.env.example` | Environment variable template |

## AI Assistant Instructions

### When Working on This Codebase

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
- Don't commit sensitive data (API keys, passwords)
- Don't skip tests or linting checks

### Helpful Context

<!-- TODO: Add project-specific context -->
- Key architectural decisions
- Known issues or limitations
- Areas of the codebase to be careful with
- Performance considerations

## Contributing

1. Create a feature branch from the main branch
2. Make your changes following the conventions above
3. Ensure all tests pass
4. Submit a pull request with a clear description

## Resources

<!-- TODO: Add relevant links -->
- [Project Documentation](./docs/)
- [Issue Tracker](#)
- [Team Wiki](#)

---

*This CLAUDE.md file was created as a template. Update it as the project develops to provide accurate guidance for AI assistants working with this codebase.*
