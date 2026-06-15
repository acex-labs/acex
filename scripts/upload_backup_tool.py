#!/usr/bin/env python3
import argparse
import base64
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    parser = argparse.ArgumentParser(description="Upload a device config backup to ACEX")
    parser.add_argument("node_id", help="Node instance ID")
    parser.add_argument("content", help="Path to the config file to upload")
    parser.add_argument("--url", default="http://127.0.0.1/", help="ACEX base URL (default: http://127.0.0.1/)")
    parser.add_argument("--api-ver", default=1, type=int, help="API version (default: 1)")
    parser.add_argument("--no-verify", action="store_true", help="Disable SSL certificate verification")
    args = parser.parse_args()

    try:
        with open(args.content, "rb") as f:
            raw = f.read()
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    encoded = base64.b64encode(raw).decode()

    api_url = f"{args.url.rstrip('/')}/api/v{args.api_ver}"
    endpoint = f"{api_url}/operations/device_configs/"

    response = requests.post(
        endpoint,
        json={"node_instance_id": args.node_id, "content": encoded},
        verify=not args.no_verify,
    )

    if response.status_code == 409:
        print("No change — config matches latest stored backup.")
        sys.exit(0)

    if not response.ok:
        print(f"Upload failed ({response.status_code}): {response.text}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    print(f"Uploaded. Hash: {data.get('hash')}  ID: {data.get('id')}  Created: {data.get('created_at')}")


if __name__ == "__main__":
    main()
