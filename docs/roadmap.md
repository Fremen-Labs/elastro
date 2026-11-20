# Elastro Roadmap

This document outlines planned and potential future features for the `elastro` package. These features are designed to enhance the functionality and usability of the package for working with Elasticsearch.

Cluster health monitoring has already shipped under `elastro health` (`assess`, `fix`, `shards`, `nodes`, `score`, `trends`, ILM, lint, and rollback). The Cluster Health Monitor item below is historical wishlist, not a remaining gap.

## Advanced Features

### Reindex Helper
- Simplified reindexing operations with progress tracking
- Configurable batch sizes and concurrency
- Error handling with retry mechanisms
- Support for transformations during reindexing
- Validation of destination mappings

### Suggestions Builder
- Completion suggester builder for autocomplete functionality
- Phrase suggester for "did you mean" functionality
- Term suggester for spell checking
- Context suggester support for context-aware suggestions

### Percolator Manager
- Interface for managing percolator queries
- Registration and deregistration of stored queries
- Document matching against percolator queries
- Bulk percolation operations

### Template Manager
- Management of index templates and component templates
- Validation of template patterns
- Template priority management
- Template versioning support

### Analyzers Builder
- Builder for custom analyzers, tokenizers, and filters
- Built-in analyzer presets for common use cases
- Testing capabilities for analyzer configurations
- Support for language-specific analyzers

### Mappings Builder
- Programmatic building of index mappings
- Field type definitions with validation
- Dynamic mapping configuration
- Multi-field support
- Field parameter configuration

### Bulk Operations Helper
- Advanced retry and backoff strategies
- Error handling with partial success support
- Automatic chunking of large operations
- Progress tracking and reporting
- Memory efficient processing

### Search Template Manager
- Parameterized search template support
- CRUD operations for stored search templates
- Mustache template validation
- Rendering and execution of templates

### Pipeline Manager
- Creation and management of ingest pipelines
- Pipeline simulation and testing
- Pipeline processors configuration
- Pipeline conditional logic

### Alias Manager
- Index alias management
- Zero-downtime reindexing via aliases
- Rolling index strategies
- Filtered aliases support

### Field Capabilities Helper
- Exploration of field types across indices
- Field mapping compatibility checks
- Field statistics and cardinality estimation
- Field usage recommendations

### Task Manager
- Management of long-running Elasticsearch tasks
- Task cancellation
- Task prioritization
- Task status monitoring

### Snapshot Manager
- Repository management
- Snapshot creation and restoration
- Snapshot scheduling
- Partial snapshot/restore operations

### Cluster Health Monitor
- Cluster health status tracking
- Node statistics collection
- Shard allocation monitoring
- Hot threads analysis
- Cluster settings management

### Search Profiler
- Query performance analysis
- Slow query identification
- Query optimization recommendations
- Timing breakdowns for query components

## CLI Enhancements

- Interactive query builder
- Query history and favorites
- Export/import functionality for complex queries
- Visualization of basic aggregation results
- Batch processing commands

## Core Improvements

- Async API support
- Comprehensive connection pooling options
- Cross-cluster search support
- Security enhancements (field and document level security)
- Caching layer for frequent queries

## Developer Experience

- More comprehensive examples
- Interactive tutorials
- Performance benchmarking tools
- Development environment containers 