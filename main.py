# main.py
import sys
import os
import re

from burp import IBurpExtender, IHttpListener, ITab
# Swing imports
from javax.swing import (
    JPanel, JButton, JCheckBox, JFileChooser, JLabel, JScrollPane, 
    JTextArea, JTable, JSplitPane, BorderFactory, ListSelectionModel,
    JComboBox
)
from javax.swing.table import DefaultTableModel
from javax.swing.event import TableModelListener
from java.awt import BorderLayout, FlowLayout, Font, Dimension, Color
import java.io

# Workaround to load local modules in Burp's Jython environment
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

from config import state, HIGHLIGHT_COLORS
from postman_parser import parse_postman_collection, parse_text_file


class TableEditListener(TableModelListener):
    """Listener to sync table edits back to state.parsed_apis"""
    
    def __init__(self, extender):
        self.extender = extender
    
    def tableChanged(self, event):
        # Only handle UPDATE events (not INSERT/DELETE during load)
        if event.getType() == event.UPDATE:
            row = event.getFirstRow()
            col = event.getColumn()
            
            # Validate row index
            if row < 0 or row >= len(state.parsed_apis):
                return
            
            new_value = self.extender._table_model.getValueAt(row, col)
            
            if col == 0:  # Method column
                old_value = state.parsed_apis[row]['method']
                state.parsed_apis[row]['method'] = str(new_value).upper()
                self.extender.log("Row {}: Method changed '{}' -> '{}'".format(row, old_value, new_value))
            elif col == 1:  # Path column
                old_value = state.parsed_apis[row]['path']
                state.parsed_apis[row]['path'] = str(new_value)
                self.extender.log("Row {}: Path changed '{}' -> '{}'".format(row, old_value, new_value))


