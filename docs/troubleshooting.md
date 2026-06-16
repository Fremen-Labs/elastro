# Troubleshooting Elastro

This guide helps you diagnose and resolve common issues encountered while using Elastro.

## Connection Issues

### Unable to Connect to Elasticsearch

**Symptoms:**
- `ConnectionError: Failed to connect to Elasticsearch`
- Operations fail with connection timeout

**Possible Causes:**
- Incorrect host URL or port
- Elasticsearch server is down
- Network connectivity issues
- Firewall blocking the connection

**Solutions:**
1. Verify the host URL and port in your configuration
2. Check if Elasticsearch is running: `curl -X GET http://localhost:9200`
3. Ensure network connectivity between your application and Elasticsearch
4. Check firewall settings to allow connections on the Elasticsearch port
5. If using Docker, ensure the network configuration allows proper connectivity

### Authentication Failures

**Symptoms:**
- `AuthenticationError: Authentication failed`
- 401 Unauthorized responses

**Possible Causes:**
- Invalid API key or username/password
- Expired credentials
- Insufficient permissions

**Solutions:**
1. Verify your authentication credentials
2. Generate a new API key if needed
3. Check that the user has the necessary permissions
4. For Elasticsearch Cloud, verify your cloud ID is correct

## Configuration Issues

### Configuration Not Being Applied

**Symptoms:**
- Default settings used despite custom configuration
- Inconsistent behavior across environments

**Possible Causes:**
- Configuration file not found in the expected location
- Incorrectly formatted YAML/JSON
- Environment variables not set

**Solutions:**
1. Check configuration file location and format
2. Validate YAML/JSON syntax
3. Verify environment variables are set correctly
4. Use explicit configuration parameters in code to override defaults
5. Enable debug logging to see which configuration is being loaded:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Multiple Configuration Conflicts

**Symptoms:**
- Unexpected configuration being applied
- Settings being overridden unexpectedly

**Possible Causes:**
- Multiple configuration sources conflicting
- Wrong profile being selected

**Solutions:**
1. Understand the configuration precedence:
   - Explicit parameters override
   - Environment variables
   - Configuration files
2. Specify the profile explicitly when connecting:
   ```python
   from elastro import ElasticsearchClient
   client = ElasticsearchClient(profile="production")
   ```

## Index Operations Issues

### Index Creation Failures

**Symptoms:**
- `IndexError: Failed to create index`
- 400 Bad Request responses

**Possible Causes:**
- Index already exists
- Invalid settings or mappings
- Insufficient disk space
- Cluster state is red

**Solutions:**
1. Check if the index already exists with `index_manager.exists()`
2. Validate your settings and mappings against Elasticsearch documentation
3. Check cluster health with `client.health_check()`
4. Use the `ignore_existing=True` parameter when appropriate:
   ```python
   index_manager.create("my-index", ignore_existing=True)
   ```

### Missing Indices

**Symptoms:**
- `IndexError: Index not found`
- 404 Not Found responses

**Possible Causes:**
- Index name misspelled
- Index was deleted or never created
- Using incorrect index pattern

**Solutions:**
1. List available indices with `index_manager.list()`
2. Check for wildcards or patterns in index names
3. Create the index if needed
4. Use `ignore_missing=True` for operations where appropriate

## Health Assessment & Remediation

### Undoing an incorrect fix

**Symptoms:**
- Index settings changed unexpectedly after `elastro health assess --fix` or `elastro index fix`
- Replica count or routing filters differ from before remediation

**Solutions:**
1. Note the `rollback_id` returned in CLI JSON output or the GUI fix API response.
2. Preview the restore: `elastro health rollback apply --id <rollback_id> --dry-run`
3. Apply the rollback: `elastro health rollback apply --id <rollback_id>`
4. If the id was lost, list recent snapshots under `~/.elastic/health-rollbacks/`.

### Assessment history not appearing

**Symptoms:**
- `elastro health score --history` returns no records

**Solutions:**
1. Run at least one assessment with `--history`: `elastro health assess --history`
2. Confirm the history index name: `elastro config get health.assessment.history_index` (default: `elastro-health-assessments`)
3. Verify the connected user can create and write to that index.

---

## Document Operations Issues

### Document Indexing Failures

**Symptoms:**
- `DocumentError: Failed to index document`
- 400 Bad Request responses

