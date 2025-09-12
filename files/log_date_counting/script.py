import random
import datetime
import uuid
from faker import Faker

# Initialize Faker for generating realistic fake data
fake = Faker()

# --- Configuration ---
LOG_FILE_PATH = "benchmark_log.log"
NUMBER_OF_LINES = 5000

# --- Data Pools for Realistic Logs ---
LOG_LEVELS = {
    "INFO": 0.60,
    "DEBUG": 0.20,
    "WARNING": 0.12,
    "ERROR": 0.07,
    "CRITICAL": 0.01
}
COMPONENTS = ["AuthService", "DatabaseConnector", "APIGateway", "BillingWorker", "CacheManager", "FrontendApp", "TaskScheduler"]
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
HTTP_STATUS_CODES = [200, 201, 204, 400, 401, 403, 404, 500, 503]
USER_ACTIONS = ["login_success", "login_failed", "profile_update", "item_purchased", "password_reset_request", "form_submission"]

# --- 1. Real Date Format Generators ---
# A list of diverse Python strftime formats for dates
REAL_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S,%f",          # 2023-10-27 14:35:01,334
    "%d/%b/%Y:%H:%M:%S %z",          # 27/Oct/2023:14:35:01 +0000 (Apache Log)
    "%b %d, %Y, %I:%M:%S %p",        # Oct 27, 2023, 02:35:01 PM
    "%Y-%m-%dT%H:%M:%S.%fZ",         # 2023-10-27T14:35:01.334567Z (ISO 8601)
    "%a %b %d %H:%M:%S %Y",          # Fri Oct 27 14:35:01 2023 (ctime format)
    "%m-%d-%Y %H:%M",                # 10-27-2023 14:35
    "[%Y/%m/%d] %H:%M:%S",           # [2023/10/27] 14:35:01
    "Date: %A, %B %d, %Y",           # Date: Friday, October 27, 2023
]

def get_random_timestamp():
    """Generates a random datetime object from the past year."""
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = datetime.timedelta(days=random.randint(0, 365), hours=random.randint(0, 24), seconds=random.randint(0, 86400))
    return now - delta

def generate_line_with_real_date():
    """(Type 1) A log line that definitely contains a date."""
    level = random.choices(list(LOG_LEVELS.keys()), list(LOG_LEVELS.values()))[0]
    date_format = random.choice(REAL_DATE_FORMATS)
    timestamp_str = get_random_timestamp().strftime(date_format)
    message = fake.sentence(nb_words=10)
    return f"{timestamp_str} [{level}] {message}"

# --- 2. Deceptive Non-Date Format Generators ---
# These functions generate strings that might be confused for dates by a weak parser.

def generate_line_with_version_number():
    """(Type 2) Looks like a date, but it's a version number."""
    version = f"v{random.randint(2020, 2024)}.{random.randint(1, 12)}.{random.randint(1, 28)}"
    return f"INFO: System updated to version {version}. Restarting services."

def generate_line_with_transaction_id():
    """(Type 3) A transaction ID with date-like components."""
    date_part = get_random_timestamp().strftime("%Y-%m-%d")
    id_part = fake.hexify(text="^^^^^^^^")
    return f"CRITICAL: Transaction {date_part}-{id_part} failed due to insufficient funds."

def generate_line_with_build_id():
    """(Type 4) A build ID in YYYYMMDD.build format."""
    build_id = f"{get_random_timestamp().strftime('%Y%m%d')}.{random.randint(1, 5)}"
    return f"DEBUG: Starting CI build {build_id} for branch 'main'."

def generate_line_with_ip_and_port():
    """(Type 5) An IP address that could be misread as DD.MM.YY.YY."""
    ip = f"{random.randint(1,28)}.{random.randint(1,12)}.{random.randint(20,24)}.{random.randint(1,254)}"
    return f"WARNING: Unrecognized connection attempt from {ip}:{random.randint(1024, 65535)}"

def generate_line_with_file_path():
    """(Type 6) A file path structured like a date."""
    path = f"/var/logs/archive/{get_random_timestamp().strftime('%Y/%m/%d')}/app.log.gz"
    return f"INFO: Log rotation complete. Archived log to {path}"

def generate_line_with_product_sku():
    """(Type 7) A product SKU that looks like DD-MM-YYYY-CODE."""
    sku = f"{random.randint(1,31):02d}-{random.randint(1,12):02d}-{random.randint(2022,2024)}-{fake.lexify(text='??').upper()}"
    return f"DEBUG: Inventory check for SKU: {sku}"

def generate_line_with_metric_values():
    """(Type 8) Performance metrics that use slashes."""
    metrics = f"{random.uniform(0.1, 5.0):.2f}/{random.uniform(5.0, 15.0):.2f}/{random.uniform(15.0, 30.0):.2f}"
    return f"INFO: System load average: {metrics} (1m/5m/15m)"
    
def generate_line_with_event_count():
    """(Type 9) A sentence where numbers could be parsed as a date."""
    date_like_num = f"{random.randint(2000, 3000)}-{random.randint(1,12)}-{random.randint(1,28)}"
    return f"INFO: Processed {date_like_num} events in the last cycle."

# --- 3. General Realistic Log Line Generators ---

def generate_standard_log_line():
    """(Type 10) A very common log format."""
    level = random.choices(list(LOG_LEVELS.keys()), list(LOG_LEVELS.values()))[0]
    component = random.choice(COMPONENTS)
    message = fake.sentence(nb_words=8)
    return f"[{level}] [{component}] {message}"

