#!/usr/bin/env python3
import sys
import urllib3
from elasticsearch import Elasticsearch

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def try_connection(hosts, verify=False, ssl_show_warn=False, username=None, password=None):
    """Try to connect to Elasticsearch with different configurations."""
    print(f"\nAttempting connection to {hosts} with verify={verify} ssl_show_warn={ssl_show_warn}")
    
    try:
        # Set up client parameters
        client_params = {
            "hosts": hosts,
        }
        
        # Only add SSL params for HTTPS URLs
        if isinstance(hosts, list):
            uses_https = any(h.startswith('https://') for h in hosts if isinstance(h, str))
        else:
            uses_https = str(hosts).startswith('https://')
            
        if uses_https:
            client_params.update({
                "verify_certs": verify,
                "ssl_show_warn": ssl_show_warn,
                "ssl_assert_hostname": False
            })
            
        # Add authentication if provided
        if username and password:
            print(f"Using authentication: {username}:{password}")
            client_params["basic_auth"] = (username, password)
        
        # Create client
        es = Elasticsearch(**client_params)
        
        # Attempt ping
        print("Attempting ping...")
        ping_result = es.ping()
        print(f"Ping result: {ping_result}")
        
        # Get info if ping successful
        if ping_result:
            info = es.info()
            print(f"Connected to Elasticsearch {info['version']['number']}")
            return True
        else:
            print("Ping returned False")
            return False
            
    except Exception as e:
        print(f"Connection error: {type(e).__name__}: {str(e)}")
        return False

def main():
    """Try multiple connection configurations."""
    # Configuration options to try
    configs = [
        {"hosts": ["http://localhost:9200"], "username": "elastic", "password": "elastic_password"},
        {"hosts": ["https://localhost:9200"], "username": "elastic", "password": "elastic_password"},
        {"hosts": "http://localhost:9200", "username": "elastic", "password": "elastic_password"},
        {"hosts": "https://localhost:9200", "username": "elastic", "password": "elastic_password"},
    ]
    
    success = False
    for config in configs:
        if try_connection(**config):
            success = True
            print(f"SUCCESS with config: {config}")
            break
    
    if not success:
        print("All connection attempts failed")
        sys.exit(1)
    
    print("Successfully connected to Elasticsearch")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 