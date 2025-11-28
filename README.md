# adomi-san-bot

This is Adomi-san, a Discord bot to help streamline and automate workflows for managing netplay brackets run via start.gg.

But you can call her Adomin ~☆！

## Contributing

### Adding Commands

The [commands/](./src/commands/) directory is organized by groups of commands. **Create a directory for the set of commands you are working on, or find the existing directory and add to it.**

[command_map.py](./src/commands/command_map.py) combines [CommandMapping](./src/commands/models/command_mapping.py) dicts from each set of commands' mapping.py file to build the full set of commands.

**Run the `register-commands` workflow via GH Actions workflow dispatch to register new commands with discord**. The [register_commands script](./scripts/register_commands.py) will discover commands via command_map.py and call Discord's API to register them.

Here is an example of the structure of a command mapping using a fully-populated entry:

```python
"command-name": { # kebab-case standard for readability in Discord
   "function": commands.my_command_function, # function ref
   "description": "Describe your function",
   "params": [
      CommandParam(
            name="param_name", # snake_case is standard
            description="Param description",
            param_type=AppCommandOptionType.boolean, # from Discord.py library
            required=False,
            choices=[
               # Provide a ParamChoice for each dropdown choice you want.
               ParamChoice(name="Yes", value=True),
               ParamChoice(name="No", value=False)
            ]
      )
   ]
}
```

For more information, look in the [commands/models/](./src/commands/models/) directory.

### Adding AWS Services

Most functions of this bot will just need DynamoDB. In case you need something else (like an SQS Queue), add on to [AWSServices](./src/aws_services.py), which is passed as a parameter to every command.

This enables us to mock AWS service behavior in tests while initializing connections on Lambda startup to minimize impact on cold start and execution times. **Discord assumes your bot failed if it does not respond to interaction requests within 3 seconds.**

Terraform is used for provisioning for all parts of this bot. Update [terraform/](./terraform/) and [the GitHub Actions workflows](./.github/workflows/) as needed for new services. Make sure to do the following as well:

- Add config variables to [config.env](./config.env) and [variables.tf](./terraform/variables.tf) as needed
- Update `read-config` in the [pipelines](./.github/workflows/development.yml) as needed to read these variables
  - Single Source of Truth is implemented for config vars py passing them via environment variables and terraform variables
- Read any relevant config vars through [constants.py](./src/constants.py)

**In general, you can follow examples already in the code around these files for reference.**

## Testing

### Unit Tests

As of 11/16/2025, unit tests are based on auto-generated tests from ChatGPT. For a bot with simple functionality like this, unit tests are code sanity tests while the main testing will be integration testing thru the bot itself.

Make a practice of implementing at least basic unit tests to verify we do not break the most basic functionality with updates.

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
