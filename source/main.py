# In your main PyQt file
# ... other imports
from PyQt5.QtGui import QPixmap
import pyqtgraph as pg
import sys
import os
import re
from pathlib import Path
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QLineEdit, QPushButton,
    QMessageBox, QDateEdit, QSpinBox, QSizePolicy, QLayout
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QDate, QTime
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QCalendarWidget
from PyQt5.QtGui import QPixmap
import pyqtgraph as pg

# This code ensures that the project's root directory is in the Python import search path (sys.path),
# so that modules within the project can be imported properly, especially those not in the same directory as this file.


def _resolve_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


project_root = _resolve_project_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from helper.paths import get_project_root
from helper.data_insert import insert_experiment_record

project_root = get_project_root()
import threading

# --- Mocking the 'data' module for file I/O and data simulation ---
class MockData:
    def __init__(self):
        self.history = []
        self.current_exp_file = None
        self.current_exp_number = 0
        self.log_dir = os.path.join(project_root, "Logs")
        self.check_file = os.path.join(self.log_dir, "last_exp.txt")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    # --- NEW: File utility to save the last experiment number ---
    def save_last_experiment(self, exp_num):
        """Saves the last completed experiment number and date to a file."""
        current_date_str = QDate.currentDate().toString("yyyy-MM-dd")
        try:
            with open(self.check_file, 'w') as f:
                f.write(f"{current_date_str},{exp_num}")
        except Exception as e:
            print(f"Error saving check file: {e}")

    # --- NEW: File utility to load the last experiment number ---
    def load_last_experiment(self):
        """Loads the last experiment number from the file, checking the date."""
        current_date_str = QDate.currentDate().toString("yyyy-MM-dd")
        if os.path.exists(self.check_file):
            try:
                with open(self.check_file, 'r') as f:
                    content = f.read().strip().split(',')
                    if len(content) == 2:
                        file_date, exp_num_str = content
                        if file_date == current_date_str:
                            return int(exp_num_str)
            except Exception as e:
                print(f"Error reading or parsing check file: {e}")
        return 0 # Return 0 if file not found, date mismatch, or error

    # Mock data generation (unchanged)
    def data_send(self, is_running, exp_num):
        T1, T2 = 29.8, 27.3
        W1, W2 = 30.15, 15.18
        
        if is_running and self.history:
            import random
            last_w1, last_w2 = self.history[-1][1], self.history[-1][2]
            W1 = last_w1 - random.uniform(0.001, 0.005)
            W2 = last_w2 - random.uniform(0.0005, 0.002)
            
            if self.current_exp_file:
                timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
                data_line = f"{timestamp},{T1:.2f},{T2:.2f},{W1:.4f},{W2:.4f}\n"
                self.current_exp_file.write(data_line)
        
        if not self.history:
             W1, W2 = 30.15, 15.18

        self.history.append((QDateTime.currentDateTime().toMSecsSinceEpoch(), W1, W2))
        return T1, T2, W1, W2, exp_num, 0, 0, self.history

    def start_new_experiment(self, exp_num):
        self.current_exp_number = exp_num
        self.history = []
        
        if self.current_exp_file:
            self.current_exp_file.close()
        
        file_name = QDate.currentDate().toString("yyyy-MM-dd") + f"_EXP_{exp_num}.txt"
        full_path = os.path.join(self.log_dir, file_name)
        
        try:
            # Use 'w' mode (write)
            self.current_exp_file = open(full_path, 'w')
            self.current_exp_file.write("Timestamp,Temp1(C),Temp2(C),Weight1(kg),Weight2(kg)\n")
            print(f"✅ Data logging started to: {full_path}")
        except Exception as e:
            print(f"❌ ERROR starting file logging: {e}")
            self.current_exp_file = None

    def stop_experiment(self):
        if self.current_exp_file:
            self.current_exp_file.close()
            self.current_exp_file = None
            print("🛑 Data logging file closed.")
            # 🔑 CRITICAL: Save the last experiment number upon STOP
            self.save_last_experiment(self.current_exp_number)

data = MockData()
# --- End of Mocking ---


# --- PyQtGraph Configuration ---
pg.setConfigOption('background', "#F3EA9D")        
pg.setConfigOption('foreground', 'k')             


