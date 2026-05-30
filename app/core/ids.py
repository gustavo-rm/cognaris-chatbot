"""ID generation utilities.

Single source of truth for UUID creation. Using a function indirection (rather
than calling uuid4 everywhere) lets us swap implementations — e.g., to UUIDv7
for time-ordering — without ripple changes.
"""
from uuid import UUID, uuid4


def new_id() -> UUID:
    return uuid4()