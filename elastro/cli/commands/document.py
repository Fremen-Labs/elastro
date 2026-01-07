"""
Document management commands for the CLI.
"""

import click
import json
import sys
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager
from elastro.core.errors import OperationError
from elastro.core.query_builder import QueryBuilder
from elastro.cli.output import format_output
from elastro.cli.completion import complete_indices

@click.command("index")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option("--id", type=str, help="Document ID")
@click.option("--file", type=click.Path(exists=True, readable=True), help="Path to document file")
@click.pass_obj
def index_document(client, index, id, file):
    """Index a document."""
    document_manager = DocumentManager(client)

    # Load document data
    if file:
        with open(file, 'r') as f:
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

@click.command("bulk")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option("--file", type=click.Path(exists=True, readable=True), required=True, help="Path to bulk documents file")
@click.pass_obj
def bulk_index(client, index, file):
    """Bulk index documents."""
    document_manager = DocumentManager(client)

    # Load documents data
    with open(file, 'r') as f:
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

@click.command("get")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.pass_obj
def get_document(client, index, id):
    """Get a document by ID."""
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
@click.option("--file", type=click.Path(exists=True, readable=True), help="Path to query file")
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
    client, index, query, size, from_, file,
    match, match_phrase, term, terms, range, prefix, wildcard, exists, ids, fuzzy,
    exclude_match, exclude_term
):
    """
    Search for documents using explicit flags or a query string.
    
    Supports combining multiple flags to build a bool query (AND by default).
    """
    document_manager = DocumentManager(client)

    # Determine query source
    if file:
        with open(file, 'r') as f:
            query_body = json.load(f)
    else:
        # Check if any flags set
        # If no flags and no query, default to match_all inside QueryBuilder
        # If flags set, build bool query.
        
        # Build the actual query part using QueryBuilder
        inner_query = QueryBuilder.build_bool_query(
            must_match=match,
            must_match_phrase=match_phrase,
            must_term=term,
            must_terms=terms,
            must_range=range,
            must_prefix=prefix,
            must_wildcard=wildcard,
            must_exists=exists,
            must_ids=ids,
            must_fuzzy=fuzzy,
            exclude_match=exclude_match,
            exclude_term=exclude_term,
            query_string=query
        )
        
        query_body = {"query": inner_query}

    # Add pagination
    options = {
        "size": size,
        "from": from_
    }

    try:
        results = document_manager.search(index, query_body, options)
        output = format_output(results)
        click.echo(output)
    except OperationError as e:
        click.echo(f"Error searching documents: {str(e)}", err=True)
        exit(1)

@click.command("update")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.option("--file", type=click.Path(exists=True, readable=True), required=True, help="Path to document file")
@click.option("--partial", is_flag=True, help="Perform partial update")
@click.pass_obj
def update_document(client, index, id, file, partial):
    """Update a document."""
    document_manager = DocumentManager(client)

    # Load document data
    with open(file, 'r') as f:
        document = json.load(f)

    try:
        result = document_manager.update(index, id, document, partial)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Document '{id}' in index '{index}' updated successfully.")
    except OperationError as e:
        click.echo(f"Error updating document: {str(e)}", err=True)
        exit(1)

@click.command("delete")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.argument("id", type=str)
@click.pass_obj
def delete_document(client, index, id):
    """Delete a document."""
    document_manager = DocumentManager(client)

    try:
        result = document_manager.delete(index, id)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Document '{id}' deleted from index '{index}'.")
    except OperationError as e:
        click.echo(f"Error deleting document: {str(e)}", err=True)
        exit(1)

@click.command("bulk-delete")
@click.argument("index", type=str, shell_complete=complete_indices)
@click.option("--file", type=click.Path(exists=True, readable=True), required=True, help="Path to IDs file")
@click.pass_obj
def bulk_delete(client, index, file):
    """Bulk delete documents."""
    document_manager = DocumentManager(client)

    # Load document IDs
    with open(file, 'r') as f:
        ids = json.load(f)

    if not isinstance(ids, list):
        click.echo("Error: IDs file must contain a JSON array of document IDs", err=True)
        exit(1)

    try:
        result = document_manager.bulk_delete(index, ids)
        output = format_output(result)
        click.echo(output)
        click.echo(f"Bulk deletion completed: {len(ids)} documents processed.")
    except OperationError as e:
        click.echo(f"Error in bulk deletion: {str(e)}", err=True)
        exit(1)
