
""" v1.2 Revision Details - dynamic logging:
    - Added 4th option in SELECT_LOGGING for logging with spacial case
            flight mode off - pumping data to server, flight mode on - sleep
    - Removed asyncio and used ThreadPoolExecutor to run gnss and modem parallel
    Author - anupshinde.business@gmail.com
"""
import os
import time
import serial
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor
from pyubx2 import UBXReader, UBX_PROTOCOL
from serial.serialutil import SerialException

# Global configuration
SELECT_LOGGING = 4  # 1 = Both, 2 = Only GNSS, 3 = Only MODEM, 4 = Pump MODEM
DEBUG = False  # Set to True for debugging
TIMES_RETRY = 15  # Set value 0 - 15 to wait and try to check LTE NW registered
OUTPUT_FOLDER = "output"

"""FOR READERS: set of commands required to config modem for LTE technology
    commands:
        AT - Get modem attention,
        AT+COPS=2 -  Deregister from network,
        AT+CGDCONT=1,"IP","wbdata" - Set PDP and APN,
        AT+COPS=0 - Automatic selection of network,
        AT+WS46=30 - Select wireless network GSM and LTE,
        AT#WS46=0,0 - Select IOT Technology CAT-M1 and LTE priority,
        AT#BND=0,0,524420,0,0' - Select LTE band,
        AT+COPS? - Test Operator Selection expected +COPS: 0,0,"Orange F",8,
        AT#REBOOT - Reboot modem,
        AT+CEREG? - Network Registration Status expected +CEREG: 0,5,
        AT+CESQ - Extended Signal Quality expected for 2G network: +CESQ: <rssi>,<ber>,255,255,255,255
                    for LTE network: +CESQ: 99,99,255,255,<rsrq>,<rsrp>,
        AT#RFSTS - Read Current Network Status
                    for GSM: #RFSTS:<PLMN>,<ARFCN>,<RSSI>,<LAC>,<RAC>,<TXPWR>,<MM>,<RR>,<NOM>,<CID>,
                            <IMSI>,<NetNameAsc>,<SD>,<ABND>
                    for LTE: #RFSTS:<PLMN>,<EARFCN>,<RSRP>,<RSSI>,<RSRQ>,<TAC>,<RAC>,[<TXPWR>],<DRX>,
                            <MM>,<RRC>,<CID>,<IMSI>,[<NetNameAsc>],<SD>,<ABND>,<T3402>,<T3412>,<SINR>
"""

cfg_commands = ['AT',
                'AT+COPS=2',
                'AT+CGDCONT=1,"IP","wbdata"',
                'AT+COPS=0',
                'AT+WS46=30',
                'AT#WS46=0,0',
                'AT#BND=0,0,524420,0,0',
                'AT#REBOOT']

signal_commands = ['AT+CESQ',
                   'AT#SGACT=1,0',
                   'AT#SGACT=1,1']

nw_eps_reg_status = "AT+CEREG?"
nw_reg_status = "AT+CREG?"

tcp_connect_commands = ['AT#SGACT?',
                        'AT#SD=1,0,7,"echo.u-blox.com",0,0,1']

message_to_server = ['AT#SSEND=1',
                     'TCP_TEST_OK',
                     '\x1a']

socket_commands = ['AT#SI',
                   'AT#SS']

msg_in_response = "TCP_TEST_OK"

message_from_server = "AT#SRECV=1,1500"

rf_status_command = "AT#RFSTS"

cops_check_command = "AT+COPS?"

flight_mode_commands = ['AT+CFUN=1',
                        'AT+CFUN=4']
pump_dummy_msg = 'aasdgajgfsdfhgafdsakjfgadskjfgiweuryaioweuryiuwyfhaksjdbvdsmbvkdshakfhdaklsfhklahfksdfhakdashfklsdhfkasdfkshalkfhafklhdsafdksjahfkdashfklahfdklsajfhkasdhfahieuwryioqyeifofiufbvyiyviyvqioiqoviuytvqiobyvqotbvyqtvyqoityvqoitbvqtvbytebvqityvetbvyitvybtvqiytqboitvyotvyqityqiwebvotyibwevytibvweytiwytvibakhksgdkjasj\x1a'
# Create output folder if it doesn't exist
if not os.path.exists(OUTPUT_FOLDER):
    os.mkdir(OUTPUT_FOLDER)