class BurpExtender(IBurpExtender, IHttpListener, ITab):
    
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        
        callbacks.setExtensionName("In-Scope API Highlighter")
        
        # --- UI Initialization ---
        self._panel = JPanel(BorderLayout())
        
        # 1. Top Control Panel with multiple rows
        from javax.swing import BoxLayout, JTextField, Box
        
        control_wrapper = JPanel()
        control_wrapper.setLayout(BoxLayout(control_wrapper, BoxLayout.Y_AXIS))
        control_wrapper.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))
        
        # === Row 1: Import Buttons ===
        row1 = JPanel(FlowLayout(FlowLayout.LEFT))
        
        btn_load = JButton("Load Postman Collection", actionPerformed=self.load_collection)
        btn_load.setFont(Font("SansSerif", Font.BOLD, 12))

        btn_import_text = JButton("Import Text File", actionPerformed=self.load_text_file)
        btn_import_text.setFont(Font("SansSerif", Font.BOLD, 12))

        btn_reset = JButton("Reset All", actionPerformed=self.reset_state)
        btn_reset.setFont(Font("SansSerif", Font.BOLD, 12))
        btn_reset.setForeground(Color.RED)
        
        self._lbl_status = JLabel("Status: Waiting for input...")
        self._lbl_status.setForeground(Color.GRAY)
        
        row1.add(btn_load)
        row1.add(btn_import_text)
        row1.add(btn_reset)
        row1.add(Box.createHorizontalStrut(20))
        row1.add(self._lbl_status)
        
        # === Row 2: Options ===
        row2 = JPanel(FlowLayout(FlowLayout.LEFT))
        
        self._cb_unique = JCheckBox("Unique Highlight Only", actionPerformed=self.toggle_unique)
        self._cb_check_method = JCheckBox("Check Method", True, actionPerformed=self.toggle_check_method)
        
        color_label = JLabel("Highlight Color:")
        color_label.setFont(Font("SansSerif", Font.BOLD, 12))
        self._color_combo = JComboBox(list(HIGHLIGHT_COLORS.keys()))
        self._color_combo.setSelectedIndex(0)
        self._color_combo.addActionListener(self.change_color)
        
        row2.add(self._cb_unique)
        row2.add(self._cb_check_method)
        row2.add(Box.createHorizontalStrut(20))
        row2.add(color_label)
        row2.add(self._color_combo)
        
        # === Row 3: State File Path ===
        row3 = JPanel(FlowLayout(FlowLayout.LEFT))
        
        from config import STATE_FILE
        path_label = JLabel("State File:")
        path_label.setFont(Font("SansSerif", Font.BOLD, 12))
        
        self._state_path_field = JTextField(STATE_FILE, 40)
        self._state_path_field.setFont(Font("Monospaced", Font.PLAIN, 11))
        
        btn_browse = JButton("Browse...", actionPerformed=self.browse_state_path)
        btn_browse.setFont(Font("SansSerif", Font.PLAIN, 11))
        
        btn_save = JButton("Save State", actionPerformed=self.save_state)
        btn_save.setFont(Font("SansSerif", Font.BOLD, 12))
        btn_save.setForeground(Color.BLUE)
        
        btn_load_state = JButton("Load State", actionPerformed=self.load_state)
        btn_load_state.setFont(Font("SansSerif", Font.BOLD, 12))
        btn_load_state.setForeground(Color.BLUE)
        
        row3.add(path_label)
        row3.add(self._state_path_field)
        row3.add(btn_browse)
        row3.add(Box.createHorizontalStrut(10))
        row3.add(btn_save)
        row3.add(btn_load_state)
        
        # Add all rows to wrapper
        control_wrapper.add(row1)
        control_wrapper.add(row2)
        control_wrapper.add(row3)
        
        # 2. API Table (Center) - Editable table for user modifications
        self._table_model = DefaultTableModel(["Method", "Path"], 0)
        self._table = JTable(self._table_model)
        self._table.setFillsViewportHeight(True)
        self._table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self._table.getTableHeader().setFont(Font("SansSerif", Font.BOLD, 12))
        self._table.setRowHeight(20)
        
        # Add listener to sync table edits back to state
        self._table_model.addTableModelListener(TableEditListener(self))
        
        table_scroll = JScrollPane(self._table)
        table_scroll.setBorder(BorderFactory.createTitledBorder("Extracted APIs (Editable)"))
        
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
        
        self._panel.add(control_wrapper, BorderLayout.NORTH)
        self._panel.add(split_pane, BorderLayout.CENTER)
        
        # --- Registration ---
        callbacks.addSuiteTab(self)
        callbacks.registerHttpListener(self)
        
        self.log("Extension loaded successfully. Ready to import Postman collection.")
        self.debug_mode = True
        
        # Auto-load previous state if available
        self._try_auto_load()

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

    def toggle_check_method(self, event):
        state.is_check_method_enabled = self._cb_check_method.isSelected()
        self.log("Check Method: {}".format(state.is_check_method_enabled))

    def change_color(self, event):
        selected_name = self._color_combo.getSelectedItem()
        state.highlight_color = HIGHLIGHT_COLORS.get(selected_name, "green")
        self.log("Highlight Color changed to: {} ({})".format(selected_name, state.highlight_color))

    def browse_state_path(self, event):
        """Open file chooser to select custom state file path"""
        chooser = JFileChooser()
        chooser.setDialogTitle("Select State File Location")
        chooser.setSelectedFile(java.io.File(self._state_path_field.getText()))
        
        if chooser.showSaveDialog(self._panel) == JFileChooser.APPROVE_OPTION:
            selected_path = chooser.getSelectedFile().getPath()
            # Ensure .json extension
            if not selected_path.endswith(".json"):
                selected_path += ".json"
            self._state_path_field.setText(selected_path)
            self.log("State file path set to: " + selected_path)

    def _get_state_path(self):
        """Get the current state file path from the text field"""
        path = self._state_path_field.getText().strip()
        return path if path else None

    def save_state(self, event):
        """Save current state to file for persistence"""
        custom_path = self._get_state_path()
        success, msg = state.save_state(custom_path)
        if success:
            self.log("[SAVED] " + msg)
            self._lbl_status.setText("State Saved!")
            self._lbl_status.setForeground(Color.BLUE)
        else:
            self.log("[ERROR] " + msg)
            self._lbl_status.setText("Save Failed")
            self._lbl_status.setForeground(Color.RED)

    def load_state(self, event):
        """Load previously saved state from file"""
        custom_path = self._get_state_path()
        success, msg = state.load_state(custom_path)
        if success:
            self._restore_ui_from_state()
            self.log("[LOADED] " + msg)
        else:
            self.log("[INFO] " + msg)
            self._lbl_status.setText("No saved state found")
            self._lbl_status.setForeground(Color.GRAY)

    def _try_auto_load(self):
        """Auto-load previous state on extension startup"""
        custom_path = self._get_state_path()
        success, msg = state.load_state(custom_path)
        if success:
            self._restore_ui_from_state()
            self.log("[AUTO-LOAD] " + msg)
        else:
            self.log("[INFO] No previous state to restore.")

    def _restore_ui_from_state(self):
        """Restore UI components from loaded state"""
        # Restore checkboxes
        self._cb_unique.setSelected(state.is_unique_url_enabled)
        self._cb_check_method.setSelected(state.is_check_method_enabled)
        
        # Restore color dropdown
        for name, color in HIGHLIGHT_COLORS.items():
            if color == state.highlight_color:
                self._color_combo.setSelectedItem(name)
                break
        
        # Restore table - clear and repopulate
        self._table_model.setRowCount(0)
        for api in state.parsed_apis:
            self._table_model.addRow([api['method'], api['path']])
        
        # Update status
        total_apis = len(state.parsed_apis)
        seen_count = len(state.seen_apis)
        self._lbl_status.setText("Restored: {} APIs, {} seen".format(total_apis, seen_count))
        self._lbl_status.setForeground(Color(0, 100, 0))

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
            
            messageInfo.setHighlight(state.highlight_color)
            self.log("[MATCH] Highlighted ({}): {}".format(state.highlight_color, identifier))
        else:
            # Verbose debug for troubleshooting "Why isn't it highlighting?"
            # Only print if it looks like an API call to reduce noise? 
            # self.log("DEBUG: No Match for {} {}".format(method, burp_path))
            pass

    def check_match(self, method, burp_path):
        # Normalize Burp Path
        burp_clean = burp_path.rstrip('/')
        if not burp_clean: burp_clean = "/"
        
        # Get APIs to check - filter by method only if Check Method is enabled
        if state.is_check_method_enabled:
            apis_to_check = [api.get('path') for api in state.parsed_apis if api['method'].upper() == method.upper()]
        else:
            # Ignore method, match any endpoint
            apis_to_check = [api.get('path') for api in state.parsed_apis]
        
        # Flexible match (ignore trailing slash)
        for api_path in apis_to_check:
            norm_api = api_path.rstrip('/')
            if not norm_api: norm_api = "/"
            
            if burp_clean == norm_api:
                return True
                
        return False
