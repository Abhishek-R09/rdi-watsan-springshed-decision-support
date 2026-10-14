"""Local field interface for the connected Project 1 agent runtime."""

from __future__ import annotations

import streamlit as st

from spring_agents.orchestrator import assess


st.set_page_config(page_title="Spring assessment", layout="wide")
st.title("Spring assessment")
st.caption("Catchment-first project prototype. A surface boundary appears only after approved data and routing rules are available.")

with st.form("assessment"):
    mode = st.selectbox("Assessment mode", ["catchment", "springshed"])
    spring_id = st.text_input("Spring ID or name (optional)")
    latitude = st.text_input("Latitude (WGS84 degrees)")
    longitude = st.text_input("Longitude (WGS84 degrees)")
    st.caption("Coordinates are kept as submitted. The system does not move a spring to a stream automatically.")
    st.subheader("Optional bucket readings")
    measurement_date_time = st.text_input("Measurement date and time (include time zone)")
    measurement_conditions = st.text_input("Weather and spring conditions")
    heavy_rainfall_recent = st.selectbox("Could recent heavy rainfall distort the reading?", ["Unknown", "Yes", "No"])
    values = []
    for index in range(3):
        left, right = st.columns(2)
        with left:
            volume = st.text_input(f"Reading {index + 1}: collected volume (L)")
        with right:
            duration = st.text_input(f"Reading {index + 1}: collection time (s)")
        if volume or duration:
            values.append({"volume_L": volume, "time_s": duration})
    submitted = st.form_submit_button("Run assessment")

if submitted:
    submission = {
        "mode": mode,
        "spring_id": spring_id or None,
        "location": {"latitude": latitude, "longitude": longitude, "crs": "EPSG:4326"},
        "field_form": {"bucket_readings": values,
                       "measurement_date_time": measurement_date_time or None,
                       "measurement_conditions": measurement_conditions or None,
                       "heavy_rainfall_recent": {"Yes": True, "No": False}.get(heavy_rainfall_recent)},
    }
    try:
        store, summary = assess(submission)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Assessment could not be saved: {exc}")
    else:
        st.subheader("Result")
        st.write(summary["reason"])
        st.write("Catchment status:", summary["payload"]["surface_catchment_status"])
        st.write("Area (ha):", summary["payload"]["area_ha"] if summary["payload"]["area_ha"] is not None else "Unavailable")
        st.write("Reason:", summary["payload"]["surface_catchment_reason"])
        st.write("Next field check:", summary["payload"]["next_field_check"])
        st.write("Run ID:", store.run_id)
        st.write("Saved outputs:", str(store.directory))
        with st.expander("Recorded data flow and missing links"):
            st.json(store.get("AG-LIN.run_trace")["payload"])
            st.json(store.get("AG-LIN.lineage_issues")["payload"])
        with st.expander("Verification checks"):
            st.json(store.get("AG-VER.verification_report")["payload"])
