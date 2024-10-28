""" v1.2 Revision Details - dynamic parsing:
    - Added 4th option in SELECT_PARSING for parsing logging files collected by dynamic_logging_v1.2 script
    Author - anupshinde.business@gmail.com
    Note: This v1.2 parsing only works with v1.1 logging script,
        with older logging script may encounter unhandled errors
"""
import os
import statistics
import numpy as np
import pandas as pd
import logging
from datetime import datetime
import time
import folium
from folium.plugins import HeatMap, MarkerCluster

# Global configuration
DEBUG = False  # Set to True for debugging
ENABLE_MAPPING = False  # Set to True for plot satellite map
SKIP_EMPTY = 0  # Set 0 to avoid skipping logs without sim modem data before exporting to Excel sheet
SELECT_PARSING = 4  # 1 = Both, 2 = Only GNSS, 3 = Only MODEM, 4 = Pump Modem
OUTPUT_FOLDER = "output"

# create timestamp for files
date_time_now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
# Define input file paths (modify as needed)
GNSS_LOG_FILE = os.path.join(OUTPUT_FOLDER, "gnss_2024-09-16_13-23-09.log")
SIM_MODEM_LOG_FILE = os.path.join(OUTPUT_FOLDER, "modem_2024-09-16_13-23-58.log")
OUTPUT_EXCEL_FILE = os.path.join(OUTPUT_FOLDER, f"performance_data_{date_time_now}.xlsx")
OUTPUT_MAP_FILE = os.path.join(OUTPUT_FOLDER, f"map_{date_time_now}.html")
DYNAMIC_PARSER_LOG_FILE = os.path.join(OUTPUT_FOLDER, f"dynamic_parser_{date_time_now}.log")


