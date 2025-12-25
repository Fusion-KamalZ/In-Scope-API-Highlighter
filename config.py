# config.py

# Creative Highlight Color Options for Burp Suite
# Maps display name -> Burp Suite highlight color name
HIGHLIGHT_COLORS = {
    "Classic Green": "green",
    "Ocean Teal": "cyan",
    "Sunset Orange": "orange",
    "Royal Magenta": "magenta",
    "Soft Pink": "pink",
}

class Config:
    def __init__(self):
        self.is_unique_url_enabled = False
        self.is_check_method_enabled = True  # If False, match only endpoint path, ignore method
        self.highlight_color = "green"  # Default highlight color
        # Set to store "METHOD:URL" strings of already highlighted requests
        self.seen_apis = set()
        # List of {'method': 'GET', 'url': 'example.com/api'}
        self.parsed_apis = []

    def clear(self):
        self.seen_apis.clear()
        self.parsed_apis = []

# Global instance to be shared across modules
state = Config()
