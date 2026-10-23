"""
Mosaic Intelligence — AWS Infrastructure Setup
Creates S3 folder structure, IAM roles, Lambda function, and EventBridge schedules.
Region: us-east-1
"""

import json
import time
import sys
import os
import zipfile
import io

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "mosaic-intelligence-datalake")
LAMBDA_FUNCTION_NAME = os.environ.get("LAMBDA_FUNCTION_NAME", "mosaic-orchestrator-prod")
ACCOUNT_ID = None  # resolved at runtime via STS

# S3 folder prefixes to create
S3_PREFIXES = [
    "raw/source=fred/",
    "raw/source=bls/",
    "raw/source=eia/",
    "raw/source=treasury/",
    "raw/source=bea/",
    "raw/source=data_exchange/",
    "processed/indicators/",
    "processed/derived/",
    "processed/snapshots/",
    "reference/",
    "exports/",
    "custom/",
    "_metadata/ingestion_log/",
    "_metadata/data_quality/",
    "_metadata/glue_jobs/",
    "_athena-results/",
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_account_id():
    global ACCOUNT_ID
    if ACCOUNT_ID is None:
        sts = boto3.client("sts", region_name=REGION)
        ACCOUNT_ID = sts.get_caller_identity()["Account"]
    return ACCOUNT_ID


def step(msg):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print(f"{'─'*60}")


def ok(msg):
    print(f"  [OK] {msg}")


def skip(msg):
    print(f"  [SKIP] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: S3 Bucket & Folder Structure
# ─────────────────────────────────────────────────────────────────────────────

def setup_s3():
    step("S3 Bucket & Folder Structure")
    s3 = boto3.client("s3", region_name=REGION)

    # Check bucket exists
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        ok(f"Bucket '{BUCKET_NAME}' exists")
    except ClientError:
        fail(f"Bucket '{BUCKET_NAME}' not found. Create it first.")
        return False

    # Enable versioning
    try:
        s3.put_bucket_versioning(
            Bucket=BUCKET_NAME,
            VersioningConfiguration={"Status": "Enabled"}
        )
        ok("Versioning enabled")
    except ClientError as e:
        fail(f"Could not enable versioning: {e}")

    # Create folder structure (empty objects as prefixes)
    for prefix in S3_PREFIXES:
        try:
            s3.put_object(Bucket=BUCKET_NAME, Key=prefix, Body=b"")
            ok(f"Created prefix: {prefix}")
        except ClientError as e:
            fail(f"Could not create prefix {prefix}: {e}")

    # Set lifecycle rule: expire Athena results after 7 days
    try:
        s3.put_bucket_lifecycle_configuration(
            Bucket=BUCKET_NAME,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "ExpireAthenaResults",
                        "Filter": {"Prefix": "_athena-results/"},
                        "Status": "Enabled",
                        "Expiration": {"Days": 7},
                    }
                ]
            }
        )
        ok("Lifecycle rule: Athena results expire after 7 days")
    except ClientError as e:
        fail(f"Could not set lifecycle rule: {e}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: IAM Role for Lambda
# ─────────────────────────────────────────────────────────────────────────────

LAMBDA_ROLE_NAME = "mosaic-lambda-execution-role"

LAMBDA_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

LAMBDA_PERMISSIONS_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject",
            ],
            "Resource": [
                f"arn:aws:s3:::{BUCKET_NAME}",
                f"arn:aws:s3:::{BUCKET_NAME}/*",
            ],
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "dataexchange:GetDataSet",
                "dataexchange:ListDataSetRevisions",
                "dataexchange:GetRevision",
                "dataexchange:ListRevisionAssets",
                "dataexchange:GetAsset",
            ],
            "Resource": "*",
        },
    ],
}


def setup_iam():
    step("IAM Role for Lambda")
    iam = boto3.client("iam", region_name=REGION)
    role_arn = None

    # Create role
    try:
        resp = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(LAMBDA_TRUST_POLICY),
            Description="Execution role for Mosaic Intelligence Lambda orchestrator",
        )
        role_arn = resp["Role"]["Arn"]
        ok(f"Created role: {LAMBDA_ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{get_account_id()}:role/{LAMBDA_ROLE_NAME}"
        skip(f"Role already exists: {LAMBDA_ROLE_NAME}")
    except ClientError as e:
        fail(f"Could not create role: {e}")
        return None

    # Attach inline policy
    try:
        iam.put_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyName="mosaic-lambda-permissions",
            PolicyDocument=json.dumps(LAMBDA_PERMISSIONS_POLICY),
        )
        ok("Attached S3 + CloudWatch + DataExchange permissions")
    except ClientError as e:
        fail(f"Could not attach policy: {e}")

    # Also attach basic Lambda execution managed policy
    try:
        iam.attach_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        ok("Attached AWSLambdaBasicExecutionRole managed policy")
    except ClientError as e:
        if "already" in str(e).lower():
            skip("AWSLambdaBasicExecutionRole already attached")
        else:
            fail(f"Could not attach managed policy: {e}")

    return role_arn


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Lambda Function (stub — ready for deployment)
# ─────────────────────────────────────────────────────────────────────────────

