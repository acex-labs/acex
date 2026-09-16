"""Entry point for `python -m acex_api`.

Delegates to the same main() the `acex-api` console script uses, so both ways of
starting the service behave identically.
"""

from acex_api.server import main

if __name__ == "__main__":
    main()
