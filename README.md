# GNSS and SIM Modem Performance Analyzer

## Overview

This project provides a comprehensive solution for logging and analyzing GNSS and SIM modem data. It consists of two Python scripts:

1. **Logging Script (dynamic_logging.py)**
   - Continuously logs data from GNSS and SIM modem modules.
   - Configures serial communication and parses data from both modules.
   - Logs timestamped data to separate files.

2. **Parsing Script (dynamic_parsing.py)**
   - Parses the generated log files to extract:
     - Timestamps
     - Location data
     - Fix information
     - Satellite details
     - Signal quality (RSRP, RSSI, RSRQ, SINR)
     - Network registration
     - Socket information
   - Merges the parsed data from both logs based on timestamps (optional filtering for empty SIM data).
   - Optionally generates a map visualizing the GNSS track (requires the `folium` library).
   - Exports the merged data to an Excel file.

## How to Use

1. **Setting Up PyCharm**
   - Create a new Python project in PyCharm.
   - install necessary libraries using `pip install <library_name>`
   - Copy the `dynamic_logging.py` and `dynamic_parsing.py` scripts into your project directory.

2. **Running the Logging Script**
   - Open `dynamic_logging.py` in PyCharm.
   - Modify the `SELECT_LOGGING` variable to choose the desired logging mode.
   - Run the script using the green "Run" button or press `Shift+F10`.

3. **Running the Parsing Script**
   - Open `dynamic_parsing.py` in PyCharm.
   - Update the `GNSS_LOG_FILE` and `SIM_MODEM_LOG_FILE` paths to point to the generated log files.
   - Adjust the `SELECT_PARSING` variable to choose the desired parsing mode.
   - Run the script to process the log files and generate the output Excel file.

## Additional Notes

- Ensure your GNSS and SIM modem modules are connected and configured correctly.
- The parsing logic might need adjustments for different GNSS or SIM modem log formats.
- To enable map generation, install the `folium` library: `pip install folium`.

By combining these scripts, you can effectively monitor and analyze the performance of your GNSS and SIM modem system.