def generate_api_access_log():
    """(Type 11) An NGINX/Apache-style access log."""
    ip = fake.ipv4()
    user_id = f"user-{random.randint(1000, 9999)}"
    method = random.choice(HTTP_METHODS)
    path = fake.uri_path()
    status = random.choice(HTTP_STATUS_CODES)
    response_time = random.randint(15, 1500)
    return f'{ip} - {user_id} "{method} {path} HTTP/1.1" {status} {response_time}ms'

def generate_user_action_log():
    """(Type 12) A log tracking a specific user action."""
    user = fake.user_name()
    action = random.choice(USER_ACTIONS)
    session_id = uuid.uuid4()
    return f"AUDIT: User '{user}' performed action '{action}'. SessionID: {session_id}"

def generate_database_query_log():
    """(Type 13) A log showing a DB query execution."""
    duration = random.uniform(0.5, 250.0)
    table = random.choice(['users', 'products', 'orders', 'sessions'])
    return f"DEBUG: [DatabaseConnector] Executed query on table '{table}' in {duration:.2f}ms"

def generate_service_startup_log():
    """(Type 14) A log indicating a service is starting."""
    component = random.choice(COMPONENTS)
    port = random.randint(3000, 9000)
    return f"INFO: {component} starting up on port {port}..."

def generate_json_log():
    """(Type 15) A structured log in JSON format."""
    level = random.choices(list(LOG_LEVELS.keys()), list(LOG_LEVELS.values()))[0]
    return f'{{"level": "{level.lower()}", "message": "{fake.sentence()}", "trace_id": "{uuid.uuid4()}"}}'

def generate_cache_log():
    """(Type 16) A log related to cache operations."""
    operation = random.choice(['HIT', 'MISS', 'SET', 'EVICT'])
    key = fake.md5()
    return f"DEBUG: [CacheManager] Cache {operation} for key: {key}"

def generate_task_scheduler_log():
    """(Type 17) A log from a background job scheduler."""
    job_id = f"job-{random.randint(10000, 99999)}"
    status = random.choice(['started', 'completed successfully', 'failed'])
    return f"INFO: [TaskScheduler] Job {job_id} {status}."

def generate_security_alert_log():
    """(Type 18) A security-related log."""
    ip = fake.ipv4()
    return f"CRITICAL: [AuthService] Multiple failed login attempts detected from IP: {ip}. Temporarily blocking."
    
def generate_deprecation_warning():
    """(Type 19) A warning about using an old feature."""
    endpoint = f"/api/v{random.randint(1,2)}/{random.choice(['users', 'data', 'metrics'])}"
    new_endpoint = endpoint.replace('/v1/', '/v2/').replace('/v2/', '/v3/')
    return f"WARNING: Deprecated endpoint {endpoint} was called. Please use {new_endpoint} instead."

def generate_resource_usage_log():
    """(Type 20) A log detailing system resource usage."""
    cpu = f"{random.uniform(5.0, 95.0):.1f}%"
    mem = f"{random.randint(256, 8192)}MB"
    return f"DEBUG: System resource usage: CPU at {cpu}, Memory at {mem}."
    
def generate_generic_error_stacktrace():
    """(Type 21) A line that might precede a stack trace."""
    error_type = random.choice(["NullPointerException", "ValueError", "KeyError", "ConnectionRefusedError"])
    return f"ERROR: Unhandled exception caught: {error_type} in {random.choice(COMPONENTS)}."
    
def generate_kv_log():
    """(Type 22) A log line with key-value pairs."""
    user = fake.user_name()
    duration = random.randint(10, 500)
    return f"INFO: User profile loaded for user={user} duration_ms={duration}"

# --- Main Script Logic ---

def generate_log_file(filepath, num_lines):
    """Generates the log file with a mix of different log line types."""
    
    # List of all the generator functions we created
    line_generators = [
        # Real Dates (should appear reasonably often)
        generate_line_with_real_date,
        generate_line_with_real_date,
        generate_line_with_real_date,
        # Deceptive Non-Dates (the challenging part)
        generate_line_with_version_number,
        generate_line_with_transaction_id,
        generate_line_with_build_id,
        generate_line_with_ip_and_port,
        generate_line_with_file_path,
        generate_line_with_product_sku,
        generate_line_with_metric_values,
        generate_line_with_event_count,
        # General Realistic Logs (to create noise and variety)
        generate_standard_log_line,
        generate_standard_log_line,
        generate_api_access_log,
        generate_user_action_log,
        generate_database_query_log,
        generate_service_startup_log,
        generate_json_log,
        generate_cache_log,
        generate_task_scheduler_log,
        generate_security_alert_log,
        generate_deprecation_warning,
        generate_resource_usage_log,
        generate_generic_error_stacktrace,
        generate_kv_log
    ]
    
    print(f"Generating {num_lines} log lines into '{filepath}'...")
    
    with open(filepath, "w") as f:
        for i in range(num_lines):
            # Pick a random generator function and call it
            generator_func = random.choice(line_generators)
            log_line = generator_func()
            f.write(log_line + "\n")
            
            # Occasionally add a multi-line stack trace for realism
            if "ERROR" in log_line and random.random() < 0.3:
                f.write(f"\t at com.{fake.word()}.{fake.word()}.{random.choice(COMPONENTS)}({fake.word()}.java:{random.randint(20, 500)})\n")
                f.write(f"\t at com.{fake.word()}.{fake.word()}.Service({fake.word()}.java:{random.randint(20, 500)})\n")


    print("Log file generation complete.")


if __name__ == "__main__":
    generate_log_file(LOG_FILE_PATH, NUMBER_OF_LINES)