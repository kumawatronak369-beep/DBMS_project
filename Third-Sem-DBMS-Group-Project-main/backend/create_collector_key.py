"""Create a collector API key, and its node if it does not exist.

Usage: python create_collector_key.py --node-code HOME-PC --node-name "My Computer"
The key is printed once; only its hash is stored.
"""

import argparse
import secrets
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_api_key
from app.db.session import SessionLocal
from app.models import CollectorApiKey, Node


def create_key(db, *, node_code: str, node_name: str, location: str, ip_address: str, key_name: str) -> tuple[Node, str, bool]:
    node = db.query(Node).filter(Node.node_code == node_code).one_or_none()
    created = node is None
    if created:
        node = Node(node_code=node_code, node_name=node_name, ip_address=ip_address, location=location, status="ACTIVE")
        db.add(node)
        db.flush()
    plain_key = "nm_" + secrets.token_urlsafe(32)
    db.add(CollectorApiKey(node_id=node.node_id, key_name=key_name, key_hash=hash_api_key(plain_key), status="ACTIVE"))
    db.commit()
    return node, plain_key, created


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a collector API key for a node (creating the node if new).")
    parser.add_argument("--node-code", required=True, help="short unique code, e.g. HOME-PC")
    parser.add_argument("--node-name", help="display name for a NEW node, e.g. 'My Computer'")
    parser.add_argument("--location", default="Home", help="location for a NEW node (default: Home)")
    parser.add_argument("--ip", default="127.0.0.1", help="address of the observation point for a NEW node")
    parser.add_argument("--key-name", default="local collector", help="label for this key")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        exists = db.query(Node).filter(Node.node_code == args.node_code).count() > 0
        if not exists and not args.node_name:
            print(f"Node '{args.node_code}' does not exist yet: add --node-name to create it.", file=sys.stderr)
            return 2
        try:
            node, key, created = create_key(
                db, node_code=args.node_code, node_name=args.node_name or "", location=args.location,
                ip_address=args.ip, key_name=args.key_name,
            )
        except SQLAlchemyError as error:
            db.rollback()
            print(f"Could not create the key: {type(error).__name__}", file=sys.stderr)
            return 1

    print(f"{'Created node' if created else 'Using existing node'}: {node.node_code} ({node.node_name})")
    print("\nCollector API key (shown once, copy it now):\n")
    print(f"    {key}\n")
    print("Put it in collector/.env as:  COLLECTOR_API_KEY=<the key above>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