LAMBDA_HANDLER_CODE = '''\
"""
Mosaic Intelligence — Lambda Orchestrator
Handles scheduled data pulls from FRED, BLS, EIA, Treasury, BEA.
Triggered by EventBridge schedules.
"""

import json
import os
import urllib.request
import urllib.parse
import boto3
from datetime import datetime


s3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET_NAME", "mosaic-intelligence-datalake")
RAW_PREFIX = os.environ.get("S3_RAW_PREFIX", "raw")

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
BLS_API_KEY = os.environ.get("BLS_API_KEY", "")
EIA_API_KEY = os.environ.get("EIA_API_KEY", "")
BEA_API_KEY = os.environ.get("BEA_API_KEY", "")


def lambda_handler(event, context):
    """
    Event format:
    {
        "source": "fred" | "bls" | "eia" | "treasury" | "bea",
        "series_ids": ["DGS10", "DGS2", ...],   # optional, defaults to all
        "backfill": false,                        # optional
        "start_date": "2000-01-01"                # optional, for backfill
    }
    """
    source = event.get("source", "fred")
    series_ids = event.get("series_ids", [])
    backfill = event.get("backfill", False)
    start_date = event.get("start_date", "2000-01-01")
    today = datetime.now().strftime("%Y-%m-%d")

    results = {"source": source, "date": today, "success": [], "failed": []}

    if source == "fred":
        results = pull_fred(series_ids, start_date if backfill else None, today, results)
    elif source == "bls":
        results = pull_bls(series_ids, results)
    elif source == "eia":
        results = pull_eia(series_ids, results)
    elif source == "treasury":
        results = pull_treasury(results)
    elif source == "bea":
        results = pull_bea(series_ids, results)

    # Write ingestion log
    log_key = f"_metadata/ingestion_log/{source}_{today}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=log_key,
        Body=json.dumps(results, default=str),
        ContentType="application/json",
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "source": source,
            "success_count": len(results["success"]),
            "failed_count": len(results["failed"]),
        }),
    }


def _s3_put(source, series_id, data, today):
    """Write raw JSON to S3 in Hive partition format."""
    year = today[:4]
    key = f"{RAW_PREFIX}/source={source}/series_id={series_id}/year={year}/{series_id}_{today}.json"
    s3.put_object(
        Bucket=BUCKET, Key=key,
        Body=json.dumps(data, default=str),
        ContentType="application/json",
    )
    return key


def _http_get(url, params=None):
    """Simple HTTP GET using urllib (no requests needed in Lambda)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ── FRED ─────────────────────────────────────────────────────────────────────

def pull_fred(series_ids, start_date, today, results):
    base = "https://api.stlouisfed.org/fred/series/observations"
    for sid in series_ids:
        try:
            params = {
                "series_id": sid,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "sort_order": "asc",
                "limit": 100000,
            }
            if start_date:
                params["observation_start"] = start_date
            data = _http_get(base, params)
            _s3_put("fred", sid, data, today)
            results["success"].append(sid)
        except Exception as e:
            results["failed"].append({"series_id": sid, "error": str(e)})
    return results


# ── BLS ──────────────────────────────────────────────────────────────────────

def pull_bls(series_ids, results):
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    today = results["date"]
    # BLS allows up to 50 series per request
    for i in range(0, len(series_ids), 50):
        batch = series_ids[i:i+50]
        try:
            payload = json.dumps({
                "seriesid": batch,
                "startyear": "2000",
                "endyear": str(datetime.now().year),
                "registrationkey": BLS_API_KEY,
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())

            for series in data.get("Results", {}).get("series", []):
                sid = series.get("seriesID", batch[0])
                _s3_put("bls", sid, {"Results": {"series": [series]}}, today)
                results["success"].append(sid)
        except Exception as e:
            for sid in batch:
                results["failed"].append({"series_id": sid, "error": str(e)})
    return results


# ── EIA ──────────────────────────────────────────────────────────────────────

def pull_eia(series_ids, results):
    today = results["date"]
    route_map = {
        "PET.EMM_EPMR_PTE_NUS_DPG.W": ("petroleum/pri/gnd", {"frequency": "weekly", "data[0]": "value", "facets[product][]": "EPM0", "facets[duoarea][]": "NUS"}),
        "PET.EMM_EPD2D_PTE_NUS_DPG.W": ("petroleum/pri/gnd", {"frequency": "weekly", "data[0]": "value", "facets[product][]": "EPD2D", "facets[duoarea][]": "NUS"}),
        "PET.WCESTUS1.W": ("petroleum/stoc/wstk", {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WCESTUS1"}),
        "NG.N3010US3.M": ("natural-gas/pri/sum", {"frequency": "monthly", "data[0]": "value"}),
        "ELEC.PRICE.US-RES.M": ("electricity/retail-sales", {"frequency": "monthly", "data[0]": "price", "facets[sectorid][]": "RES", "facets[stateid][]": "US"}),
    }
    for sid in series_ids:
        try:
            if sid in route_map:
                route, extra = route_map[sid]
            else:
                route, extra = "petroleum/pri/spt", {"frequency": "weekly", "data[0]": "value"}
            params = {"api_key": EIA_API_KEY, "start": "2000-01-01", "length": 5000, **extra}
            data = _http_get(f"https://api.eia.gov/v2/{route}/data/", params)
            _s3_put("eia", sid.replace(".", "_"), data, today)
            results["success"].append(sid)
        except Exception as e:
            results["failed"].append({"series_id": sid, "error": str(e)})
    return results


# ── Treasury ─────────────────────────────────────────────────────────────────

def pull_treasury(results):
    today = results["date"]
    endpoints = {
        "avg_interest_rates": "/v2/accounting/od/avg_interest_rates",
        "debt_to_penny": "/v2/accounting/od/debt_to_penny",
    }
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    for name, path in endpoints.items():
        try:
            params = {"sort": "-record_date", "page[size]": 10000}
            data = _http_get(f"{base}{path}", params)
            _s3_put("treasury", name, data, today)
            results["success"].append(name)
        except Exception as e:
            results["failed"].append({"series_id": name, "error": str(e)})
    return results


# ── BEA ──────────────────────────────────────────────────────────────────────

def pull_bea(series_ids, results):
    today = results["date"]
    base = "https://apps.bea.gov/api/data"
    for table_name in series_ids:
        try:
            params = {
                "UserID": BEA_API_KEY,
                "method": "GetData",
                "DataSetName": "NIPA",
                "TableName": table_name,
                "Frequency": "Q",
                "Year": "ALL",
                "ResultFormat": "JSON",
            }
            data = _http_get(base, params)
            _s3_put("bea", table_name, data, today)
            results["success"].append(table_name)
        except Exception as e:
            results["failed"].append({"series_id": table_name, "error": str(e)})
    return results
'''


