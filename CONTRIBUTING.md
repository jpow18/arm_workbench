# Contributing

Keep the core lightweight, task-oriented and simulation-first. New tasks should
implement the small task protocol and include success, stop, timeout and fault tests.
No plugin may expose arbitrary model-generated motor commands or approve human gates.

Run before proposing changes:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests examples
```

Describe simulation and physical verification separately. Hardware patches require
an exact dependency baseline, fake-backed tests, explicit operator-controlled
commissioning steps and documented safety limitations. Do not commit personal
photos, hardware-local configuration, tokens or calibration files.