# Custom Axis Item (omitted for brevity)
class TimeAxisItem(pg.AxisItem):
    """Custom AxisItem to format axis ticks based on the selected time unit."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_unit = 'Seconds'  

    def set_time_unit(self, unit):
        self.time_unit = unit
        self.setLabel(text=f'Time ({unit})')

    def tickText(self, values, scale, spacing):
        strings = []
        for v in values:
            if self.time_unit == 'Seconds':
                strings.append(f'{int(v)}') 
            elif self.time_unit == 'Minutes':
                strings.append(f'{int(v)}') 
            elif self.time_unit == 'Hours':
                strings.append(f'{round(v, 2)}') 
            else:
                strings.append(super().tickText([v], scale, spacing)[0])
        return strings


class FullScreenWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BPCL Real-Time Dashboard")
        self._init_popup_window()
        self._centered_once = False

        # --- Experiment State Variables ---
        self.is_running = False
        self.experiment_number = 0  
        self.logging_interval_ms = 2000
        self.data_interval_ms = 2000 
        self.last_reset_date = QDate.currentDate()
        self.experiment_start_ms = 0
        self.displaying_history = False

        # --- Time Scale Configuration ---
        self.time_scales = {
            "Seconds":  {'range': 60,  'step': 2, 'unit_label': 'seconds'}, 
            "Minutes":  {'range': 60,  'step': 2, 'unit_label': 'minutes'}, 
            "Hours":    {'range': 24,  'step': 2, 'unit_label': 'hours'},   
        }
        self.current_time_scale = 'Seconds'  
        self.max_history_points = self._calculate_max_points(self.current_time_scale)

        # --- Theme/Layout Setup (Omitted for brevity) ---
        self.bg_color = "#FFFFFF"            
        self.fg_color = "#1E3A8A"            
        self.accent_color2 = "#1288E9"        
        self.border_style = f"2px solid {self.fg_color}"
        self.button_style = f"""
            QPushButton {{background-color: {self.fg_color}; color: white; border-radius: 5px; padding: 5px 10px; font-weight: bold;}}
            QPushButton:hover {{background-color: {self.accent_color2};}}
        """
        self.setStyleSheet(f"background-color: {self.bg_color};")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_grid = QGridLayout(central_widget)
        self.main_grid.setSizeConstraint(QLayout.SetMinimumSize)
        # ... (Layout configuration) ...
        # The following lines configure the layout proportions of the main_grid using "stretches" and "spacing".
        # Column stretches control how extra horizontal space is distributed among columns (higher number = more space).
        # Row stretches control how extra vertical space is distributed among rows (higher number = more space).
        # Setting spacing determines the space (in pixels) between widgets in the grid.

        # Columns: left data column (0), right graph column (1), optional spacer (2)
        self.main_grid.setColumnStretch(0, 3)     # Data/control stack (narrower)
        self.main_grid.setColumnStretch(1, 8)     # Graph column (dominant)
        self.main_grid.setColumnStretch(2, 0)     # Optional spacer (unused)

        # Rows: header (0), data label (1), control panel (2), chart (3), data retrieval (4), footer (5)
        self.main_grid.setRowStretch(0, 10)   # Header/bar
        self.main_grid.setRowStretch(1, 30)   # Data labels
        self.main_grid.setRowStretch(2, 10)   # Control panel
        # self.main_grid.setRowStretch(3, 60)   # Main chart/graph area
        self.main_grid.setSpacing(50)         # Space between all widgets in the grid
        self.main_grid.setRowStretch(4, 10)   # Data retrieval panel
        self.main_grid.setRowStretch(5, 0)    # Footer (optionally unused/minimal space)

        # --- UI Component Initialization and Placement (Omitted for brevity) ---
        self._setup_header_area()
        self.main_grid.addWidget(self.header_widget, 0, 0, 1, 2)
        self.data_label_widget = self._create_data_display_widget()
        self.main_grid.addWidget(self.data_label_widget, 1, 0, 1, 1)
        self.control_panel_widget = self._setup_control_panel()
        self.main_grid.addWidget(self.control_panel_widget, 2, 0, 1, 1)
        self.chart_widget, self.w1_curve, self.w2_curve = self._create_line_chart_widget()
        self.main_grid.addWidget(self.chart_widget, 1, 1, 4, 1)
        self._setup_data_retrieval_panel()
        self.main_grid.addWidget(self.data_retrieval_widget, 4, 0, 1, 1)
        self._setup_footer_area()
        self.main_grid.addWidget(self.footer_container, 5, 0, 1, 1)

        # --- Timers (Omitted for brevity) ---
        self.datetime_timer = QTimer(self); self.datetime_timer.timeout.connect(self.update_datetime); self.datetime_timer.start(1000)
        self.update_datetime()
        self.data_timer = QTimer(self); self.data_timer.timeout.connect(self.update_data); self.data_timer.setInterval(self.data_interval_ms); self.data_timer.start()
        self.daily_reset_timer = QTimer(self); self.daily_reset_timer.timeout.connect(self._check_daily_reset); self.daily_reset_timer.start(30000)

        # 🔑 CRITICAL: Load the last experiment number from the check file on startup
        self._load_last_experiment_number()
        
        # Initial check to set the experiment number display
        self.exp_label.setText(f"EXPERIMENT : {self.experiment_number}")
        QTimer.singleShot(0, self._lock_to_content_minimum_size)


    def _init_popup_window(self):
        """Start maximized while keeping the frame resizable."""
        self.setMinimumSize(960, 600)
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            self.setGeometry(available)
        else:
            self.resize(1280, 800)
            self._center_on_screen()

    def _center_on_screen(self):
        """Use the frame geometry to account for window decorations."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._centered_once:
            self._center_on_screen()
            self._centered_once = True

    def _lock_to_content_minimum_size(self):
        """Prevent shrinking below the size required by the layout contents."""
        min_size = self.minimumSizeHint()
        self.setMinimumSize(min_size)
    # ================== UPDATED EXPERIMENT LOADING LOGIC ==================

    def _load_last_experiment_number(self):
        """
        Loads the last experiment number from the check file. 
        If the file date is old or file is missing, it resets to 0.
        """
        max_exp_num = data.load_last_experiment()
            
        # Set the experiment number to the last completed one.
        # The next START EXPERIMENT click will increment it.
        self.experiment_number = max_exp_num
        if max_exp_num > 0:
            print(f"Loaded max experiment number for today from check file: {max_exp_num}. Next experiment will be: {self.experiment_number + 1}")
        else:
             # Fallback to file scanning if check file is missing/old/error (optional, but robust)
             self.experiment_number = self._scan_log_directory()
             print(f"Check file failed. Scanned logs and found max: {self.experiment_number}. Next experiment will be: {self.experiment_number + 1}")

    def _scan_log_directory(self):
        """Helper function to scan files if the check file is unavailable/old."""
        log_dir = data.log_dir
        current_date_str = QDate.currentDate().toString("yyyy-MM-dd")
        pattern = re.compile(rf"^{re.escape(current_date_str)}_EXP_(\d+)\.txt$", re.IGNORECASE)
        max_exp_num = 0
        try:
            for filename in os.listdir(log_dir):
                match = pattern.match(filename)
                if match:
                    exp_num = int(match.group(1))
                    if exp_num > max_exp_num:
                        max_exp_num = exp_num
        except FileNotFoundError:
            pass
        return max_exp_num
        
    # ================== DAILY RESET & EXPERIMENT LOGIC ==================

    def _check_daily_reset(self, startup=False):
        """
        Checks if it's midnight and resets the experiment counter by reloading 
        the last experiment number for the new day.
        """
        current_date = QDate.currentDate()
        current_time = QTime.currentTime()
        
        if (current_date > self.last_reset_date) and (current_time.hour() == 0 and current_time.minute() < 1) and not startup:
            
            if self.is_running:
                self._stop_experiment(silent=True)
            
            self.last_reset_date = current_date
            
            # 🔑 CRITICAL: Reload experiment number for the new day
            self._load_last_experiment_number()
            
            self.exp_label.setText(f"EXPERIMENT : {self.experiment_number}")
            print(f"🕛 Daily Reset triggered. Next experiment number loaded: {self.experiment_number + 1}.")


    def _start_experiment(self):
        """Starts the logging session."""
        if self.is_running:
            return
        self._exit_history_mode()

        # --- Read user interval and unit ---
        try:
            interval_value = float(self.interval_input.text())
            if interval_value <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a positive number for the interval.")
            return

        unit = self.interval_unit_combo.currentText()
        if unit == "Seconds":
            new_interval_ms = int(interval_value * 1000)
        elif unit == "Minutes":
            new_interval_ms = int(interval_value * 60 * 1000)
        else:
            new_interval_ms = 2000  # fallback

        # --- Continue existing logic ---
        self.experiment_number += 1
        self.experiment_start_ms = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.exp_label.setText(f"Experiment : {self.experiment_number}")

        self.is_running = True
        self.logging_interval_ms = new_interval_ms
        self.data_interval_ms = new_interval_ms
        self.data_timer.setInterval(self.data_interval_ms)
        self.data_timer.start()

        data.start_new_experiment(self.experiment_number)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.interval_input.setEnabled(True)
        self.interval_unit_combo.setEnabled(True)

        self.max_history_points = self._calculate_max_points(self.current_time_scale)
        print(f"--- Experiment EXP_{self.experiment_number} STARTED (Interval: {new_interval_ms}ms, Unit: {unit}) ---")




    def _stop_experiment(self, silent=False):
        """Stops the logging session."""
        if not self.is_running:
            return
        self._exit_history_mode()

        # 1. Update State and Timer
        self.is_running = False
        self.data_timer.stop()
        
        # 2. Stop File I/O Logic (This calls data.save_last_experiment internally)
        data.stop_experiment()

        # 3. Update UI (Omitted for brevity)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_input.setEnabled(True)
        
        if not silent:
            print(f"--- Experiment EXP_{self.experiment_number} STOPPED ---")

    # ================== (Other methods remain unchanged) ==================

    def _calculate_max_points(self, scale_key):
        data_interval_s = self.data_interval_ms / 1000 
        scale_data = self.time_scales[scale_key]
        range_value = scale_data['range']
        unit_label = scale_data['unit_label']
        if unit_label == 'seconds':
            range_s = range_value
        elif unit_label == 'minutes':
            range_s = range_value * 60
        elif unit_label == 'hours':
            range_s = range_value * 60 * 60
        else:
            return 30 
        return int(range_s / data_interval_s) + 1
        
    def _add_time_scale_selector_inner(self):
        widget = QWidget()
        h_layout = QHBoxLayout(widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)
        label = QLabel("Graph Time Scale:")
        label.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold))
        label.setStyleSheet(f"color: {self.fg_color};")
        h_layout.addWidget(label)
        self.time_scale_combo = QComboBox()
        self.time_scale_combo.addItems(self.time_scales.keys())
        self.time_scale_combo.setCurrentText(self.current_time_scale)
        self.time_scale_combo.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold))
        self.time_scale_combo.setMinimumWidth(140)
        self.time_scale_combo.setMinimumHeight(40)
        self.time_scale_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.time_scale_combo.setStyleSheet("""
            QComboBox {border: 2px solid #1E3A8A; border-radius: 8px; padding: 5px 12px; background-color: #E3F2FD; color: #1E3A8A; font-weight: bold;}
            QComboBox::down-arrow {content: "▼"; font-size: 10px; color: black; width: 10px; height: 9px; padding-right: 5px;}
            QComboBox QAbstractItemView {background-color: #FFFFFF; selection-background-color: #90CAF9; color: #1E3A8A;}
        """)
        self.time_scale_combo.currentIndexChanged.connect(self._handle_scale_change)
        h_layout.addWidget(self.time_scale_combo)
        return widget


    def _handle_scale_change(self, index):
        new_scale = self.time_scale_combo.currentText()
        if new_scale == self.current_time_scale:
            return
        self.current_time_scale = new_scale
        scale_data = self.time_scales[new_scale]
        self.max_history_points = self._calculate_max_points(new_scale)
        self.plot_widget.setXRange(0, scale_data['range'], padding=0.05)
        axis_label = f"Time ({scale_data['unit_label'].capitalize()})"
        self.plot_widget.getAxis("bottom").setLabel(text=axis_label)
        self.x_axis.set_time_unit(scale_data['unit_label'].capitalize())
        self.update_data()

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _set_measure_label(self, label, prefix, value, unit, precision=2):
        numeric_value = self._safe_float(value)
        if numeric_value is None:
            label.setText(f"{prefix} : -- {unit}".strip())
        else:
            formatted = f"{numeric_value:.{precision}f}"
            label.setText(f"{prefix} : {formatted} {unit}".strip())

    def _enter_history_mode(self):
        self.displaying_history = True

    def _exit_history_mode(self):
        if self.displaying_history:
            self.displaying_history = False

    def _prepare_dataframe_for_display(self, df):
        if df.empty:
            return df
        clean_df = df.copy()
        clean_df["date"] = clean_df["date"].astype(str)
        clean_df["time"] = clean_df["time"].astype(str)
        clean_df["timestamp"] = pd.to_datetime(
            clean_df["date"] + " " + clean_df["time"], errors="coerce"
        )
        clean_df = clean_df.dropna(subset=["timestamp"])
        numeric_cols = [
            "temp_1",
            "temp_2",
            "weight_1",
            "weight_2",
            "difference",
            "room_temp",
        ]
        for col in numeric_cols:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
        clean_df.sort_values("timestamp", inplace=True)
        clean_df.reset_index(drop=True, inplace=True)
        return clean_df

    def _apply_historical_dataset(self, df):
        if df.empty:
            self._clear_plot_items()
            return
        self._enter_history_mode()

        latest = df.iloc[-1]
        experiment_label = latest.get("experiment", "N/A")
        self.exp_label.setText(f"EXPERIMENT : {experiment_label}")
        self._set_measure_label(self.t1_label, "TEMP -1", latest.get("temp_1"), "C")
        self._set_measure_label(self.t2_label, "TEMP -2", latest.get("temp_2"), "C")
        self._set_measure_label(self.w1_label, "WEIGHT -1", latest.get("weight_1"), "kg", precision=4)
        self._set_measure_label(self.w2_label, "WEIGHT -2", latest.get("weight_2"), "kg", precision=4)
        self._set_measure_label(self.rt1_label, "ROOM TEMP", latest.get("room_temp"), "C")

        diff_value = latest.get("difference")
        if pd.isna(diff_value):
            w1 = self._safe_float(latest.get("weight_1"))
            w2 = self._safe_float(latest.get("weight_2"))
            diff_value = (w1 - w2) if (w1 is not None and w2 is not None) else None
        self._set_measure_label(self.w_diff_label, "DIFF (W1-W2)", diff_value, "kg", precision=4)

        self._plot_dataframe(df)

    def _plot_dataframe(self, df):
        if df.empty:
            self._clear_plot_items()
            return

        df_to_plot = df.tail(self.max_history_points).copy()
        timestamps = df_to_plot["timestamp"]
        base_ts = timestamps.iloc[0]
        seconds = (timestamps - base_ts).dt.total_seconds()
        scale_unit = self.time_scales[self.current_time_scale]["unit_label"]
        if scale_unit == "minutes":
            x_data = (seconds / 60).tolist()
        elif scale_unit == "hours":
            x_data = (seconds / 3600).tolist()
        else:
            x_data = seconds.tolist()

        w1_values = df_to_plot["weight_1"].ffill().bfill().fillna(0.0).tolist()
        w2_values = df_to_plot["weight_2"].ffill().bfill().fillna(0.0).tolist()
        self.w1_curve.setData(x_data, w1_values)
        self.w2_curve.setData(x_data, w2_values)
        self._update_axis_ranges(x_data, w1_values, w2_values)


    def _setup_control_panel(self):
        widget = QWidget()
        h_layout = QHBoxLayout(widget)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(15)

        # --- Time scale (graph) selector ---
        time_scale_widget = self._add_time_scale_selector_inner()
        h_layout.addWidget(time_scale_widget)
        h_layout.addStretch()

        font_label = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold)

        # --- Logging interval label ---
        interval_label = QLabel("Log Interval:")
        interval_label.setFont(font_label)
        interval_label.setStyleSheet(f"color: {self.fg_color};")
        h_layout.addWidget(interval_label)

        # --- NEW: Unit dropdown (Seconds / Minutes) ---
        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["Seconds", "Minutes"])
        self.interval_unit_combo.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Bold))
        self.interval_unit_combo.setMinimumWidth(130)
        self.interval_unit_combo.setMinimumHeight(40)
        self.interval_unit_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.interval_unit_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #1E3A8A; border-radius: 8px;
                padding: 5px 12px; background-color: #E3F2FD;
                color: #1E3A8A; font-weight: bold;
            }
            QComboBox::down-arrow {
                content: "▼"; font-size: 10px; color: black;
                width: 10px; height: 9px; padding-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                selection-background-color: #90CAF9;
                color: #1E3A8A;
            }
        """)
        h_layout.addWidget(self.interval_unit_combo)

        # --- NEW: Value input field ---
        self.interval_input = QLineEdit("2")
        self.interval_input.setFont(QtGui.QFont("Segoe UI", 12))
        self.interval_input.setMinimumWidth(120)
        self.interval_input.setMinimumHeight(40)
        self.interval_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.interval_input.setAlignment(Qt.AlignCenter)
        self.interval_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #1E3A8A; border-radius: 8px;
                background-color: #E3F2FD; color: #1E3A8A;
                font-weight: bold;
            }
        """)
        h_layout.addWidget(self.interval_input)

        # --- Start/Stop buttons ---
        button_font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)

        self.start_button = QPushButton("START EXPERIMENT")
        self.start_button.setFont(button_font)
        self.start_button.setMinimumHeight(45)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_button.setStyleSheet("""
            QPushButton {background-color: #2E7D32; color: white; border-radius: 10px; padding: 5px 15px;}
            QPushButton:hover {background-color: #43A047;}
        """)
        self.start_button.clicked.connect(self._start_experiment)
        h_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("STOP EXPERIMENT")
        self.stop_button.setFont(button_font)
        self.stop_button.setMinimumHeight(45)
        self.stop_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.stop_button.setStyleSheet("""
            QPushButton {background-color: #D32F2F; color: white; border-radius: 10px; padding: 5px 15px;}
            QPushButton:hover {background-color: #E53935;}
        """)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_experiment)
        h_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setFont(button_font)
        self.clear_button.setMinimumHeight(45)
        self.clear_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clear_button.setStyleSheet("""
            QPushButton {background-color: #546E7A; color: white; border-radius: 10px; padding: 5px 15px;}
            QPushButton:hover {background-color: #78909C;}
        """)
        self.clear_button.clicked.connect(self._clear_dashboard)
        h_layout.addWidget(self.clear_button)

        return widget


    def _setup_header_area(self):
        self.header_widget = QWidget()
        h_layout = QHBoxLayout(self.header_widget)
        h_layout.setContentsMargins(10, 10, 10, 0)
        h_layout.setSpacing(20)
        self.left_logo = QLabel()
        self.left_logo.setScaledContents(True)
        try:
             left_pixmap = QPixmap("Bharat_Petroleum_logo_PNG1.png")
             self.left_logo.setPixmap(left_pixmap)
        except Exception:
             self.left_logo.setText("BPCL Logo")
        self.left_logo.setMinimumSize(80, 60)
        self.left_logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        h_layout.addWidget(self.left_logo, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        h_layout.addStretch()
        self.main_label = QLabel("Bharat Petroleum Corporation Limited")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setStyleSheet(f"color: {self.fg_color}; font-weight: bold; font-size: 36px; font-family: 'Segoe UI', sans-serif; letter-spacing: 1px;")
        h_layout.addWidget(self.main_label, alignment=Qt.AlignCenter)
        h_layout.addStretch()
        self.right_logo = QLabel()
        self.right_logo.setScaledContents(True)
        try:
            right_pixmap = QPixmap(r"C:\Users\UNITY\Desktop\LPG\right image.png")
            self.right_logo.setPixmap(right_pixmap)
        except Exception:
            self.right_logo.setText("LPG Image")
        self.right_logo.setMinimumSize(60, 60)
        self.right_logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        h_layout.addWidget(self.right_logo, alignment=Qt.AlignRight | Qt.AlignVCenter)

    def _create_data_display_widget(self):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: #FFFFFF; border: {self.border_style}; border-radius: 12px;")
        vbox = QVBoxLayout(widget)
        vbox.setSpacing(25)
        vbox.setContentsMargins(20, 20, 20, 20)
        vbox.setAlignment(Qt.AlignTop)
        self.exp_label = QLabel()
        self.t1_label = QLabel()
        self.t2_label = QLabel()
        self.w1_label = QLabel()
        self.w2_label = QLabel()
        self.rt1_label = QLabel()
        self.w_diff_label = QLabel()
        label_style = "color: #0D1B2A; font-size: 22px; font-weight: bold; padding: 8px 16px; background-color: #5D8AA8; border-radius: 10px;"
        title_style = "color: #1E3A8A; font-weight: bold; font-size: 30px; padding: 10px 16px; background-color: #FFD700; border-radius: 12px;"
        exp_style = "color: #FFFFFF; font-weight: bold; font-size: 34px; padding: 10px 20px; background-color: #2B65EC; border-radius: 15px;"
        diff_style = "color: #0D1B2A; font-weight: bold; font-size: 22px; padding: 8px 16px; background-color: #5D8AA8; border-radius: 10px;"
        self.exp_label.setAlignment(Qt.AlignCenter)
        self.exp_label.setStyleSheet(exp_style)
        vbox.addWidget(self.exp_label)
        for text in ("LPG PLUS (+)", "LPG"):
            title_lbl = QLabel(text)
            title_lbl.setAlignment(Qt.AlignCenter)
            title_lbl.setStyleSheet(title_style)
            vbox.addWidget(title_lbl)
        for lbl in (self.t1_label, self.t2_label, self.w1_label, self.w2_label):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(label_style)
            vbox.addWidget(lbl)
        self.rt1_label.setAlignment(Qt.AlignCenter)
        self.rt1_label.setStyleSheet(label_style)
        vbox.addWidget(self.rt1_label)
        self.w_diff_label.setAlignment(Qt.AlignCenter)
        self.w_diff_label.setStyleSheet(diff_style)
        vbox.addWidget(self.w_diff_label)
        return widget

    def _create_line_chart_widget(self):
        self.x_axis = TimeAxisItem(orientation="bottom")
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": self.x_axis})
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(330)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setBackground("#FFFFFF")
        self.plot_widget.getPlotItem().setContentsMargins(10, 10, 10, 10)
        self.plot_widget.setStyleSheet("border: 1px solid #E2E8F0; border-radius: 8px;")

        self.plot_widget.setTitle(
            "<span style='color:#0F172A;font-size:16pt;font-weight:600;'>Weight Trend (W1 vs W2)</span>"
        )

        self.plot_widget.addLegend(offset=(10, 10), labelTextColor="#0F172A")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        scale_data = self.time_scales[self.current_time_scale]
        self.plot_widget.setXRange(0, scale_data["range"], padding=0)
        self.plot_widget.setYRange(14, 32, padding=0)

        label_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Medium)
        axis_pen = pg.mkPen("#94A3B8", width=1)
        for axis in ("left", "bottom"):
            axis_item = self.plot_widget.getAxis(axis)
            axis_label = (
                "Weight (kg)"
                if axis == "left"
                else f"Time ({scale_data['unit_label'].capitalize()})"
            )
            axis_item.setLabel(text=axis_label, font=label_font)
            axis_item.setPen(axis_pen)
            axis_item.setTextPen(pg.mkPen("#475569"))

        self.x_axis.set_time_unit(scale_data["unit_label"].capitalize())

        w1_pen = pg.mkPen(color="#2563EB", width=0.8, cosmetic=True)
        w2_pen = pg.mkPen(color="#F97316", width=0.8, cosmetic=True)

        w1_curve = self.plot_widget.plot(name="Weight 1 (W1)", pen=w1_pen, antialias=True)
        w2_curve = self.plot_widget.plot(name="Weight 2 (W2)", pen=w2_pen, antialias=True)
        for curve in (w1_curve, w2_curve):
            curve.setClipToView(True)

        return self.plot_widget, w1_curve, w2_curve

    # # ... (inside the FullScreenWindow class) ...

    def update_data(self):
        """Main data update handler — updates UI, plots, and inserts into DB."""
        if self.displaying_history and not self.is_running:
            return
        T1, T2, W1, W2, exp_num, W4, W5, history = data.data_send(self.is_running, self.experiment_number)

        # ====== 🖥️ UI LABEL UPDATES ======
        self.t1_label.setText(f"TEMP -1 : {T1:.2f} °C")
        self.t2_label.setText(f"TEMP -2 : {T2:.2f} °C")
        self.w1_label.setText(f"WEIGHT -1 : {W1:.4f} kg")
        self.w2_label.setText(f"WEIGHT -2 : {W2:.4f} kg")
        self.rt1_label.setText(f"ROOM TEMP : {W4:.2f} °C")

        # Calculate difference
        weight_difference = W1 - W2
        self.w_diff_label.setText(f"DIFF (W1-W2) : {weight_difference:.4f} kg")

        # ====== 🧩 DATABASE INSERTION ======
        if self.is_running:
            record = {
                'date': QDate.currentDate().toString("yyyy-MM-dd"),
                'time': QTime.currentTime().toString("hh:mm:ss"),
                'experiment': f'EXP_{self.experiment_number}',
                'temp_1': f'{T1:.2f}',
                'temp_2': f'{T2:.2f}',
                'weight_1': f'{W1:.4f}',
                'weight_2': f'{W2:.4f}',
                'difference': f'{weight_difference:.4f}',
                'room_temp': f'{W4:.2f}'
            }

            # ✅ Run DB insertion in background thread (no GUI lag)
            threading.Thread(target=insert_experiment_record, args=(record,), daemon=True).start()

        # ====== 📈 GRAPH PLOTTING ======
        if not self.is_running or not history:
            self._clear_plot_items()
            return

        # Limit data to max history points
        history_to_plot = history[-self.max_history_points:]
        timestamps_ms, w1_values, w2_values = zip(*history_to_plot)

        # Time scale calculations
        start_ref_ms = self.experiment_start_ms
        time_diff_ms = [t_ms - start_ref_ms for t_ms in timestamps_ms]
        scale_unit = self.time_scales[self.current_time_scale]['unit_label']

        if scale_unit == 'seconds':
            x_data = [t / 1000 for t in time_diff_ms]
        elif scale_unit == 'minutes':
            x_data = [t / 60000 for t in time_diff_ms]
        elif scale_unit == 'hours':
            x_data = [t / 3600000 for t in time_diff_ms]
        else:
            x_data = [t / 1000 for t in time_diff_ms]

        # Update curves and focus markers
        self.w1_curve.setData(x_data, w1_values)
        self.w2_curve.setData(x_data, w2_values)
        self._update_focus_points(x_data, w1_values, w2_values)
        self._update_axis_ranges(x_data, w1_values, w2_values)
        self._update_axis_ranges(x_data, w1_values, w2_values)

    def _update_axis_ranges(self, x_data, w1_values, w2_values):
        if not x_data:
            return
        latest_x = x_data[-1]
        window = self.time_scales[self.current_time_scale]["range"]
        if latest_x > window:
            start = latest_x - window
            end = latest_x
        else:
            start = 0
            end = window
        self.plot_widget.setXRange(start, end, padding=0)

        combined = list(w1_values) + list(w2_values)
        ymin = min(combined)
        ymax = max(combined)
        span = max(0.2, ymax - ymin)
        padding = span * 0.1
        lower = max(0, ymin - padding)
        upper = ymax + padding
        if lower == upper:
            upper = lower + 1
        self.plot_widget.setYRange(lower, upper, padding=0)

    def _clear_plot_items(self):
        self.w1_curve.setData([], [])
        self.w2_curve.setData([], [])

    def _clear_dashboard(self):
        """Reset UI labels, plots, and state to an idle baseline."""
        if self.is_running:
            self._stop_experiment(silent=True)

        self._exit_history_mode()
        self.last_retrieved_data = None

        self.exp_label.setText(f"EXPERIMENT : {self.experiment_number}")
        self._set_measure_label(self.t1_label, "TEMP -1", None, "C")
        self._set_measure_label(self.t2_label, "TEMP -2", None, "C")
        self._set_measure_label(self.w1_label, "WEIGHT -1", None, "kg")
        self._set_measure_label(self.w2_label, "WEIGHT -2", None, "kg")
        self._set_measure_label(self.rt1_label, "ROOM TEMP", None, "C")
        self._set_measure_label(self.w_diff_label, "DIFF (W1-W2)", None, "kg")

        self._clear_plot_items()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_input.setEnabled(True)
        self.interval_unit_combo.setEnabled(True)

        if hasattr(data, "history") and isinstance(getattr(data, "history"), list):
            data.history.clear()




    def _setup_footer_area(self):
        self.footer_container = QWidget()
        h_layout = QHBoxLayout(self.footer_container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)
        self.datetime_label = QLabel()
        self.datetime_label.setStyleSheet("color: #6C757D; font-size: 14px; padding: 5px;")
        h_layout.addStretch()
        h_layout.addWidget(self.datetime_label)

    def update_datetime(self):
        current_dt = QDateTime.currentDateTime().toString("dd-MM-yyyy hh:mm:ss AP")
        self.datetime_label.setText(f"Last Update: {current_dt}")

  


    def _setup_data_retrieval_panel(self):
        self.data_retrieval_widget = QWidget()
        self.data_retrieval_widget.setStyleSheet("""
            border: 2px solid gray; border-radius: 10px; padding: 10px; background-color: #FFFFFF;
        """)
        self.data_retrieval_widget.setMinimumHeight(110)
        self.data_retrieval_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        h_layout = QHBoxLayout(self.data_retrieval_widget)
        h_layout.setContentsMargins(10, 5, 10, 5)
        h_layout.setSpacing(20)
        h_layout.setAlignment(Qt.AlignCenter)

        # --- Start Date ---
        h_layout.addWidget(QLabel("Start Date:"))
        self.start_date_edit = QDateEdit(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setStyleSheet("""
            QDateEdit {background-color: white; border: 2px solid gray; border-radius: 5px; padding: 5px;}
            QComboBox::drop-down {subcontrol-origin: padding; subcontrol-position: top right; width: 25px; border-left: 2px solid gray; background-color: #FF6600; border-top-right-radius: 5px; border-bottom-right-radius: 5px;}
            QComboBox::down-arrow {content: "▼"; font-size: 10px; color: black; width: 10px; height: 9px; padding-right: 5px;}
            QComboBox::drop-down:hover {background-color: #FF8533;}
        """)
        calendar_start = QCalendarWidget()
        calendar_start.setStyleSheet("""
            QCalendarWidget QWidget { color: black; }
            QCalendarWidget QAbstractItemView:enabled {color: black; selection-background-color: #87CEFA;}
            QCalendarWidget QToolButton { color: black; font-weight: bold; }
            QCalendarWidget QSpinBox { color: black; }
        """)
        self.start_date_edit.setCalendarWidget(calendar_start)
        h_layout.addWidget(self.start_date_edit)

        # --- End Date ---
        h_layout.addWidget(QLabel("End Date:"))
        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setStyleSheet("""
            QDateEdit {background-color: white; border: 2px solid gray; border-radius: 5px; padding: 5px;}
            QComboBox::drop-down {subcontrol-origin: padding; subcontrol-position: top right; width: 25px; border-left: 2px solid gray; background-color: #FF6600; border-top-right-radius: 5px; border-bottom-right-radius: 5px;}
            QComboBox::down-arrow {content: "▼"; font-size: 10px; color: black; width: 10px; height: 9px; padding-right: 5px;}
            QComboBox::drop-down:hover {background-color: #FF8533;}
        """)
        calendar_end = QCalendarWidget()
        calendar_end.setStyleSheet("""
            QCalendarWidget QWidget { color: black; }
            QCalendarWidget QAbstractItemView:enabled {color: black; selection-background-color: #87CEFA;}
            QCalendarWidget QToolButton { color: black; font-weight: bold; }
            QCalendarWidget QSpinBox { color: black; }
        """)
        self.end_date_edit.setCalendarWidget(calendar_end)
        h_layout.addWidget(self.end_date_edit)

        # --- Experiment Number Entry Box ---
        exp_label = QLabel("Experiment No(s):")
        exp_label.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Bold))
        exp_label.setStyleSheet("color: #0D47A1;")
        h_layout.addWidget(exp_label)

        self.exp_input = QLineEdit()
        self.exp_input.setPlaceholderText("e.g. 1, 2, 3")
        self.exp_input.setMinimumWidth(160)
        self.exp_input.setMinimumHeight(35)
        self.exp_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.exp_input.setStyleSheet("""
            QLineEdit {
                background-color: white; border: 2px solid gray; border-radius: 5px;
                padding: 5px; font-size: 11pt;
            }
            QLineEdit:focus { border: 2px solid #FF6600; }
        """)
        h_layout.addWidget(self.exp_input)

        # --- Get Data Button ---
        self.get_data_button = QPushButton("Get Data")
        self.get_data_button.setStyleSheet(self.button_style.replace(self.fg_color, "#FF6600"))
        self.get_data_button.setMinimumHeight(40)
        self.get_data_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.get_data_button.clicked.connect(self.retrieve_historical_data)
        h_layout.addWidget(self.get_data_button)

        return self.data_retrieval_widget


    def retrieve_historical_data(self):
        '''
        Called when 'Get Data' button is clicked.
        Fetches records from storage between selected dates and experiment numbers,
        updates the UI labels, and plots the retrieved data.
        '''
        from helper.data_get import get_data_by_date_and_experiment
        import re
        from PyQt5.QtWidgets import QMessageBox

        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        exp_text = self.exp_input.text().strip()
        if not exp_text:
            QMessageBox.warning(self, "Input Error", "Please enter at least one experiment number.")
            return

        experiment_numbers = [int(x) for x in re.findall(r"\d+", exp_text)]
        if not experiment_numbers:
            QMessageBox.warning(self, "Input Error", "Invalid experiment number format.")
            return

        print(f"? Fetching data from {start_date} to {end_date} for experiments {experiment_numbers}...")
        df = get_data_by_date_and_experiment(start_date, end_date, experiment_numbers)
        if df.empty:
            QMessageBox.information(
                self,
                "No Data Found",
                f"No records found between {start_date} and {end_date} "
                f"for experiments {', '.join(map(str, experiment_numbers))}.",
            )
            print("?? No records found.")
            self._clear_plot_items()
            return

        cleaned_df = self._prepare_dataframe_for_display(df)
        if cleaned_df.empty:
            QMessageBox.information(
                self,
                "No Data Found",
                "Records were found but could not be aligned to timestamps.",
            )
            self._clear_plot_items()
            return

        row_count = len(cleaned_df)
        print(f"\n? Data retrieved successfully: {row_count} rows")
        print(cleaned_df.head())

        QMessageBox.information(
            self,
            "Data Retrieved",
            f"? Retrieved {row_count} records from {start_date} to {end_date} "
            f"for EXP {', '.join(map(str, experiment_numbers))}.",
        )

        self.last_retrieved_data = cleaned_df
        self._apply_historical_dataset(cleaned_df)


# --- Main Application Execution ---
if __name__ == '__main__':
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = FullScreenWindow()
    window.show()
    sys.exit(app.exec_())
