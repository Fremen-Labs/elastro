import sys
from elastro.config import load_config
from elastro.core.client import ElasticsearchClient


def setup_indices():
    try:
        cfg = load_config(None, "default")
        client = ElasticsearchClient(
            hosts=cfg["elasticsearch"]["hosts"],
            auth=cfg["elasticsearch"]["auth"],
            timeout=cfg["elasticsearch"]["timeout"],
            retry_on_timeout=cfg["elasticsearch"]["retry_on_timeout"],
            max_retries=cfg["elasticsearch"]["max_retries"],
        )
        client.connect()
        es = client.client
    except Exception as e:
        print(f"Failed to connect using Elastro config: {e}")
        sys.exit(1)

    # 1. Setup agent_semantic_memory
    memory_mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "note_type": {"type": "keyword"},
                "subject": {"type": "text", "analyzer": "english"},
                "content": {"type": "text", "analyzer": "english"},
                "tags": {"type": "keyword"},
            }
        }
    }

    # 2. Setup flow_tools
    tools_mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "tool_name": {"type": "keyword"},
                "file_path": {"type": "keyword"},
                "purpose": {"type": "text", "analyzer": "english"},
                "parameters": {"type": "text"},
            }
        }
    }

    try:
        if not es.indices.exists(index="agent_semantic_memory"):
            es.indices.create(index="agent_semantic_memory", body=memory_mapping)
            print("Created agent_semantic_memory index.")
        else:
            print("agent_semantic_memory already exists.")

        if not es.indices.exists(index="flow_tools"):
            es.indices.create(index="flow_tools", body=tools_mapping)
            print("Created flow_tools index.")
        else:
            print("flow_tools already exists.")

        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_indices()
