# R3 debug-from-failure: read the traceback, fix, re-test

Run the suite, observe the FAIL, read `app.py`, fix the off-by-one,
re-run until green. The transcript must show FAIL then PASS.
