"""
MODULE: ac_store
GOAL: AC Traceability Store utility scripts — importable Python package marker.
BUSINESS CONTEXT: Marks scripts/ac_store/ as a valid Python package so that
    consumer projects can import modules from this directory after leafcutter
    deploys it via build_ac_store_scripts() in build_phases.py.
ARCHITECTURE: Empty package init. All executable logic lives in the sibling
    modules (ac_prioritizer, generate_ticket_from_ac, scan_ac_store, etc.).
    Deployed verbatim to {consumer}/.leafcutter/scripts/ac_store/ by build.py;
    a directory shim at {consumer}/scripts/ac_store/ points into this location
    so agent templates can import from 'scripts/ac_store' on sys.path.
"""
