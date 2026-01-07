from elasticsearch import Elasticsearch; print("Testing connection"); client = Elasticsearch(hosts=["http://localhost:9200"], verify_certs=False); print(f"Ping result: {client.ping()}")
