"""
Generates a VAPID key pair for Web Push reminders (run once, on your own machine):

    pip install "pywebpush==2.5.0"
    python -m backend.scripts.generate_vapid_keys

Put the PUBLIC key in Render as VAPID_PUBLIC_KEY (the backend hands it to browsers) and the
PRIVATE key only in the GitHub Actions secret VAPID_PRIVATE_KEY (the reminder worker signs with
it). The private key is printed to your terminal only; never commit it or paste it into chats.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = b64url(key.private_numbers().private_value.to_bytes(32, "big"))
    public = b64url(key.public_key().public_bytes(serialization.Encoding.X962,
                                                  serialization.PublicFormat.UncompressedPoint))
    print("VAPID_PUBLIC_KEY  (Render env):           ", public)
    print("VAPID_PRIVATE_KEY (GitHub Actions secret): ", private)


if __name__ == "__main__":
    main()
