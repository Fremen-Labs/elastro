"""
Document management commands for the CLI.
"""

import rich_click as click
import json
import sys
from typing import Optional, Tuple, Any
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager
from elastro.core.errors import OperationError
from elastro.core.query_builder import QueryBuilder
from elastro.cli.output import format_output
from elastro.cli.completion import complete_indices


@click.command("index", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option("--id", type=str, help="Document ID")
@click.option(
    "--file", type=click.Path(exists=True, readable=True), help="Path to document file"
)
@click.pass_obj
def index_document(
    client: ElasticsearchClient, index: str, id: Optional[str], file: Optional[str]
) -> None:
    """
    Index a document.

    Indexes a single JSON document. You can provide the document body via a file or standard input.

    Examples:

    Index from file:
    ```bash
    elastro doc index my-logs --file ./event.json
    ```

    Index from stdin:
    ```bash
    echo '{"user": "jon", "action": "login"}' | elastro doc index my-logs
    ```

    Specify explicit ID:
    ```bash
    elastro doc index my-logs --id 123 --file ./user.json
    ```
    """
    document_manager = DocumentManager(client)

    # Load document data
    if file:
        with open(file, "r") as f:
            document = json.load(f)
    else:
        # Read from stdin if no file provided
        document = json.loads(sys.stdin.read())

    try:
        result = document_manager.index(index, id, document)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Document indexed successfully in '{index}'.")
    except OperationError as e:
        click.echo(f"Error indexing document: {str(e)}", err=True)
        exit(1)


@click.command("bulk", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option(
    "--file",
    type=click.Path(exists=True, readable=True),
    required=True,
    help="Path to bulk documents file",
)
@click.pass_obj
def bulk_index(client: ElasticsearchClient, index: str, file: str) -> None:
    """
    Bulk index documents.

    Indexes multiple documents from a JSON array file.

    Examples:

    Bulk index from a JSON array file:
    ```bash
    elastro doc bulk my-logs --file ./bulk_data.json
    ```
    """
    document_manager = DocumentManager(client)

    # Load documents data
    with open(file, "r") as f:
        documents = json.load(f)

    if not isinstance(documents, list):
        click.echo("Error: Bulk file must contain a JSON array of documents", err=True)
        exit(1)

    try:
        result = document_manager.bulk_index(index, documents)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Bulk indexing completed: {len(documents)} documents processed.")
    except OperationError as e:
        click.echo(f"Error in bulk indexing: {str(e)}", err=True)
        exit(1)


@click.command("get", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.pass_obj
def get_document(client: ElasticsearchClient, index: str, id: str) -> None:
    """
    Get a document by ID.

    Retrieves a single document source and metadata.

    Examples:

    Get document by ID:
    ```bash
    elastro doc get my-logs 123
    ```
    """
    document_manager = DocumentManager(client)

    try:
        result = document_manager.get(index, id)
        output = format_output(result)
        click.echo(output)
    except OperationError as e:
        click.echo(f"Error retrieving document: {str(e)}", err=True)
        exit(1)


@click.command("search")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("query", type=str, required=False)
@click.option("--size", type=int, default=10, help="Maximum number of results")
@click.option("--from", "from_", type=int, default=0, help="Starting offset")
@click.option(
    "--file", type=click.Path(exists=True, readable=True), help="Path to query file"
)
# Top 10 Query Types
@click.option("--match", multiple=True, help="Match query (field=value)")
@click.option("--match-phrase", multiple=True, help="Match phrase query (field=phrase)")
@click.option("--term", multiple=True, help="Term query (field=value)")
@click.option("--terms", multiple=True, help="Terms query (field=val1,val2)")
@click.option("--range", multiple=True, help="Range query (field=op:val)")
@click.option("--prefix", multiple=True, help="Prefix query (field=value)")
@click.option("--wildcard", multiple=True, help="Wildcard query (field=pattern)")
@click.option("--exists", multiple=True, help="Exists query (field)")
@click.option("--ids", multiple=True, help="IDs query (id1,id2)")
@click.option("--fuzzy", multiple=True, help="Fuzzy query (field=value)")
# Excludes
@click.option("--exclude-match", multiple=True, help="Exclude match (must_not)")
@click.option("--exclude-term", multiple=True, help="Exclude term (must_not)")
@click.pass_obj
def search_documents(
    client: ElasticsearchClient,
    index: str,
    query: Optional[str],
    size: int,
    from_: int,
    file: Optional[str],
    match: Tuple[str, ...],
    match_phrase: Tuple[str, ...],
    term: Tuple[str, ...],
    terms: Tuple[str, ...],
    range: Tuple[str, ...],
    prefix: Tuple[str, ...],
    wildcard: Tuple[str, ...],
    exists: Tuple[str, ...],
    ids: Tuple[str, ...],
    fuzzy: Tuple[str, ...],
    exclude_match: Tuple[str, ...],
    exclude_term: Tuple[str, ...],
) -> None:
    """
    Search for documents using explicit flags or a query string.

    Supports combining multiple flags to build a bool query (AND by default).
    Or provide a raw query body via --file.

    Examples:

    Simple match query:
    ```bash
    elastro doc search my-logs --match status=error
    ```

    Combine queries (AND operations):
    ```bash
    elastro doc search my-logs --match status=error --range timestamp=gte:now-1h
    ```

    Use full Query DSL from file:
    ```bash
    elastro doc search my-logs --file ./advanced_query.json
    ```
    """
    document_manager = DocumentManager(client)

    # Determine query source
    if file:
        with open(file, "r") as f:
            query_body = json.load(f)
    else:
        # Check if any flags set
        # If no flags and no query, default to match_all inside QueryBuilder
        # If flags set, build bool query.

        # Build the actual query part using QueryBuilder
        inner_query = QueryBuilder.build_bool_query(
            must_match=list(match) if match else None,
            must_match_phrase=list(match_phrase) if match_phrase else None,
            must_term=list(term) if term else None,
            must_terms=list(terms) if terms else None,
            must_range=list(range) if range else None,
            must_prefix=list(prefix) if prefix else None,
            must_wildcard=list(wildcard) if wildcard else None,
            must_exists=list(exists) if exists else None,
            must_ids=list(ids) if ids else None,
            must_fuzzy=list(fuzzy) if fuzzy else None,
            exclude_match=list(exclude_match) if exclude_match else None,
            exclude_term=list(exclude_term) if exclude_term else None,
            query_string=query,
        )

        query_body = {"query": inner_query}

    # Add pagination
    options = {"size": size, "from": from_}

    try:
        results = document_manager.search(index, query_body, options)
        output = format_output(results)
        click.echo(output)
    except OperationError as e:
        click.echo(f"Error searching documents: {str(e)}", err=True)
        exit(1)


@click.command("update", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.option(
    "--file",
    type=click.Path(exists=True, readable=True),
    required=True,
    help="Path to document file",
)
@click.option("--partial", is_flag=True, help="Perform partial update")
@click.pass_obj
def update_document(
    client: ElasticsearchClient, index: str, id: str, file: str, partial: bool
) -> None:
    """
    Update a document.

    Updates an existing document. Use --partial to update only specific fields.

    Examples:

    Full document replacement:
    ```bash
    elastro doc update my-logs 123 --file ./new_doc.json
    ```

    Partial update (only specified fields):
    ```bash
    elastro doc update my-logs 123 --file ./fields.json --partial
    ```
    """
    document_manager = DocumentManager(client)

    # Load document data
    with open(file, "r") as f:
        document = json.load(f)

    try:
        result = document_manager.update(index, id, document, partial)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Document '{id}' in index '{index}' updated successfully.")
    except OperationError as e:
        click.echo(f"Error updating document: {str(e)}", err=True)
        exit(1)


@click.command("delete", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.pass_obj
def delete_document(client: ElasticsearchClient, index: str, id: str) -> None:
    """
    Delete a document.

    Permanently removes a single document by ID.

    Examples:

    Delete a document by ID:
    ```bash
    elastro doc delete my-logs 123
    ```
    """
    document_manager = DocumentManager(client)

    try:
        result = document_manager.delete(index, id)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Document '{id}' deleted from index '{index}'.")
    except OperationError as e:
        click.echo(f"Error deleting document: {str(e)}", err=True)
        exit(1)


@click.command("bulk-delete", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option(
    "--file",
    type=click.Path(exists=True, readable=True),
    required=True,
    help="Path to IDs file",
)
@click.pass_obj
def bulk_delete(client: ElasticsearchClient, index: str, file: str) -> None:
    """
    Bulk delete documents.

    Deletes multiple documents using a JSON array of IDs.

    Examples:

    Bulk delete using a list of IDs:
    ```bash
    elastro doc bulk-delete my-logs --file ./ids_to_delete.json
    ```
    """
    document_manager = DocumentManager(client)

    # Load document IDs
    with open(file, "r") as f:
        ids = json.load(f)

    if not isinstance(ids, list):
        click.echo(
            "Error: IDs file must contain a JSON array of document IDs", err=True
        )
        exit(1)

    try:
        result = document_manager.bulk_delete(index, ids)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Bulk deletion completed: {len(ids)} documents processed.")
    except OperationError as e:
        click.echo(f"Error in bulk deletion: {str(e)}", err=True)
        exit(1)
