# adomi-san-bot

This is Adomi-san, a Discord bot to help streamline and automate workflows for managing netplay brackets run via start.gg.

But you can call her Adomin-tan ~☆！

Click [here](https://discord.com/oauth2/authorize?client_id=1388611843655860254&scope=bot%20applications.commands&permissions=580963046644800) to invite her over!

## Testing

### Local Testing

To test locally, run `make test` in your command line.

Here is how the Makefile sets up and runs unit tests. The [unit test workflow](./.github/workflows/workflow-run-unit-tests.yml) uses these same steps to verify unit tests pass before deployment.

1. Create virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate    # Windows
   ```
2. Run `pip install setuptools` if you have not already installed `setuptools`
3. Install dependencies with `pip install -r requirements.txt` and `pip install -r requirements-dev.txt`
4. Set PYTHONPATH: `export PYTHONPATH="$PYTHONPATH:$(pwd)/src"`
   - Windows: `$env:PYTHONPATH="$env:PYTHONPATH;${PWD}\src"`
5. Run tests with `pytest tests/`
