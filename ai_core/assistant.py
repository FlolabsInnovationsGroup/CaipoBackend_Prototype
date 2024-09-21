from ai_core.encryption_utils import encrypt_file, save_encrypted_data

def secure_env_file():
    file_path = ".env"
    password = "!@!#$^@&(%$&%)#^F%6L234O#$%M@#$A#@$D"
    
    # Encrypt the .env file
    encrypted_data = encrypt_file(file_path, password)
    
    # Save the encrypted file to disk
    save_encrypted_data("encrypted_env.bin", encrypted_data)
    print(f"Encrypted .env file saved as 'encrypted_env.bin'")
    
if __name__ == "__main__":
    secure_env_file()
