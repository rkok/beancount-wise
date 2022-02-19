Wise importer for Beancount
===========================

Gets transactions from the Wise (formerly TransferWise) API 
and maps them to Beancount transactions.

Supports:

- Multiple profiles (e.g. personal and business)
- Multiple currencies (grabs all)
- Separate postings for transfer fees

## Setup

In your Beancount project dir, create a file called `wise.yaml` and fill in:

```yaml
# The amount of months to go back in history
# Observed maximum is 12 - tweak importer.py to get a different range
nMonths: 1

# Your Wise token (Settings > API tokens)
token: your-token

# Private key from your key pair, required to retrieve account statements
# See: https://api-docs.wise.com/#strong-customer-authentication-personal-token 
privatePemPath: "./wise-private.pem"

# Configuration for your Wise profiles (e.g. personal and business)
# Profile ID can only be found using manual API call AFAIK
# See: https://api-docs.wise.com/#payouts-guide-get-your-profile-id
profiles:
  '12345678':
    account: Assets:Wise:FooAccount
  '90123456':
    account: Assets:Wise:BarAccount

# Optional: account to put transfer fees on
feesAccount: Expenses:Fees:WireTransfer
```

Then, in your Beancount importer config file:

```python
#!/usr/bin/env python3
import os, sys

sys.path.insert(0, os.path.abspath(".")) # <- Yeah, this probably sucks
                                         #    drop me a line if you know a 
                                         #    better way
import bc_wise.importer as wise

CONFIG = [
    wise.Importer()
]
```

## Running

```bash
bean-extract -e ledger.beancount config.py .
```

## Thanks

This was based on the (no longer working) Transferwise importer from [tariochbctools](https://github.com/tarioch/beancounttools)