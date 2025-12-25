# config.py
import json
import os

# Creative Highlight Color Options for Burp Suite
# Maps display name -> Burp Suite highlight color name
HIGHLIGHT_COLORS = {
    "Classic Green": "green",
    "Ocean Teal": "cyan",
    "Sunset Orange": "orange",
    "Royal Magenta": "magenta",
    "Soft Pink": "pink",
}

# State file path - stored in user's home directory
STATE_FILE = os.path.join(os.path.expanduser("~"), ".burp_api_highlighter_state.json")

class Config:
    def __init__(self):
        self.is_unique_url_enabled = False
        self.is_check_method_enabled = True  # If False, match only endpoint path, ignore method
        self.highlight_color = "green"  # Default highlight color
        # Set to store "METHOD:URL" strings of already highlighted requests
        self.seen_apis = set()
        # List of {'method': 'GET', 'path': '/api/v1/user'}
        self.parsed_apis = []

    def clear(self):
        self.seen_apis.clear()
        self.parsed_apis = []

    def save_state(self, file_path=None):
        """Save current state to JSON file for persistence across sessions"""
        target_path = file_path if file_path else STATE_FILE
        data = {
            "is_unique_url_enabled": self.is_unique_url_enabled,
            "is_check_method_enabled": self.is_check_method_enabled,
            "highlight_color": self.highlight_color,
            "seen_apis": list(self.seen_apis),  # Convert set to list for JSON
            "parsed_apis": self.parsed_apis,
        }
        try:
            with open(target_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True, "State saved to: " + target_path
        except Exception as e:
            return False, "Error saving state: " + str(e)

    def load_state(self, file_path=None):
        """Load state from JSON file if it exists"""
        target_path = file_path if file_path else STATE_FILE
        if not os.path.exists(target_path):
            return False, "No saved state found at: " + target_path
        try:
            with open(target_path, 'r') as f:
                data = json.load(f)
            self.is_unique_url_enabled = data.get("is_unique_url_enabled", False)
            self.is_check_method_enabled = data.get("is_check_method_enabled", True)
            self.highlight_color = data.get("highlight_color", "green")
            self.seen_apis = set(data.get("seen_apis", []))
            self.parsed_apis = data.get("parsed_apis", [])
            return True, "State loaded: {} APIs, {} seen".format(len(self.parsed_apis), len(self.seen_apis))
        except Exception as e:
            return False, "Error loading state: " + str(e)

# Global instance to be shared across modules
state = Config()

