GNSS and SIM Modem Performace Analyzer
This project provides a two-part solution for logging and analyzing GNSS and SIM modem data:

Part 1: Logging Script

This script continuously logs data from GNSS and SIM modem modules to separate files.

Features:

Selectable logging mode (GNSS and modem, GNSS only, modem only, or modem with flight mode simulation)
Configures serial communication with GNSS and modem modules
Parses UBX data frames from GNSS module
Parses AT commands and responses from SIM modem module
Logs timestamped data to separate files
Part 2: Parsing Script

This script parses the generated log files and extracts relevant information for analysis.

Features:

Parses GNSS log files for timestamps, location data, fix information, satellite details, and CNo data
Parses SIM modem log files for timestamps, signal quality (RSRP, RSSI, RSRQ, SINR), network registration, and socket information
Merges parsed data from both logs based on timestamps (optional filtering for empty SIM data)
Optionally generates a map visualizing the GNSS track (requires Folium library)
Exports the merged data to an Excel file
How to Use:

1. Setting Up PyCharm

Create a new Python project in PyCharm.
Copy the logging script (e.g., gnss_modem_logger.py) and parsing script (e.g., gnss_modem_parser.py) into your project directory.
2. Running the Logging Script

Open the logging script in PyCharm.
Modify the SELECT_LOGGING variable at the beginning to choose the desired logging mode.
Click the green "Run" button (play icon) or press Shift+F10 to execute the script. Data will be logged to separate files.
3. Running the Parsing Script

Open the parsing script in PyCharm.
Update the GNSS_LOG_FILE and SIM_MODEM_LOG_FILE paths to point to the generated log files created by the logging script.
Adjust the SELECT_PARSING variable to choose the desired parsing mode (both GNSS and modem, GNSS only, modem only, or pump modem).
Click the green "Run" button or press Shift+F10 to process the log files and generate the output Excel file.
Additional Notes:

Ensure the GNSS and SIM modem modules are connected and configured correctly.
Modify the parsing logic if your GNSS or SIM modem log formats differ.
Install folium (optional for maps): pip install folium in your project's terminal.
This combined solution provides a powerful tool for monitoring and analyzing GNSS and SIM modem performance. By logging and parsing data, you can gain valuable insights into your system's behavior.