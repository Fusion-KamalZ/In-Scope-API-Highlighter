# config.py

class Config:
    def __init__(self):
        self.is_unique_url_enabled = False
        # Set to store "METHOD:URL" strings of already highlighted requests
        self.seen_apis = set()
        # List of {'method': 'GET', 'url': 'example.com/api'}
        self.parsed_apis = []

    def clear(self):
        self.seen_apis.clear()
        self.parsed_apis = []

# Global instance to be shared across modules
state = Config()