def setup_lambda(role_arn):
    step("Lambda Function")

    if not role_arn:
        fail("No IAM role ARN — skipping Lambda creation")
        return False

    lam = boto3.client("lambda", region_name=REGION)

    # Build deployment package in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", LAMBDA_HANDLER_CODE)
    zip_buffer.seek(0)
    zip_bytes = zip_buffer.read()

    # Env vars for the Lambda
    env_vars = {
        "S3_BUCKET_NAME": BUCKET_NAME,
        "S3_RAW_PREFIX": "raw",
        "FRED_API_KEY": os.environ.get("FRED_API_KEY", ""),
        "BLS_API_KEY": os.environ.get("BLS_API_KEY", ""),
        "EIA_API_KEY": os.environ.get("EIA_API_KEY", ""),
        "BEA_API_KEY": os.environ.get("BEA_API_KEY", ""),
    }

    # Wait for role to propagate
    print("  Waiting for IAM role to propagate (10s)...")
    time.sleep(10)

    try:
        lam.create_function(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=300,
            MemorySize=512,
            Environment={"Variables": env_vars},
            Description="Mosaic Intelligence data orchestrator — pulls from FRED/BLS/EIA/Treasury/BEA to S3",
        )
        ok(f"Created Lambda: {LAMBDA_FUNCTION_NAME}")
    except lam.exceptions.ResourceConflictException:
        # Update existing function
        lam.update_function_code(
            FunctionName=LAMBDA_FUNCTION_NAME,
            ZipFile=zip_bytes,
        )
        ok(f"Updated Lambda code: {LAMBDA_FUNCTION_NAME}")
        # Wait for code update to stabilize before updating config
        time.sleep(5)
        try:
            lam.update_function_configuration(
                FunctionName=LAMBDA_FUNCTION_NAME,
                Runtime="python3.12",
                Role=role_arn,
                Handler="lambda_function.lambda_handler",
                Timeout=300,
                MemorySize=512,
                Environment={"Variables": env_vars},
            )
            ok(f"Updated Lambda config: {LAMBDA_FUNCTION_NAME}")
        except ClientError as e:
            fail(f"Could not update Lambda config: {e}")
    except ClientError as e:
        fail(f"Could not create Lambda: {e}")
        return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: EventBridge Schedules