def configure_logging():
    """Configures logging for the application."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(DYNAMIC_PARSER_LOG_FILE),
            logging.StreamHandler(),
        ],
    )


logger = logging.getLogger(__name__)


def create_map(data):
    """Creates a folium map with the given data.

    Args:
        data (pd.DataFrame): DataFrame containing latitude, longitude, and quality data.

    Returns:
        folium.Map: The created map.
    """

    # Map color code based on sim modem signal quality
    def get_color(quality):
        if quality <= 20:
            return 'red'
        elif quality <= 30:
            return 'orange'
        elif quality <= 40:
            return 'lightgreen'
        else:
            return 'green'

    # Create a folium map centered on the approximate location
    average_lat = data['lat'].mean()
    average_lon = data['lon'].mean()
    m = folium.Map(location=[average_lat, average_lon], zoom_start=10)

    # Create a Polyline for the path
    folium.PolyLine(list(zip(data['lat'], data['lon'])), color='blue', weight=2.5).add_to(m)

    # Create a heatmap layer
    heatmap = folium.plugins.HeatMap(list(zip(data['lat'], data['lon'], data['quality'])))
    heatmap.add_to(m)

    # Create a MarkerCluster for interactive markers
    marker_cluster = MarkerCluster(max_cluster_size=50, zoom_start=5)

    for index, row in data.iterrows():
        popup_content = (f"Timestamp: {row['timestamp']}<br>Quality: "
                         f"{row['quality']}<br>Average CNo: {row['average_cno']}")
        marker = folium.Marker([row['lat'], row['lon']], popup=popup_content,
                               icon=folium.Icon(color=get_color(row['quality'])))
        marker_cluster.add_child(marker)

    m.add_child(marker_cluster)

    return m


def extract_value_from_string(string, key):
    """Extracts a value from a string based on a given key.

    Args:
        string (str): The string to extract the value from.
        key (str): The key to identify the value.

    Returns:
        int or float: The extracted value if found, None otherwise.
    """
    try:
        parts = string.split("=")
        if parts[0] == key:
            return int(parts[1]) if parts[1].isdigit() else float(parts[1])
    except (IndexError, ValueError):
        logger.warning(f"extract_value_from_string: Error extracting value from string: {string}, key: {key}")
    return None


def extract_value_from_variable_string(string, delimiter):
    """Extracts a value from a string with a delimiter.

    Args:
        string (str): The string to extract the value from.
        delimiter (str): The delimiter separating the key and value.

    Returns:
        int or float: The extracted value if found, None otherwise.
    """
    try:
        parts = string.split(delimiter)
        return int(parts[1]) if parts[1].isdigit() else float(parts[1])
    except (IndexError, ValueError):
        logger.warning(f"extract_value_from_variable_string: Error extracting value "
                       f"from variable string: {string}, delimiter: {delimiter}")
    return None


def find_substring_in_string(string, key_string):
    """Checks if a substring exists within a string.

    Args:
        string (str): The string to search.
        key_string (str): The substring to find.

    Returns:
        bool: True if the substring is found, False otherwise.
    """
    return key_string in string


def safe_fmean(data):
    """Calculates the mean of a list, handling potential division by zero.

    Args:
        data (list): The list of data points.

    Returns:
        float: The mean of the data or None if the list is empty.
    """
    return statistics.fmean(data) if data else None


def safe_max(data):
    """Finds the maximum value in a list, handling empty lists.

    Args:
        data (list): The list of data points.

    Returns:
        int or float: The maximum value in the list or None if empty.
    """
    return max(data) if data else None


def map_sinr_to_db(sinr_value):
    """Maps SINR value to dB.

    Args:
        sinr_value (int): The SINR value.

    Raises:
        ValueError: If the SINR value is outside the valid range.

    Returns:
        int: The SINR value in dB.
    """
    if not isinstance(sinr_value, int):
        raise ValueError("map_sinr_to_db: sinr_value must be integer")
    if sinr_value < 0 or sinr_value > 250:
        raise ValueError("map_sinr_to_db: sinr_value must be between 0 and 250")
    return sinr_value // 5 - 20


def calculate_signal_quality(rsrp, rssi, rsrq, sinr):
    """Calculates signal quality based on RSRP, RSSI, RSRQ, and SINR values.

    Args:
        rsrp (int): Reference Signal Received Power (RSRP) value.
        rssi (int): Received Signal Strength Indicator (RSSI) value.
        rsrq (float): Reference Signal Received Quality (RSRQ) value.
        sinr (int): Signal-to-Interference-plus-Noise Ratio (SINR) value.

    Returns:
        float: Calculated signal quality.
    """
    # Map RSRP to quality percentage
    if rsrp >= -84:
        rsrp_quality = 40
    elif rsrp >= -102:
        rsrp_quality = 30
    elif rsrp >= -111:
        rsrp_quality = 20
    else:
        rsrp_quality = 10

    # Map RSSI to quality percentage
    if rssi >= -65:
        rssi_quality = 40
    elif rssi >= -75:
        rssi_quality = 30
    elif rssi >= -85:
        rssi_quality = 20
    else:
        rssi_quality = 10

    # Map RSRQ to quality percentage
    if rsrq >= -5:
        rsrq_quality = 40
    elif rssi >= -6:
        rsrq_quality = 30
    else:
        rsrq_quality = 10

    # Map SINR to quality percentage
    if sinr >= 12.5:
        sinr_quality = 40
    elif sinr >= 10:
        sinr_quality = 30
    elif sinr >= 7:
        sinr_quality = 20
    else:
        sinr_quality = 10

    # Calculate overall signal quality
    return (rsrp_quality + rssi_quality + rsrq_quality + sinr_quality) / 4


def parse_gnss_log(file_path):
    """Parses GNSS log file and returns a pandas DataFrame.

    Args:
        file_path (str): Path to the GNSS log file.

    Returns:
        pd.DataFrame: DataFrame containing parsed GNSS data.
    """
    gnss_data = []
    (num_svs, utc_time, ttff, gps_avg_cno, gps_max_cno, gps_cno_above40, sbas_avg_cno, sbas_max_cno, sbas_cno_above40,
     galileo_avg_cno, galileo_max_cno, galileo_cno_above40, beidou_avg_cno, beidou_max_cno, beidou_cno_above40,
     glonass_avg_cno, glonass_max_cno, glonass_cno_above40, fix_type, gnss_fix_ok, num_sv, lon, lat, h_msl,
     h_acc, v_acc, g_speed, s_acc, head_acc, p_dop, head_veh) = [None] * 31
    with open(file_path, 'r') as f:
        for line_number, line in enumerate(f, start=1):
            try:
                timestamp, ubx_data = line.split('<', 1)
                timestamp = timestamp[:-1]
                ubx_head, ubx_data = ubx_data.split('(', 1)
                logger.debug(f"parse_gnss_log: UBX data frame: {ubx_data}")
                ubx_messages = ubx_data.strip().split(',')
                match (ubx_messages[0]):
                    case 'NAV-PVT':
                        logger.debug(f"parse_gnss_log: NAV-PVT == {ubx_messages[0]}")
                        utc_year = extract_value_from_string(ubx_messages[2], ' year')
                        utc_month = extract_value_from_string(ubx_messages[3], ' month')
                        utc_day = extract_value_from_string(ubx_messages[4], ' day')
                        utc_hour = extract_value_from_string(ubx_messages[5], ' hour')
                        utc_min = extract_value_from_string(ubx_messages[6], ' min')
                        utc_second = extract_value_from_string(ubx_messages[7], ' second')
                        utc_time = datetime(utc_year, utc_month, utc_day, utc_hour, utc_min, utc_second)
                        fix_type = extract_value_from_string(ubx_messages[14], ' fixType')
                        gnss_fix_ok = extract_value_from_string(ubx_messages[15], ' gnssFixOk')
                        num_sv = extract_value_from_string(ubx_messages[23], ' numSV')
                        lon = extract_value_from_string(ubx_messages[24], ' lon')
                        lat = extract_value_from_string(ubx_messages[25], ' lat')
                        h_msl = extract_value_from_string(ubx_messages[27], ' hMSL')
                        h_acc = extract_value_from_string(ubx_messages[28], ' hAcc')
                        v_acc = extract_value_from_string(ubx_messages[29], ' vAcc')
                        g_speed = extract_value_from_string(ubx_messages[33], ' gSpeed')
                        s_acc = extract_value_from_string(ubx_messages[35], ' sAcc')
                        head_acc = extract_value_from_string(ubx_messages[36], ' headAcc')
                        p_dop = extract_value_from_string(ubx_messages[37], ' pDOP')
                        head_veh = extract_value_from_string(ubx_messages[41], ' headVeh')

                    case 'NAV-SAT':
                        logger.debug(f"parse_gnss_log: NAV-SAT == {ubx_messages[0]}\n")
                        num_svs = extract_value_from_string(ubx_messages[3], ' numSvs')
                        satellite_gps, satellite_sbas, satellite_galileo = [], [], []
                        satellite_beidou, satellite_glonass = [], []
                        for i in range(num_svs):
                            if find_substring_in_string(ubx_messages[5 + i * 23], 'GPS'):
                                satellite_gps.append(extract_value_from_variable_string(ubx_messages[7 + i * 23], '='))
                                logger.debug(f"parse_gnss_log: satellite_gps:{satellite_gps}")
                            elif find_substring_in_string(ubx_messages[5 + i * 23], 'SBAS'):
                                satellite_sbas.append(extract_value_from_variable_string(ubx_messages[7 + i * 23], '='))
                                logger.debug(f"parse_gnss_log: satellite_sbas:{satellite_sbas}")
                            elif find_substring_in_string(ubx_messages[5 + i * 23], 'Galileo'):
                                satellite_galileo.append(
                                    extract_value_from_variable_string(ubx_messages[7 + i * 23], '='))
                                logger.debug(f"parse_gnss_log: satellite_galileo:{satellite_galileo}")
                            elif find_substring_in_string(ubx_messages[5 + i * 23], 'BeiDou'):
                                satellite_beidou.append(
                                    extract_value_from_variable_string(ubx_messages[7 + i * 23], '='))
                                logger.debug(f"parse_gnss_log: satellite_beidou:{satellite_beidou}")
                            elif find_substring_in_string(ubx_messages[5 + i * 23], 'GLONASS'):
                                satellite_glonass.append(
                                    extract_value_from_variable_string(ubx_messages[7 + i * 23], '='))
                                logger.debug(f"parse_gnss_log: satellite_glonass:{satellite_glonass}")
                            else:
                                logger.info("parse_gnss_log: Unsupported Constellation")
                        # UBX-NAV-SAT parameters for each constellation
                        logger.debug(f"parse_gnss_log: gps list = {satellite_gps}\n")
                        gps_avg_cno = safe_fmean(satellite_gps)
                        gps_max_cno = safe_max(satellite_gps)
                        gps_cno_above40 = np.sum(np.array(satellite_gps) > 40)

                        logger.debug(f"parse_gnss_log: sbas list = {satellite_sbas}\n")
                        sbas_avg_cno = safe_fmean(satellite_sbas)
                        sbas_max_cno = safe_max(satellite_sbas)
                        sbas_cno_above40 = np.sum(np.array(satellite_sbas) > 40)

                        logger.debug(f"parse_gnss_log: galileo list = {satellite_galileo}\n")
                        galileo_avg_cno = safe_fmean(satellite_galileo)
                        galileo_max_cno = safe_max(satellite_galileo)
                        galileo_cno_above40 = np.sum(np.array(satellite_galileo) > 40)

                        logger.debug(f"parse_gnss_log: beidou list = {satellite_beidou}\n")
                        beidou_avg_cno = safe_fmean(satellite_beidou)
                        beidou_max_cno = safe_max(satellite_beidou)
                        beidou_cno_above40 = np.sum(np.array(satellite_beidou) > 40)

                        logger.debug(f"parse_gnss_log: glonass list = {satellite_glonass}\n")
                        glonass_avg_cno = safe_fmean(satellite_glonass)
                        glonass_max_cno = safe_max(satellite_glonass)
                        glonass_cno_above40 = np.sum(np.array(satellite_glonass) > 40)

                    case 'NAV-STATUS':
                        logger.debug(f"parse_gnss_log: NAV-STATUS == {ubx_messages[0]}\n")
                        ttff = (extract_value_from_string(ubx_messages[13], ' ttff')) / 1000.00
                        logger.debug(f"parse_gnss_log: ttff: {ttff}")

                    case _:
                        logger.info("parse_gnss_log: Unsupported UBX MSG type")

                # all parameters to append to gnss panda frame
                gnss_data.append(
                    [timestamp, utc_time, num_svs, ttff, gps_avg_cno, gps_max_cno, gps_cno_above40, sbas_avg_cno,
                     sbas_max_cno, sbas_cno_above40, galileo_avg_cno, galileo_max_cno, galileo_cno_above40,
                     beidou_avg_cno, beidou_max_cno, beidou_cno_above40, glonass_avg_cno, glonass_max_cno,
                     glonass_cno_above40, fix_type, gnss_fix_ok, num_sv, lon, lat, h_msl, h_acc, v_acc, g_speed,
                     s_acc, head_acc, p_dop, head_veh])
            except Exception as e:
                logger.error(f"parse_gnss_log: Error parsing line {line_number}: {e}")
    return pd.DataFrame(gnss_data,
                        columns=['timestamp', 'UTC-Time', 'numSVs', 'ttff', 'GPS-Avg', 'GPS-Max', 'GPS-CNO-G40',
                                 'SBAS-Avg', 'SBAS-Max', 'SBAS-CNO-G40', 'Galileo-Avg', 'Galileo-Max',
                                 'Galileo-CNO-G40', 'BeiDou-Avg', 'BeiDou-Max', 'BeiDou-CNO-G40', 'Glonass-Avg',
                                 'Glonass-Max', 'Glonass-CNO-G40', 'fix_type', 'gnss_fix_ok', 'num_sv', 'lon', 'lat',
                                 'h_msl', 'h_acc', 'v_acc', 'g_speed', 's_acc', 'head_acc', 'p_dop', 'head_veh'])


def parse_line(line):
    try:
        # Split by '#'
        parts = line.split('#')
        timestamp = parts[0]
        timestamp = timestamp[:-1]
        rfsts_data = parts[1] if len(parts) > 1 else None
        server_data = parts[2] if len(parts) > 2 else None
        sock_info_data = parts[3] if len(parts) > 3 else None
        sock_status_data = parts[4] if len(parts) > 4 else None

        # Split by '+'
        parts1 = line.split('+')
        nw_eps_data = parts1[1] if len(parts1) > 1 else None
        nw_data = parts1[2] if len(parts1) > 2 else None

        logger.debug(f"parse_line: {timestamp, rfsts_data, server_data, sock_info_data, sock_status_data,nw_eps_data, nw_data}")
        return timestamp, rfsts_data, server_data, sock_info_data, sock_status_data, nw_eps_data, nw_data
    except (IndexError, ValueError) as e:
        logger.info(f"parse_line: Error parsing line: {e}")
        return None, None, None, None, None, None


def parse_pump_modem_log(file_path):
    """Parses SIM modem log file and returns a pandas DataFrame.

    Args:
        file_path (str): Path to the SIM modem log file.

    Returns:
        pd.DataFrame: DataFrame containing parsed SIM modem data.
    """
    sim_modem_data = []
    # (timestamp, phone_status) = [None] * 2
    with (open(file_path, 'r') as f):
        for line_number, line in enumerate(f, start=1):
            logger.debug(f"parse_pump_modem_log: read line: {line_number}:{line}")
            try:
                timestamp, phone_mode, drop1, drop2, drop3, drop4, drop5 = parse_line(line)
                logger.debug(f"parse_pump_modem_log:  phone_mode: {phone_mode}")
                sim_modem_data.append([timestamp, phone_mode])
            except Exception as e:
                logger.error(f"parse_pump_modem_log: Error parsing line {line_number}: {e}")
    return pd.DataFrame(sim_modem_data, columns=['timestamp', 'phone_mode'])


def parse_sim_modem_log(file_path):
    """Parses SIM modem log file and returns a pandas DataFrame.

    Args:
        file_path (str): Path to the SIM modem log file.

    Returns:
        pd.DataFrame: DataFrame containing parsed SIM modem data.
    """
    sim_modem_data = []
    (timestamp, rsrp, rssi, rsrq, sinr_in_db, quality, server_msg, sock_info, sock_status,
     nw_eps_status, nw_status) = [None] * 11
    with (open(file_path, 'r') as f):
        for line_number, line in enumerate(f, start=1):
            logger.debug(f"parse_sim_modem_log: read line: {line_number}:{line}")
            try:
                timestamp, rfsts_data, server_data, sock_info_data, sock_status_data, nw_eps_data, nw_data = parse_line(
                    line)

                if rfsts_data is not None and "RFSTS" in rfsts_data:
                    head, rfsts_data = rfsts_data.split(':', 1)
                    rsrp = int(rfsts_data.split(',')[2])  # Example: extract RSRP
                    rssi = int(rfsts_data.split(',')[3])  # Example: extract RSSI
                    rsrq = float(rfsts_data.split(',')[4])  # Example: extract RSRQ
                    sinr = int(rfsts_data.split(',')[18].split(':')[0])  # Example: extract SINR
                    sinr_in_db = map_sinr_to_db(sinr)
                    quality = calculate_signal_quality(rsrp, rssi, rsrq, sinr)
                if server_data is not None and "MSG" in server_data:
                    head, server_msg = server_data.split(':', 1)
                if sock_info_data is not None and "SI" in sock_info_data:
                    head, sock_info = sock_info_data.split(':', 1)
                if sock_status_data is not None and "SS" in sock_status_data:
                    head, status, drop = sock_status_data.split(':', 2)
                    sock_status = status.split(",", 2)[1]
                if nw_eps_data is not None and "CEREG" in nw_eps_data:
                    head, nw_eps_status = nw_eps_data.split(':', 1)
                    nw_eps_status = nw_eps_status.replace(":", "")
                if nw_data is not None and "CREG" in nw_data:
                    head, nw_status = nw_data.split(':', 1)
                logger.debug(f"parse_sim_modem_log:  rfsts_data: {rfsts_data}, server_msg: {server_msg}, "
                             f"sock_info: {sock_info},sock_status: {sock_status}, sinr_in_db: {sinr_in_db}, "
                             f" quality: {quality}, nw_eps_status: {nw_eps_status}, nw_status: {nw_status}")
                sim_modem_data.append([timestamp, rsrp, rssi, rsrq, sinr_in_db, quality, server_msg, sock_info,
                                       sock_status, nw_eps_status, nw_status])
            except Exception as e:
                logger.error(f"parse_sim_modem_log: Error parsing line {line_number}: {e}")
    return pd.DataFrame(sim_modem_data, columns=['timestamp', 'rsrp', 'rssi', 'rsrq', 'sinr', 'quality',
                                                 'server_msg', 'sock_info', 'sock_status', 'cereg', 'creg'])


def merge_dataframes(gnss_dataframe, sim_modem_dataframe):
    """Merges GNSS and SIM modem dataframes based on timestamp.

    Args:
        gnss_dataframe (pd.DataFrame): DataFrame containing GNSS data.
        sim_modem_dataframe (pd.DataFrame): DataFrame containing SIM modem data.

    Returns:
        pd.DataFrame: Merged DataFrame.
    """
    return gnss_dataframe.merge(sim_modem_dataframe, on='timestamp', how='outer')


def export_to_excel(merged_dataframe, output_file, skip_empty=1):
    """Exports merged dataframe to Excel.

    Args:
        merged_dataframe (pd.DataFrame): DataFrame to be exported.
        output_file (str): Path to the output Excel file.
        skip_empty (bool, optional): If True, skips Excel write if modem data is empty. Defaults to True.
    """
    if skip_empty:
        last_5_columns = merged_dataframe.iloc[:, -5:]
        complete_rows = merged_dataframe[~last_5_columns.isnull().any(axis=1)]
        if not complete_rows.empty:
            complete_rows.to_excel(output_file, index=False)
        else:
            logger.info("export_to_excel: Last 5 data frames empty, skipping Excel write...")
    else:
        merged_dataframe.to_excel(output_file, index=False)


if __name__ == "__main__":
    configure_logging()
    logger.info("Main: Starting data processing...")
    start_time = time.time()
    match SELECT_PARSING:
        case 1:
            logger.info("Main: SELECT_PARSING set to Both")
            gnss_df = parse_gnss_log(GNSS_LOG_FILE)
            logger.debug(f"Main: gnss_df {gnss_df}")
            sim_modem_df = parse_sim_modem_log(SIM_MODEM_LOG_FILE)
            logger.debug(f"Main: sim_modem_df {sim_modem_df}")
            logger.info(f"Main: Data parsing completed in {time.time() - start_time:.2f} seconds")
            merged_df = merge_dataframes(gnss_df, sim_modem_df)
            if ENABLE_MAPPING:
                # Extract relevant data for mapping
                map_data = merged_df[
                    ['timestamp', 'lat', 'lon', 'quality', 'GPS-Max', 'SBAS-Max', 'Galileo-Max', 'BeiDou-Max',
                     'Glonass-Max']]
                # Handle NaN values and Calculate overall average of max CNo of each constellation
                map_data = map_data.dropna(subset=['timestamp', 'lat', 'lon', 'quality'])
                map_data['average_cno'] = map_data[
                    ['GPS-Max', 'SBAS-Max', 'Galileo-Max', 'BeiDou-Max', 'Glonass-Max']].mean(
                    axis=1)

                # Remove colons from timestamp
                map_data['timestamp'] = map_data['timestamp'].astype(str).str[:-1]
                # Assuming your timestamp format is YYYY-MM-DD HH:MM:SS
                map_data['timestamp'] = pd.to_datetime(map_data['timestamp'], format='%Y-%m-%d %H:%M:%S')

                # Time-based binning (adjust time interval as needed) 1Min or 10S
                map_data['timestamp_bin'] = map_data['timestamp'].dt.floor('10s')
                # Group data by time bin and calculate averages
                aggregated_data = map_data.groupby('timestamp_bin').mean().reset_index()

                # Create and display the map
                plot_map = create_map(aggregated_data)
                plot_map.save(OUTPUT_MAP_FILE)  # save the map in html file
            else:
                logger.info("Main: Mapping is disabled.")
            export_to_excel(merged_df, OUTPUT_EXCEL_FILE, SKIP_EMPTY)
            logger.info("Main: Data processing finished...")
        case 2:
            logger.info("Main: SELECT_PARSING set to Only GNSS")
            gnss_df = parse_gnss_log(GNSS_LOG_FILE)
            logger.debug(f"Main: gnss_df {gnss_df}")
            logger.info(f"Main: Data parsing completed in {time.time() - start_time:.2f} seconds")
            export_to_excel(gnss_df, OUTPUT_EXCEL_FILE, SKIP_EMPTY)
            logger.info("Main: Data processing finished...")
        case 3:
            logger.info("Main: SELECT_PARSING set to Only MODEM")
            sim_modem_df = parse_sim_modem_log(SIM_MODEM_LOG_FILE)
            logger.debug(f"Main: sim_modem_df {sim_modem_df}")
            logger.info(f"Main: Data parsing completed in {time.time() - start_time:.2f} seconds")
            export_to_excel(sim_modem_df, OUTPUT_EXCEL_FILE, SKIP_EMPTY)
            logger.info("Main: Data processing finished...")
        case 4:
            logger.info("Main: SELECT_PARSING set to Pump Modem")
            gnss_df = parse_gnss_log(GNSS_LOG_FILE)
            logger.debug(f"Main: gnss_df {gnss_df}")
            pump_sim_modem_df = parse_pump_modem_log(SIM_MODEM_LOG_FILE)
            logger.debug(f"Main: sim_modem_df {pump_sim_modem_df}")
            logger.info(f"Main: Data parsing completed in {time.time() - start_time:.2f} seconds")
            merged_df = merge_dataframes(gnss_df, pump_sim_modem_df)
            export_to_excel(merged_df, OUTPUT_EXCEL_FILE, SKIP_EMPTY)
            logger.info("Main: Data processing finished...")
        case _:
            logger.info("Main: Unsupported SELECT_PARSING type")
