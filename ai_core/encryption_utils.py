from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, kdf

from cryptography.hazmat.primitives.kdf import pbkdf2
import os

# AES-256-GCM (Galois Counter Mode) Encryption Algorithm Development

def generate_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from the password using PBKDF2."""
    kdf1 = kdf.pbkdf2.PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 32 bytes = 256 bits
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf1.derive(password.encode())
    return key

def encrypt_file(file_path: str, password: str):
    # Read the .env file contents
    with open(file_path, 'rb') as file:
        file_data = file.read()
    
    # Generate a random 256-bit (32 bytes) key from the password
    salt = os.urandom(16)  # 16-byte salt for key derivation
    key = generate_key(password, salt)

    # Generate a 12-byte IV (GCM standard)
    iv = os.urandom(12)

    # Create the AES-256-GCM cipher
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    # Encrypt the file data
    ciphertext = encryptor.update(file_data) + encryptor.finalize()

    # Authentication tag (used for integrity check)
    tag = encryptor.tag

    # Return the encrypted components
    return {
        'ciphertext': ciphertext,
        'iv': iv,
        'tag': tag,
        'salt': salt
    }

# Encrypt the .env file
encrypted_data = encrypt_file('.env', 'your-strong-password')

# Save the encrypted components for later decryption
with open('encrypted_env.bin', 'wb') as enc_file:
    # Write salt, iv, tag, and ciphertext sequentially
    enc_file.write(encrypted_data['salt'])
    enc_file.write(encrypted_data['iv'])
    enc_file.write(encrypted_data['tag'])
    enc_file.write(encrypted_data['ciphertext'])
