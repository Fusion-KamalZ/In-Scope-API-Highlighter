# postman_parser.py
import json

def parse_postman_collection(file_path):
    """Parses Postman v2.1 JSON and returns list of {'method': str, 'url': str}."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    apis = []
    _extract_recursively(data, apis)
    return apis

def _extract_recursively(node, apis):
    if isinstance(node, list):
        for item in node:
            _extract_recursively(item, apis)
    elif isinstance(node, dict):
        if 'request' in node:
            req = node['request']
            method = req.get('method', 'GET')
            url = req.get('url', {})
            
            # Extract Path Only
            path_str = ""
            if isinstance(url, dict) and 'path' in url and isinstance(url['path'], list):
                # Robust way: "path": ["api", "v1", "user"]
                path_parts = [str(p) for p in url['path']]
                path_str = "/" + "/".join(path_parts)
            else:
                # Fallback to parsing string/raw
                raw_url = ""
                if isinstance(url, str):
                    raw_url = url
                elif isinstance(url, dict):
                    raw_url = url.get('raw', "")
                
                if raw_url:
                    # heuristic: remove protocol://host or {{variable}}
                    # Find the first slash that isn't part of the protocol
                    # Regex: Remove protocol://domain.tld
                    import re
                    # Remove plain protocol http://domain
                    temp = re.sub(r'^https?://[^/]+', '', raw_url)
                    # Remove {{vars}} at start
                    temp = re.sub(r'^\{\{.*?\}\}', '', temp)
                    # What if it's {{base}}/api ? -> /api
                    
                    # Ensure starts with /
                    if not temp.startswith('/'):
                        temp = "/" + temp
                    
                    # Remove query params ?foo=bar
                    temp = temp.split('?')[0]
                    path_str = temp
            
            if path_str:
                apis.append({'method': method, 'path': path_str})
        
        if 'item' in node:
            _extract_recursively(node['item'], apis)

def parse_text_file(file_path):
    """Parses a text file with lines 'METHOD /path' or just '/path'."""
    apis = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    # Assume METHOD /path
                    method = parts[0].upper()
                    path = parts[1]
                else:
                    # Assume just /path, default generic GET
                    method = 'GET'
                    path = parts[0]
                
                # Cleanup path
                # Remove protocol if user pasted full URL
                import re
                path = re.sub(r'^https?://[^/]+', '', path)
                # Ensure starts with /
                if not path.startswith('/'):
                    path = '/' + path
                # Remove query params
                path = path.split('?')[0]
                
                apis.append({'method': method, 'path': path})
    except Exception as e:
        print("Error parsing text file: " + str(e))
        raise e
        
    return apis
