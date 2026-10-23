# Contributing

Please report the Python version, operating system, exact command, expected result and actual result. Include a tiny synthetic CSV that reproduces the problem; never upload private business data.

For code changes, add a regression test for the observed failure, run `python -m unittest discover -s tests -v`, and explain any changes in CSV semantics. Keep runtime dependencies minimal and preserve original files.

Useful first contributions include reproducible encoding failures, clearer bilingual examples and testing with real export formats after removing personal data. AI-assisted contributions are welcome; the contributor must review and test the result.
