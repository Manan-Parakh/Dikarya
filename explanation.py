# PyQt5 is a comprehensive set of Python bindings for Qt v5, a powerful cross-platform GUI (Graphical User Interface) framework. 
# It allows Python developers to create desktop applications with advanced user interfaces using the Qt framework's widgets, tools, 
# and facilities. PyQt5 is widely used for building professional-grade applications, prototypes, and tools that require a user interface.

# Yes, I can read the code in manan.py. It contains imports, PyQt5 setup, and a class for mocking data logging. It sets up experiment logging, UI theming, and custom axis handling for real-time dashboard purposes, mostly using PyQt5 and pyqtgraph, and organizes logging in a file structure. The main custom window is FullScreenWindow, which handles experiment state, logging, and layout.


"""
Explanation of all classes and functions defined in manan.py:

Class: MockData
---------------
This class is a mock or stub for handling experiment data and file logging.
It is meant for prototyping, simulation, or testing before integrating real data sources.

- __init__(self)
    - Initializes the MockData instance.
    - Sets up properties:
        - self.history: list, stores history of experiment records.
        - self.current_exp_file: unused here, intended to store path of current experiment's log file.
        - self.current_exp_number: tracks the current experiment number.
        - self.log_dir: directory for storing log files, default is "Logs".
        - self.check_file: path for storing/checking last experiment metadata ("today_experment_check.txt").
    - If log directory does not exist, creates it to ensure file saving works.

- save_last_experiment(self, exp_num)
    - Stores the last completed experiment number *and* the date to today_experment_check.txt.
    - Uses QDate from PyQt5 to get the current date as a string.
    - Opens the check file in write mode and writes in the format: "{current_date_str},{exp_num}"
    - Catches and prints exceptions for file write errors.

- load_last_experiment(self)
    - Loads last experiment number from the check file *if the date matches today's date*.
    - Uses QDate to get current date.
    - Reads the file, splits at comma. If date matches and the format is right, returns the stored last experiment number as int.
    - If file is missing, date is different, or read/parse error, returns 0.

- data_send(self, is_running, exp_num)
    - Simulates a new data record for an experiment.
    - By default, T1, T2 (temperatures) and W1, W2 (weights) start with constant values.
    - If `is_running` and there is previously sent data (self.history), generates new W1, W2 using random small decrements (random.uniform), making weights appear to reduce slightly on each call.
    - This function is used to *simulate live experimental data* for the GUI and plotting systems – standing in for a real sensor/data acquirer.

Other Structural Notes:
-----------------------
- There are multiple PyQt5 imports for widgets, layouts, and graphical components, including pyqtgraph.
- The module imports and sets up objects/classes necessary for building a PyQt5 application window that handles experiment visualization and logging.
- In the rest of manan.py (not fully shown), you would expect more classes for UI (`FullScreenWindow` is referred to in comments) and more hooks for real-time dashboard/plot updating, experiment control, and cross-window communication via signals/slots.

Summary:
--------
MockData acts as a self-contained simulation for experiment data, file IO for daily progress, and forms the backend for prototyping before integration with actual experiment hardware or a database.
"""