# create timestamp for file
date_time_now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
DYNAMIC_LOGGING_LOG_FILE = os.path.join(OUTPUT_FOLDER, f"dynamic_logging_{date_time_now}.log")

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(DYNAMIC_LOGGING_LOG_FILE),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


def create_log_file(base_name):
    """Creates a new log file with a timestamped name in the output folder."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = os.path.join(OUTPUT_FOLDER, f"{base_name}_{timestamp}.log")
    logger.debug(f"create_log_file: New log file generated for {base_name}: {log_file_path}")
    return log_file_path


def start_serial_connection(port, baud_rate):
    """Starts serial connections to GNSS: baud 230400 and modem: baud 115200 ports."""
    try:
        logger.info("start_serial_connection: Connecting to COM ports...")
        return serial.Serial(port, baud_rate)
    except SerialException as e:
        logger.error(f"start_serial_connection: Error connecting to COM ports: {e}")
        return None


def com_port_read_write(port, command, max_timeout=3):
    """Sends a command to the specified serial port and returns the response."""
    try:
        port.flush()
        port.write(f"{command}\r\n".encode())
        port.timeout = max_timeout
        response = port.readall().decode().strip()
        logger.debug(f"com_port_read_write: Writing to port: {port} command: {command} response: {response}")
        return response
    except (UnicodeDecodeError, SerialException) as e:
        logger.error(f"com_port_read_write: Error reading from serial port: {e}")
        return None


def configure_sim_module(com_port, config_commands, max_retries=15):
    """Configures the SIM module with the given commands."""
    config_responses = []
    for command in config_commands:
        cfg_response = com_port_read_write(com_port, command, 2)
        if cfg_response is not None:
            if "OK" in cfg_response:
                config_responses.append((command, cfg_response))
            else:
                logger.error(f"configure_sim_module: config SIM returned "
                             f"ERROR for command {command}:{cfg_response}")
                return False
    logger.debug(config_responses)
    logger.info("configure_sim_module: Configuration Success, Rebooting Modem...")
    time.sleep(2)
    start_search_nw = time.time()
    for attempt in range(max_retries):
        cops_response = com_port_read_write(com_port, cops_check_command, 2)
        if cops_response is not None:
            if '8' in cops_response:
                logger.info(f"configure_sim_module: LTE Network registered and roaming, "
                            f"time to register nw :{time.time() - start_search_nw:.2f} seconds")
                return True
            else:
                logger.info(f"configure_sim_module: cops response: {cops_response} Searching for LTE network. "
                            f"Retry {attempt + 1}/{max_retries}\n")
                time.sleep(1)


def pump_data_to_server(port, max_msg_count):
    context_response = com_port_read_write(port, 'AT#SGACT=1,1', 5)
    logger.info(f"pump_data_to_server: context_response: {context_response}")
    server_response = com_port_read_write(port, 'AT#SD=1,0,7,"echo.u-blox.com",0,0,1', 10)
    logger.info(f"pump_data_to_server: server_response: {server_response}")
    while max_msg_count:
        send_response = com_port_read_write(port, 'AT#SSEND=1', 5)
        logger.info(f"pump_data_to_server: send_response: {send_response}")
        msg_response = com_port_read_write(port, pump_dummy_msg, 5)
        logger.info(f"pump_data_to_server:{max_msg_count} msg_response: {msg_response}")
        if msg_response is not None and 'OK' not in msg_response:
            break
        max_msg_count -= 1
    socket_response = com_port_read_write(port, 'AT#SH=1', 5)
    logger.info(f"pump_data_to_server: shutdown socket connection: {socket_response}")


def tcp_connection_test(port, tcp_commands, msg_to_commands, msg_from_command, sock_commands):
    message_response = []

    for command in tcp_commands:
        server_response = com_port_read_write(port, command, 1)
        logger.info(f"tcp_connection_test: server_response: {server_response}")

    for command in msg_to_commands:
        msg_response = com_port_read_write(port, command, 1)
        logger.debug(f"tcp_connection_test: message response: {msg_response}")

    response = com_port_read_write(port, msg_from_command, 1)
    logger.debug(f"tcp_connection_test: response from server : {response}")
    if response is not None:
        lines = response.splitlines()
        message_response.append("#MSG:")
        for line in lines:
            if msg_in_response in line:
                # logger.info(f"tcp_connection_test:  response from server is : {line}")
                message_response.append(line)
                break
    else:
        message_response.append("#MSG: None")

    for command in sock_commands:
        sock_response = com_port_read_write(port, command, 1)
        logger.debug(f"tcp_connection_test: socket response: {sock_response}")
        if sock_response is not None:
            lines = sock_response.splitlines()
            for line in lines:
                if line.startswith("#SI: 1"):
                    logger.debug(f"tcp_connection_test: #SI socket response in line: {line}")
                    message_response.append(line)
                    break
                elif line.startswith("#SS: 1"):
                    logger.debug(f"tcp_connection_test: #SS socket response in line: {line}")
                    message_response.append(line)
                    break

    return " ".join(str(item) for item in message_response)


def check_network_status(port, command):
    response = []
    nw_stat_response = com_port_read_write(port, command, 1)
    if nw_stat_response is not None:
        lines = nw_stat_response.splitlines()
        for line in lines:
            if line.startswith("+CEREG:") or line.startswith("+CREG:") or line.startswith("+COPS:"):
                logger.debug(f"check_network_status:  network status is : {line}")
                response.append(line)
    else:
        logger.debug(f"check_network_status: Failed get network status for command {command} : {nw_stat_response}")
    return " ".join(str(item) for item in response)


def check_rf_status(port, command):
    response = []
    rf_status_responses = com_port_read_write(port, command, 2)
    logger.debug(f"check_rf_status: {rf_status_responses}")
    if rf_status_responses is not None:
        lines = rf_status_responses.splitlines()
        for line in lines:
            if line.startswith("#RFSTS:"):
                logger.debug(f"check_rf_status: check RF status: {line}")
                response.append(line)
    else:
        logger.debug(f"check_rf_status: Failed to check RF status: {rf_status_responses}")
    return " ".join(str(item) for item in response)


def pump_modem_data_with_flight_mode(com_port, sig_commands, config_commands, phone_mode_commands):
    """ Pump modem data while flight mode on or off and logs into file"""
    modem_configured = configure_sim_module(com_port, config_commands, TIMES_RETRY)  # configure modem
    if modem_configured:
        modem_log_file = create_log_file("modem")
        with open(modem_log_file, "a", encoding='utf-8') as f:
            for command in sig_commands:
                stat_response = com_port_read_write(com_port, command, 2)  # log modem signals
                if stat_response is not None:
                    logger.info(f"pump_modem_data_with_flight_mode: signal command:{command} "
                                f"and signal status: {stat_response}\n")
                else:
                    logger.info(f"pump_modem_data_with_flight_mode: signal command : {command} "
                                f"for signal status responded None")

            logger.info("pump_modem_data_with_flight_mode: Started logging into file...\n")
            while True:
                for command in phone_mode_commands:
                    phone_mode_response = com_port_read_write(com_port, command, 1)
                    logger.info(f"pump_modem_data_with_flight_mode: mode set to: {command} "
                                f"mode_response: {phone_mode_response}")
                    if '1' in command:
                        time.sleep(10)  # allow modem to connect back to network
                        cops_response = com_port_read_write(com_port, cops_check_command, 2)
                        logger.info(f"pump_modem_data_with_flight_mode: Confirming nw "
                                    f"is attached to modem, cops: {cops_response}")
                        if cops_response is not None:
                            if '8' in cops_response:
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                                f.write(f"{timestamp}:'#Pumping Data To Server...'\n")
                                f.flush()
                                os.fsync(f)
                                logger.info(f"Start time of pump modem data : {time.strftime('%Y-%m-%d %H:%M:%S')}")
                                pump_data_to_server(com_port, 5)
                                logger.info(f"End time of pump modem data : {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    elif '4' in command:
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"{timestamp}:'#Flight Mode Active...'\n")
                        f.flush()
                        os.fsync(f)
                    time.sleep(10)  # allow gnss to take few logs with flight mode active
    else:
        logger.info("pump_modem_data_with_flight_mode: Failed to configure modem..\n")


def read_and_log_modem_data(com_port, sig_commands, rf_command, nw_eps_command,
                            nw_command, config_commands):
    """Reads and logs data from the modem port asynchronously."""
    modem_configured = configure_sim_module(com_port, config_commands, TIMES_RETRY)  # configure modem
    if modem_configured:
        modem_log_file = create_log_file("modem")
        with open(modem_log_file, "a", encoding='utf-8') as f:
            for command in sig_commands:
                stat_response = com_port_read_write(com_port, command, 2)  # log modem signals
                if stat_response is not None:
                    logger.info(f"read_and_log_modem_data: signal command:{command} "
                                f"and signal status: {stat_response}\n")
                else:
                    logger.info(f"read_and_log_modem_data: signal command : {command} "
                                f"for signal status responded None")

            logger.info("read_and_log_modem_data: Started logging into file...\n")
            while True:
                tcp_status = tcp_connection_test(com_port, tcp_connect_commands,
                                                 message_to_server, message_from_server,
                                                 socket_commands)
                nw_eps_status = check_network_status(com_port, nw_eps_command)
                nw_status = check_network_status(com_port, nw_command)
                rf_status = check_rf_status(com_port, rf_command)

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.debug(
                    f"read_and_log_modem_data: Writing to file timestamp appended "
                    f"RF status response and NTP response: {timestamp}+{rf_status}+{tcp_status}+"
                    f"{nw_eps_status}+{nw_status}\n")
                f.write(f"{timestamp}:{rf_status}:{tcp_status}:{nw_eps_status}:{nw_status}\n")
                f.flush()
                os.fsync(f)
    else:
        logger.info("read_and_log_modem_data: Failed to configure modem..\n")


def read_and_log_gnss_data(com_port):
    """Reads and logs data from the GNSS port."""
    gnss_log_file = create_log_file("gnss")
    with open(gnss_log_file, "a") as f:
        while True:
            ubx_raw_data = UBXReader(com_port, protfilter=UBX_PROTOCOL)
            if ubx_raw_data is not None:
                for raw_data, ubx_data in ubx_raw_data:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.debug(
                        f"read_and_log_gnss_data: Writing to file timestamp appended "
                        f"UBX data frames: {timestamp}+{ubx_data}\n")
                    f.write(f"{timestamp}:{ubx_data}\n")
                    f.flush()
                    os.fsync(f)
            else:
                logger.debug(f"read_and_log_gnss_data: UBX raw data responded NONE")


def start_gnss_thread(port):
    logger.info(f"start_gnss_thread: Starting GNSS serial connection on port {port}")
    ser = start_serial_connection(port, 230400)
    logger.debug(f"start_gnss_thread: gnss serial connections established {ser}")
    if ser is not None:
        read_and_log_gnss_data(ser)
    else:
        logger.info("start_gnss_thread: failed to get gnss serial connection")


def start_modem_thread(port):
    logger.info(f"start_modem_thread: Starting Modem serial connection on port {port}")
    ser = start_serial_connection(port, 115200)
    logger.debug(f"start_modem_thread: modem serial connections established {ser}")
    if ser is not None:
        read_and_log_modem_data(ser, signal_commands, rf_status_command,
                                nw_eps_reg_status, nw_reg_status, cfg_commands)
    else:
        logger.info("start_modem_thread: failed to get modem serial connection")


def start_pump_modem_thread(port):
    logger.info(f"start_pump_modem_thread: Starting Modem serial connection on port {port}")
    ser = start_serial_connection(port, 115200)
    logger.debug(f"start_pump_modem_thread: modem serial connections established {ser}")
    if ser is not None:
        pump_modem_data_with_flight_mode(ser, signal_commands, cfg_commands,
                                         flight_mode_commands)
    else:
        logger.info("start_pump_modem_thread: failed to get modem serial connection")


def run_io_tasks_in_parallel(tasks):
    with ThreadPoolExecutor() as executor:
        running_tasks = [executor.submit(task) for task in tasks]
        for running_task in running_tasks:
            running_task.result()


if __name__ == "__main__":
    match SELECT_LOGGING:
        case 1:
            logger.info("Main: SELECT_LOGGING set to Both")
            run_io_tasks_in_parallel([
                lambda: start_gnss_thread('COM4'),
                lambda: start_modem_thread('COM8'),
            ])
        case 2:
            logger.info("Main: SELECT_LOGGING set to Only GNSS")
            logger.info("start_gnss_thread: Starting GNSS thread...")
            start_gnss_thread('COM4')  # verify in win device manager
        case 3:
            logger.info("Main: SELECT_LOGGING set to Only MODEM")
            logger.info("start_modem_thread: Starting Modem thread...")
            start_modem_thread('COM8')  # verify in win device manager
        case 4:
            logger.info("Main: SELECT_LOGGING set to Pump MODEM")
            # start_pump_modem_thread('COM8')
            run_io_tasks_in_parallel([
                lambda: start_gnss_thread('COM4'),
                lambda: start_pump_modem_thread('COM8'),
            ])
        case _:
            logger.info("Main: Unsupported SELECT_LOGGING type")
