# main.py
import sys
import os
import re

from burp import IBurpExtender, IHttpListener, ITab
# Swing imports
from javax.swing import (
    JPanel, JButton, JCheckBox, JFileChooser, JLabel, JScrollPane, 
    JTextArea, JTable, JSplitPane, BorderFactory, ListSelectionModel
)
from javax.swing.table import DefaultTableModel
from java.awt import BorderLayout, FlowLayout, Font, Dimension, Color

# Workaround to load local modules in Burp's Jython environment
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

from config import state
from postman_parser import parse_postman_collection, parse_text_file

class BurpExtender(IBurpExtender, IHttpListener, ITab):
    
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        
        callbacks.setExtensionName("In-Scope API Highlighter")
        
        # --- UI Initialization ---
        self._panel = JPanel(BorderLayout())
        
        # 1. Top Control Panel
        control_panel = JPanel(FlowLayout(FlowLayout.LEFT))
        control_panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))
        
        btn_load = JButton("Load Postman Collection", actionPerformed=self.load_collection)
        btn_load.setFont(Font("SansSerif", Font.BOLD, 12))

        btn_import_text = JButton("Import Text File", actionPerformed=self.load_text_file)
        btn_import_text.setFont(Font("SansSerif", Font.BOLD, 12))

        btn_reset = JButton("Reset", actionPerformed=self.reset_state)
        btn_reset.setFont(Font("SansSerif", Font.BOLD, 12))
        btn_reset.setForeground(Color.RED)
        
        self._cb_unique = JCheckBox("Unique Highlight Only", actionPerformed=self.toggle_unique)
        
        self._lbl_status = JLabel("Status: Waiting for input...")
        self._lbl_status.setForeground(Color.GRAY)
        
        control_panel.add(btn_load)
        control_panel.add(btn_import_text)
        control_panel.add(self._cb_unique)
        control_panel.add(btn_reset)
        control_panel.add(self._lbl_status)
        
        # 2. API Table (Center)
        self._table_model = DefaultTableModel(["Method", "Path"], 0)
        self._table = JTable(self._table_model)
        self._table.setFillsViewportHeight(True)
        self._table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self._table.getTableHeader().setFont(Font("SansSerif", Font.BOLD, 12))
        self._table.setRowHeight(20)
        
        table_scroll = JScrollPane(self._table)
        table_scroll.setBorder(BorderFactory.createTitledBorder("Extracted APIs"))
        
        # 3. Logs (Bottom)
        self._log_area = JTextArea()
        self._log_area.setEditable(False)
        self._log_area.setFont(Font("Monospaced", Font.PLAIN, 12))
        log_scroll = JScrollPane(self._log_area)
        log_scroll.setBorder(BorderFactory.createTitledBorder("Extension Logs"))
        
        # Split Pane for Table vs Logs
        split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, table_scroll, log_scroll)
        split_pane.setDividerLocation(300)
        split_pane.setResizeWeight(0.6)
        
        self._panel.add(control_panel, BorderLayout.NORTH)
        self._panel.add(split_pane, BorderLayout.CENTER)
        
        # --- Registration ---
        callbacks.addSuiteTab(self)
        callbacks.registerHttpListener(self)
        
        self.log("Extension loaded successfully. Ready to import Postman collection.")
        self.debug_mode = True

    # ITab
    def getTabCaption(self):
        return "Postman Analyzer"
    
    def getUiComponent(self):
        return self._panel
        
    # Actions
    def load_collection(self, event):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self._panel) == JFileChooser.APPROVE_OPTION:
            fpath = chooser.getSelectedFile().getPath()
            self.log("Loading collection: " + fpath)
            
            try:
                apis = parse_postman_collection(fpath)
                self._append_apis(apis)
                self.log("Successfully parsed {} APIs from collection.".format(len(apis)))
                
            except Exception as e:
                self.log("Error extracting APIs: " + str(e))
                self._lbl_status.setText("Error loading collection")
                self._lbl_status.setForeground(Color.RED)

    def load_text_file(self, event):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self._panel) == JFileChooser.APPROVE_OPTION:
            fpath = chooser.getSelectedFile().getPath()
            self.log("Loading text file: " + fpath)
            
            try:
                apis = parse_text_file(fpath)
                self._append_apis(apis)
                self.log("Successfully parsed {} APIs from text file.".format(len(apis)))
                
            except Exception as e:
                self.log("Error parsing text file: " + str(e))
                self._lbl_status.setText("Error loading text file")
                self._lbl_status.setForeground(Color.RED)

    def _append_apis(self, new_apis):
        # Append new APIs to global state
        state.parsed_apis.extend(new_apis)
        
        # Determine current row count to append correctly
        current_rows = self._table_model.getRowCount()
        
        for api in new_apis:
            self._table_model.addRow([api['method'], api['path']])
            
        total_apis = len(state.parsed_apis)
        self._lbl_status.setText("Total Loaded: {} APIs".format(total_apis))
        self._lbl_status.setForeground(Color(0, 100, 0)) # Dark Green

    def reset_state(self, event):
        # Clear global state
        state.parsed_apis = []
        state.seen_apis.clear()
        
        # Clear UI
        self._table_model.setRowCount(0)
        self._lbl_status.setForeground(Color.GRAY)
        self.log("Extension state reset.")

    def toggle_unique(self, event):
        state.is_unique_url_enabled = self._cb_unique.isSelected()
        self.log("Unique filter: {}".format(state.is_unique_url_enabled))

    def log(self, msg):
        self._log_area.append(msg + "\n")
        # Also print to stdout for standard debug
        print(msg)
        # Scroll to bottom
        self._log_area.setCaretPosition(self._log_area.getDocument().getLength())

    # IHttpListener
    def processHttpMessage(self, toolFlag, messageIsRequest, messageInfo):
        # Only Proxy (4) and only Requests
        if toolFlag != 4 or not messageIsRequest:
            return
            
        url_obj = self._helpers.analyzeRequest(messageInfo).getUrl()
        
        # Check Scope: Strict check now logic "Ignore Scope" removed
        if not self.debug_mode and not self._callbacks.isInScope(url_obj):
            # Debug log for user
            if self.debug_mode: print("DEBUG: Skipped (Not in Scope): " + str(url_obj))
            return

        method = self._helpers.analyzeRequest(messageInfo).getMethod()
        burp_path = url_obj.getPath()
        
        if self.debug_mode:
            print("Checking: {} {}".format(method, burp_path))

        if self.check_match(method, burp_path):
            identifier = "{} {}".format(method, burp_path)
            
            if state.is_unique_url_enabled:
                if identifier in state.seen_apis:
                    # self.log("Skipped (Duplicate): " + identifier)
                    return
                state.seen_apis.add(identifier)
            
            messageInfo.setHighlight("green")
            self.log("[MATCH] Highlighted: " + identifier)
        else:
            # Verbose debug for troubleshooting "Why isn't it highlighting?"
            # Only print if it looks like an API call to reduce noise? 
            # self.log("DEBUG: No Match for {} {}".format(method, burp_path))
            pass

    def check_match(self, method, burp_path):
        # Normalize Burp Path
        burp_clean = burp_path.rstrip('/')
        if not burp_clean: burp_clean = "/"
        
        # Filter by method
        same_method_apis = [api.get('path') for api in state.parsed_apis if api['method'].upper() == method.upper()]
        
        # Flexible match (ignore trailing slash)
        for api_path in same_method_apis:
            norm_api = api_path.rstrip('/')
            if not norm_api: norm_api = "/"
            
            if burp_clean == norm_api:
                return True
                
        return False
