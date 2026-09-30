import sys
sys.path.insert(0, '.')
import tkinter as tk
from tkinter import scrolledtext, ttk
import tkinter.font as tkfont
import os

# Recreate the essential parts to create an app instance for testing
def create_test_app():
    # Import necessary functions from the module
    from user_productivity_tool import (
        discover_actions_for_gui, 
        discover_users_for_gui,
        _setup_fonts as module_setup_fonts,
        _apply_theme as module_apply_theme,
        _setup_layout as module_setup_layout
    )
    
    root = tk.Tk()
    root.withdraw()  # Hide the window
    
    # Create app instance manually (replicate UserProductivityApp.__init__)
    class TestApp:
        def __init__(self, root):
            self.tk = tk
            self.root = root
            self.root.title("User Productivity Tool")
            
            # Background task queue
            import queue
            import threading
            self._queue = queue
            self._task_queue = queue.Queue()
            self._bg_thread = None
            
            # Fonts
            self._setup_fonts = module_setup_fonts
            self._setup_fonts()
            
            # Palettes
            self.PALETTES = {
                "dark": {
                    "app": "#0f172a", "card": "#1e293b", "input": "#0f172a",
                    "border": "#334155", "text": "#f1f5f9", "text2": "#94a3b8",
                    "accent": "#22d3ee", "accent_text": "#0f172a", "accent_hover": "#67e8f9",
                    "select": "#164e63", "zebra": "#172033",
                },
                "light": {
                    "app": "#f1f5f9", "card": "#ffffff", "input": "#f1f5f9",
                    "border": "#cbd5e1", "text": "#0f172a", "text2": "#475569",
                    "accent": "#2563eb", "accent_text": "#ffffff", "accent_hover": "#1d4ed8",
                    "select": "#dbeafe", "zebra": "#f8fafc",
                }
            }
            
            self.current_theme = tk.StringVar(value="light")
            self.csv_path_var = tk.StringVar()
            self.threshold_var = tk.StringVar(value="5")
            self.status_var = tk.StringVar(value="Select a user action log CSV to begin.")
            self.current_markdown = ""
            self.current_report = None
            self.action_rows = []
            self.user_rows = []
            self.ranking_sort_var = tk.StringVar(value="Score")
            self.ranking_desc_var = tk.BooleanVar(value=True)
            
            # Widget references
            self.weights_canvas = None
            self.users_canvas = None
            self.result_text = None
            self.ranking_tree = None
            self.details_tree = None
            self.info_text_widgets = []
            
            # Theme and layout
            self._apply_theme = module_apply_theme
            self._apply_theme()
            self._setup_layout = module_setup_layout
            self._setup_layout()
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(2, weight=1)
            self.root.minsize(1000, 700)
            self.root.geometry("1200x800")
            
            # Initialize with empty states
            self.set_action_rows(*discover_actions_for_gui())
            self.set_user_rows([])
            
            # Start queue polling
            self._poll_task_queue()
            
            # Copy the actual methods
            self.set_action_rows = self.__class__.set_action_rows
            self.set_user_rows = self.__class__.set_user_rows
            
        def _setup_fonts(self):
            from user_productivity_tool import _setup_fonts as module_setup_fonts
            module_setup_fonts(self)
            
        def _apply_theme(self):
            from user_productivity_tool import _apply_theme as module_apply_theme
            module_apply_theme(self)
            
        def _setup_layout(self):
            from user_productivity_tool import _setup_layout as module_setup_layout
            module_setup_layout(self)
            
        def _poll_task_queue(self):
            # For testing, we don't need to start the actual polling
            # Just create a stub that does nothing
            pass
    
    app = TestApp(root)
    return app, root

# Test the app creation and method calls
print("Creating test app...")
app, root = create_test_app()
print("App created successfully")

# Get CSV data
path = "sample.csv"
actions, weights = discover_actions_for_gui(path)
users = discover_users_for_gui(path)
print(f"CSV data: {len(actions)} actions, {len(users)} users")

# Test set_action_rows
try:
    print("Testing set_action_rows...")
    app.set_action_rows(actions, weights)
    print("SUCCESS: set_action_rows worked")
except Exception as e:
    print(f"ERROR in set_action_rows: {e}")
    import traceback
    traceback.print_exc()

# Test set_user_rows
try:
    print("Testing set_user_rows...")
    app.set_user_rows(users)
    print("SUCCESS: set_user_rows worked")
except Exception as e:
    print(f"ERROR in set_user_rows: {e}")
    import traceback
    traceback.print_exc()

root.destroy()
print("Test completed")