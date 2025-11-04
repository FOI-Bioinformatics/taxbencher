# Development Documentation

This directory contains comprehensive technical documentation for taxbencher developers.

## Quick Navigation

### Core Documentation
- **[Architecture](architecture.md)** - Pipeline structure, data flow, and design patterns
- **[Modules](modules.md)** - Detailed module specifications and implementation details
- **[Workflow Patterns](workflow-patterns.md)** - Channel operations and Nextflow patterns
- **[Development Guide](development-guide.md)** - How to add modules, modify workflows, and configure
- **[Testing](testing.md)** - Test framework, nf-test usage, and coverage
- **[Code Quality](code-quality.md)** - Best practices, innovative patterns, container strategy

### Reports
- [Code Quality Report](../reports/code-quality.md) - Latest quality assessment
- [Test Coverage Report](../reports/test-coverage.md) - Detailed test analysis
- [Validation Report](../reports/validation.md) - Validation infrastructure overview
- [Test Improvements Summary](../reports/test-improvements.md) - Historical improvements

### User Documentation
- [Usage Guide](../usage.md) - How to run the pipeline
- [Input Formats](../raw-inputs.md) - Supported input formats
- [Output Documentation](../output.md) - Understanding pipeline outputs
- [Troubleshooting](../troubleshooting.md) - Common issues and solutions

## Getting Started as a Developer

1. **Understand the architecture** - Read [architecture.md](architecture.md) for pipeline overview
2. **Review modules** - See [modules.md](modules.md) for module specifications
3. **Learn the patterns** - Study [workflow-patterns.md](workflow-patterns.md) for channel operations
4. **Set up development** - Follow [development-guide.md](development-guide.md)
5. **Write tests** - See [testing.md](testing.md) for testing requirements

## Contributing

Before contributing:
1. Read the [Development Guide](development-guide.md)
2. Check [Code Quality](code-quality.md) for standards
3. Review [Testing](testing.md) for test requirements
4. Lint with `nf-core pipelines lint`
5. Run tests with `nf-test test`

## Quick References

**Common Tasks:**
- Adding a module: See [development-guide.md#adding-modules](development-guide.md)
- Modifying workflows: See [development-guide.md#modifying-workflows](development-guide.md)
- Running tests: See [testing.md#running-tests](testing.md)
- Debugging: See [workflow-patterns.md#debugging](workflow-patterns.md)

**Key Patterns:**
- Per-sample grouping: [workflow-patterns.md#per-sample-grouping](workflow-patterns.md)
- Tuple-embedded channels: [code-quality.md#innovative-patterns](code-quality.md)
- Automatic format detection: [workflow-patterns.md#format-detection](workflow-patterns.md)

## External Resources

- [nf-core guidelines](https://nf-co.re/docs/guidelines)
- [Nextflow documentation](https://nextflow.io/docs/latest/)
- [nf-test documentation](https://www.nf-test.com/)
- [CAMI OPAL](https://github.com/CAMI-challenge/OPAL)