# ─────────────────────────────────────────────────────────────────────────────

# Import the series lists from config
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config as cfg

    FRED_ALL = cfg.get_all_fred_series()
    BLS_ALL = cfg.get_all_bls_series()
    EIA_ALL = cfg.get_all_eia_series()

    # Split FRED by frequency
    FRED_DAILY = []
    FRED_WEEKLY = []
    FRED_MONTHLY = []
    FRED_QUARTERLY = []
    for tab, series_dict in cfg.FRED_INDICATORS.items():
        for sid, meta in series_dict.items():
            freq = meta.get("frequency", "monthly")
            if freq == "daily":
                FRED_DAILY.append(sid)
            elif freq == "weekly":
                FRED_WEEKLY.append(sid)
            elif freq == "quarterly" or freq == "annual":
                FRED_QUARTERLY.append(sid)
            else:
                FRED_MONTHLY.append(sid)
except Exception:
    FRED_ALL = []
    BLS_ALL = []
    EIA_ALL = []
    FRED_DAILY = []
    FRED_WEEKLY = []
    FRED_MONTHLY = []
    FRED_QUARTERLY = []


SCHEDULES = [
    {
        "name": "mosaic-daily-fred",
        "description": "Daily FRED series (yields, spreads, VIX, FX)",
        "schedule": "cron(0 11 ? * MON-FRI *)",  # 6 AM ET (11 UTC)
        "input": {"source": "fred", "series_ids": FRED_DAILY},
    },
    {
        "name": "mosaic-weekly-fred",
        "description": "Weekly FRED series (jobless claims, M2, gas)",
        "schedule": "cron(0 13 ? * FRI *)",  # 8 AM ET Friday
        "input": {"source": "fred", "series_ids": FRED_WEEKLY},
    },
    {
        "name": "mosaic-monthly-fred",
        "description": "Monthly FRED series (CPI, employment, housing)",
        "schedule": "cron(0 12 1 * ? *)",  # 7 AM ET, 1st of month
        "input": {"source": "fred", "series_ids": FRED_MONTHLY},
    },
    {
        "name": "mosaic-quarterly-fred",
        "description": "Quarterly/Annual FRED series (GDP, earnings)",
        "schedule": "cron(0 12 1 1,4,7,10 ? *)",  # 1st of quarter months
        "input": {"source": "fred", "series_ids": FRED_QUARTERLY},
    },
    {
        "name": "mosaic-bls-monthly",
        "description": "BLS series (CPI-U, PPI, employment cost)",
        "schedule": "cron(0 13 1 * ? *)",  # 8 AM ET, 1st of month
        "input": {"source": "bls", "series_ids": BLS_ALL},
    },
    {
        "name": "mosaic-eia-weekly",
        "description": "EIA series (gas, crude, electricity)",
        "schedule": "cron(0 14 ? * WED *)",  # 9 AM ET Wednesday (EIA release day)
        "input": {"source": "eia", "series_ids": EIA_ALL},
    },
    {
        "name": "mosaic-treasury-daily",
        "description": "Treasury yield curve and debt data",
        "schedule": "cron(0 16 ? * MON-FRI *)",  # 11 AM ET
        "input": {"source": "treasury"},
    },
    {
        "name": "mosaic-bea-quarterly",
        "description": "BEA NIPA tables (GDP components)",
        "schedule": "cron(0 12 1 1,4,7,10 ? *)",
        "input": {"source": "bea", "series_ids": ["T20100", "T20305"]},
    },
]