**Possible Causes:**
- Document schema doesn't match the index mapping
- Field type conflicts
- Document size exceeds limits
- Required fields missing

**Solutions:**
1. Validate document schema against index mapping
2. Check for type conflicts (e.g., sending a string for a numeric field)
3. Split large documents or increase Elasticsearch limits
4. Use the validation module to validate documents before indexing:
   ```python
   from elastro.core.validation import validate_document
   validate_document(document, schema)
   ```

### Search Query Issues

**Symptoms:**
- Empty search results when documents should exist
- `OperationError: Failed to execute search`
- Query returning too many or unexpected results

**Possible Causes:**
- Query syntax errors
- Field names misspelled
- Analyzer issues affecting tokenization
- Too restrictive filtering

**Solutions:**
1. Test query directly in Elasticsearch Dev Tools
2. Check field names in the mapping
3. Use `match` instead of `term` for analyzed text fields
4. Start with a simpler query and build complexity gradually
5. Use `explain=True` to understand the relevance scoring:
   ```python
   results = doc_manager.search(index="products", query={"match": {"name": "laptop"}}, explain=True)
   ```

## Bulk Operations Issues

### Bulk Indexing Failures

**Symptoms:**
- `DocumentError: Bulk operation partially failed`
- Some documents indexed but others failed

**Possible Causes:**
- Rejections due to version conflicts
- Some documents violating mappings
- Memory pressure during large bulk operations

**Solutions:**
1. Check the response for specific error details
2. Validate all documents before bulk indexing
3. Reduce batch sizes for very large operations
4. Use optimized serialization for large documents
5. Handle version conflicts with appropriate versioning strategy:
   ```python
   doc_manager.bulk_index("products", documents, version_type="external")
   ```

## CLI Issues

### Command Not Found

**Symptoms:**
- `elastic-cli: command not found`

**Possible Causes:**
- Package not installed properly
- Python scripts directory not in PATH
- Virtual environment not activated

**Solutions:**
1. Reinstall the package: `pip install -e .`
2. Ensure Python scripts directory is in PATH
3. Activate your virtual environment
4. Install with the `--user` flag if appropriate: `pip install --user elastic-module`

### CLI Configuration Issues

**Symptoms:**
- CLI commands failing with configuration errors
- Commands using unexpected settings

**Possible Causes:**
- No configuration file initialized
- Wrong profile selected
- Configuration file permissions issues

**Solutions:**
1. Initialize configuration: `elastic-cli config init`
2. Specify profile when running commands: `elastic-cli --profile=dev index list`
3. Check configuration file permissions
4. Use environment variables to override configuration temporarily

## Performance Issues

### Slow Operations

**Symptoms:**
- Operations taking longer than expected
- Timeouts during large operations

**Possible Causes:**
- Inefficient queries
- Missing or improper index settings
- Network latency
- Inadequate Elasticsearch resources

**Solutions:**
1. Optimize query structure and use filters instead of queries when possible
2. Add appropriate indexes for search patterns
3. Increase timeout settings for long-running operations:
   ```python
   client = ElasticsearchClient(timeout=120)  # 2 minutes
   ```
4. Use pagination for large result sets
5. Consider using async operations for bulk processing

### Memory Issues

**Symptoms:**
- Out of memory errors
- Process crashes during large operations

**Possible Causes:**
- Loading too many documents in memory
- Large bulk operations
- Deep pagination with large result sets

**Solutions:**
1. Use scroll API for processing large result sets:
   ```python
   from elastro.advanced import scroll_search
   for batch in scroll_search(doc_manager, "products", query, batch_size=1000):
       process_batch(batch)
   ```
2. Reduce batch sizes for bulk operations
3. Use generators to process results incrementally
4. Avoid deep pagination; use search_after or scroll instead

## Logging and Debugging

### Enabling Debug Logs

To get more detailed information about operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('elastro').setLevel(logging.DEBUG)
```

For CLI operations:

```bash
elastic-cli --debug index list
```

### Tracing Elasticsearch Requests

To see the actual requests sent to Elasticsearch:

```python
import logging
logging.getLogger('elasticsearch').setLevel(logging.DEBUG)
```

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [GitHub issues](https://github.com/Fremen-Labs/elastro/issues) for similar problems
2. Review the Elasticsearch documentation for specific error messages
3. Enable debug logging and examine the logs
4. Open a new issue with details about your environment, steps to reproduce, and error messages
