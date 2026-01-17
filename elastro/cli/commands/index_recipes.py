from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class IndexRecipe:
    name: str
    description: str
    settings: Dict[str, Any]
    mappings: Dict[str, Any]
    prompts: List[Dict[str, Any]] = None

    def get_settings(self) -> Dict[str, Any]:
        return self.settings.copy()

    def get_mappings(self) -> Dict[str, Any]:
        return self.mappings.copy()

RECIPES: Dict[str, IndexRecipe] = {
    "1": IndexRecipe(
        name="Standard Text Search",
        description="Optimized for full-text search with English analyzer and keyword sub-fields.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "title": {
                    "type": "text",
                    "analyzer": "english",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                "content": {
                    "type": "text",
                    "analyzer": "english"
                },
                "category": {
                    "type": "keyword"
                },
                "published_date": {
                    "type": "date"
                }
            }
        }
    ),
    "2": IndexRecipe(
        name="High-Volume Logs",
        description="Time-series log data with @timestamp, IP handling, and keyword optimization.",
        settings={
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "refresh_interval": "30s"
        },
        mappings={
            "properties": {
                "@timestamp": {
                    "type": "date"
                },
                "level": {
                    "type": "keyword"
                },
                "message": {
                    "type": "text"
                },
                "source_ip": {
                    "type": "ip"
                },
                "host": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "os": {"type": "keyword"}
                    }
                }
            }
        }
    ),
    "3": IndexRecipe(
        name="Strict Financial Data",
        description="Strict mapping enforcement, no coercion, and scaled floats for currency.",
        settings={
            "number_of_shards": 2,
            "number_of_replicas": 2
        },
        mappings={
            "dynamic": "strict",
            "properties": {
                "transaction_id": {
                    "type": "keyword"
                },
                "amount": {
                    "type": "scaled_float",
                    "scaling_factor": 100
                },
                "currency": {
                    "type": "keyword"
                },
                "status": {
                    "type": "keyword"
                },
                "timestamp": {
                    "type": "date",
                    "format": "strict_date_optional_time||epoch_millis"
                }
            }
        }
    ),
    "4": IndexRecipe(
        name="Geo-Spatial Data",
        description="Storage for Geo-Points (Lat/Lon) and Geo-Shapes.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "name": {
                    "type": "text"
                },
                "location": {
                    "type": "geo_point"
                },
                "boundary": {
                    "type": "geo_shape"
                },
                "city": {
                    "type": "keyword"
                }
            }
        }
    ),
    "5": IndexRecipe(
        name="Nested Objects",
        description="Handling arrays of objects independently using 'nested' type.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "product_id": {
                    "type": "keyword"
                },
                "reviews": {
                    "type": "nested",
                    "properties": {
                        "user": {"type": "keyword"},
                        "comment": {"type": "text"},
                        "stars": {"type": "integer"}
                    }
                }
            }
        }
    ),
    "6": IndexRecipe(
        name="Flattened Metadata",
        description="Efficiently handle large numbers of arbitrary keys using 'flattened' type.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "service_name": {
                    "type": "keyword"
                },
                "metadata": {
                    "type": "flattened"
                },
                "tags": {
                    "type": "keyword"
                }
            }
        }
    ),
    "7": IndexRecipe(
        name="Custom Routing",
        description="Optimization for high-cardinality searches using custom routing partition.",
        settings={
            "number_of_shards": 4,
            "number_of_replicas": 1,
            "routing_partition_size": 2
        },
        mappings={
            "_routing": {
                "required": True
            },
            "properties": {
                "user_id": {
                    "type": "keyword"
                },
                "doc_id": {
                    "type": "keyword"
                },
                "content": {
                    "type": "text"
                }
            }
        }
    ),
    "8": IndexRecipe(
        name="Optimized Metrics",
        description="Space-saving numeric types (byte, half_float) for metric data.",
        settings={
            "number_of_shards": 2,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "metric_name": {
                    "type": "keyword"
                },
                "value_cpu": {
                    "type": "half_float"
                },
                "value_memory": {
                    "type": "long"
                },
                "load_status": {
                    "type": "byte"
                },
                "timestamp": {
                    "type": "date"
                }
            }
        }
    ),
    "9": IndexRecipe(
        name="Binary / Blob Store",
        description="Store base64 encoded binary data with 'enabled: false' to save overhead.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "filename": {
                    "type": "keyword"
                },
                "mime_type": {
                    "type": "keyword"
                },
                "blob_data": {
                    "type": "binary",
                    "doc_values": False,
                    "store": True
                },
                "raw_metadata": {
                    "type": "object",
                    "enabled": False
                }
            }
        }
    ),
    "10": IndexRecipe(
        name="Autocomplete",
        description="Search-as-you-type functionality using specialized text fields.",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        mappings={
            "properties": {
                "suggestion": {
                    "type": "search_as_you_type"
                },
                "full_title": {
                    "type": "text"
                },
                "popularity": {
                    "type": "integer"
                }
            }
        }
    )
}

def get_recipe_choices():
    return [f"{k}. {v.name}" for k, v in RECIPES.items()]