def setup_eventbridge():
    step("EventBridge Schedules")
    events = boto3.client("events", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    # Get Lambda ARN
    try:
        fn = lam.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        lambda_arn = fn["Configuration"]["FunctionArn"]
    except ClientError:
        fail(f"Lambda '{LAMBDA_FUNCTION_NAME}' not found — skipping EventBridge setup")
        return False

    for sched in SCHEDULES:
        rule_name = sched["name"]
        try:
            # Create/update rule
            events.put_rule(
                Name=rule_name,
                ScheduleExpression=sched["schedule"],
                State="ENABLED",
                Description=sched["description"],
            )
            ok(f"Rule: {rule_name} ({sched['schedule']})")

            # Set Lambda as target
            events.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        "Id": f"{rule_name}-target",
                        "Arn": lambda_arn,
                        "Input": json.dumps(sched["input"]),
                    }
                ],
            )

            # Grant EventBridge permission to invoke Lambda
            try:
                lam.add_permission(
                    FunctionName=LAMBDA_FUNCTION_NAME,
                    StatementId=f"eventbridge-{rule_name}",
                    Action="lambda:InvokeFunction",
                    Principal="events.amazonaws.com",
                    SourceArn=f"arn:aws:events:{REGION}:{get_account_id()}:rule/{rule_name}",
                )
            except ClientError as e:
                if "already exists" in str(e).lower():
                    pass  # Permission already granted
                else:
                    fail(f"Could not add invoke permission for {rule_name}: {e}")

        except ClientError as e:
            fail(f"Could not create rule {rule_name}: {e}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Glue Catalog (Athena queryability)
# ─────────────────────────────────────────────────────────────────────────────

def setup_glue():
    step("Glue Catalog (for Athena queries)")
    glue = boto3.client("glue", region_name=REGION)

    db_name = "mosaic_intelligence"

    # Create database
    try:
        glue.create_database(
            DatabaseInput={
                "Name": db_name,
                "Description": "Mosaic Intelligence economic data lake",
            }
        )
        ok(f"Created Glue database: {db_name}")
    except glue.exceptions.AlreadyExistsException:
        skip(f"Glue database '{db_name}' already exists")
    except ClientError as e:
        fail(f"Could not create Glue database: {e}")
        return False

    # Create table for raw FRED data
    try:
        glue.create_table(
            DatabaseName=db_name,
            TableInput={
                "Name": "raw_fred",
                "Description": "Raw FRED API responses (Hive-partitioned)",
                "StorageDescriptor": {
                    "Columns": [
                        {"Name": "observations", "Type": "array<struct<date:string,value:string>>"},
                    ],
                    "Location": f"s3://{BUCKET_NAME}/raw/source=fred/",
                    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    "SerdeInfo": {
                        "SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe",
                    },
                },
                "PartitionKeys": [
                    {"Name": "series_id", "Type": "string"},
                    {"Name": "year", "Type": "string"},
                ],
                "TableType": "EXTERNAL_TABLE",
            },
        )
        ok("Created Glue table: raw_fred")
    except glue.exceptions.AlreadyExistsException:
        skip("Glue table 'raw_fred' already exists")
    except ClientError as e:
        fail(f"Could not create Glue table: {e}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Mosaic Intelligence — Infrastructure Setup")
    print(f"  Region: {REGION}")
    print(f"  Bucket: {BUCKET_NAME}")
    print(f"  Lambda: {LAMBDA_FUNCTION_NAME}")
    print("=" * 60)

    # Verify credentials
    try:
        acct = get_account_id()
        ok(f"AWS Account: {acct}")
    except Exception as e:
        fail(f"Could not verify AWS credentials: {e}")
        sys.exit(1)

    # Run setup steps
    s3_ok = setup_s3()
    role_arn = setup_iam()
    lambda_ok = setup_lambda(role_arn)
    eventbridge_ok = setup_eventbridge()
    glue_ok = setup_glue()

    # Summary
    step("Setup Summary")
    print(f"  S3 Bucket:    {'OK' if s3_ok else 'FAILED'}")
    print(f"  IAM Role:     {'OK' if role_arn else 'FAILED'}")
    print(f"  Lambda:       {'OK' if lambda_ok else 'FAILED'}")
    print(f"  EventBridge:  {'OK' if eventbridge_ok else 'FAILED'}")
    print(f"  Glue:         {'OK' if glue_ok else 'FAILED'}")
    print()

    if all([s3_ok, role_arn, lambda_ok, eventbridge_ok, glue_ok]):
        print("  All infrastructure components deployed successfully!")
        print(f"\n  Next steps:")
        print(f"    1. Run a test invocation:")
        print(f'       aws lambda invoke --function-name {LAMBDA_FUNCTION_NAME} \\')
        print(f'         --payload \'{{"source": "fred", "series_ids": ["DGS10"]}}\' \\')
        print(f'         /tmp/lambda-output.json && cat /tmp/lambda-output.json')
        print(f"    2. Check S3 for data: aws s3 ls s3://{BUCKET_NAME}/raw/source=fred/")
        print(f"    3. Run full backfill when ready")
    else:
        print("  Some components failed — check errors above.")


if __name__ == "__main__":
    main()
