import string
import random
from typing import Optional

def generate_random_password(length: int = 12) -> str:
    """
    Generate a random password with letters, digits, and punctuation.
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))