from importlib.metadata import distributions
import json
import sys

import streamlit as st

print("DIAGNOSTIC_RUNTIME " + json.dumps({
    "python": sys.version.split()[0], "streamlit": st.__version__,
    "packages": {item.metadata["Name"]: item.version for item in distributions() if item.metadata["Name"]},
}, sort_keys=True), flush=True)
st.title("Boldin Market Risk Explorer")
st.write("Isolated frontend delivery test. No dashboard imports or data-source calls.")
