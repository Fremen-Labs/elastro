import hmac
import hashlib
import requests
import json
import time
import sys

secret = b"dev-secret-key"
payload_dict = {
    "ref": "refs/heads/feature/async-client",
    "repository": {
        "name": "elastro",
        "full_name": "Fremen-Labs/elastro",
        "clone_url": "git@github.com:Fremen-Labs/elastro.git",
    },
    "head_commit": {
        "id": "master",  # just to pass validation if any
        "message": "AsyncElasticsearch Migration",
    },
}
payload = json.dumps(payload_dict).encode("utf-8")
signature = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()

try:
    res = requests.post(
        "http://127.0.0.1:8888/webhooks/github",
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
        },
        data=payload,
    )
    print(f"Status: {res.status_code}")
    print(res.text)
except Exception as e:
    print(f"Failed: {e}")
