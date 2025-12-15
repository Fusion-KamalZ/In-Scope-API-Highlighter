# Burp Suite Extension: In-Scope API Highlighter

Highlights In-Scope Proxy traffic if it matches requests in a Postman Collection.

## Features
- **Load Collection**: Supports Postman v2.1 JSON.
- **API List View**: Displays all imported API methods and paths in a table.
- **Auto-Highlight**: Marks matching requests **Green**.
- **In-Scope Only**: Only highlights requests that are defined in Burp's Target Scope.
- **Unique Filter**: Optionally highlight each unique endpoint only once.

## Installation
1.  **Requirement**: Jython Standalone JAR configured in Burp (Extender > Options > Python Environment).
2.  **Add Extension**:
    -   Type: `Python`
    -   File: `main.py`

## Usage
1.  Go to the **Postman Analyzer** tab.
2.  Click **Load Postman Collection** and select your `.json` file.
3.  You will see the list of extracted APIs in the central table.
4.  Browse the target site via Burp Proxy.
5.  Matching requests (that are **In Scope**) will be highlighted Green in the **HTTP History**.

## Troubleshooting
**"No requests are being highlighted?"**
1.  **Check Scope**: Ensure your target URL is added to **Target > Scope**.
2.  **Check Table**: Verify that your API paths are correctly listed in the extension table.
3.  **Check Logs**: Look at the "Extension Logs" pane at the bottom for match confirmations.

