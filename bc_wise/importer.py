from datetime import date, datetime, timezone
from os import path

import dateutil.parser
import requests
import base64
import rsa
import sys

import yaml
from beancount.core import amount, data
from beancount.core.number import D
from beancount.ingest import importer
from dateutil.relativedelta import relativedelta

class Importer(importer.ImporterProtocol):
    """An importer for Transferwise using the API."""
    def identify(self, file):
        return path.basename(file.name) == "wise.yaml"

    def file_account(self, file):
        return ""

    def extract(self, file, existing_entries=None):
        with open(file.name, "r") as f:
            config = yaml.safe_load(f)

        startDate = datetime.combine(
            date.today() + relativedelta(months=-config["nMonths"]), datetime.min.time(), timezone.utc
        ).isoformat()
        endDate = datetime.combine(
            date.today(), datetime.max.time(), timezone.utc
        ).isoformat()

        entries = []

        headers = {"Authorization": "Bearer " + config["token"]}
        r = requests.get("https://api.transferwise.com/v1/profiles", headers=headers)
        profiles = r.json()

        for profile in profiles:
            profileId = profile["id"]
            profileCfg = config["profiles"][str(profileId)]

            if profileCfg is None:
                continue

            r = requests.get(
                "https://api.transferwise.com/v1/borderless-accounts",
                params={"profileId": profileId},
                headers=headers,
            )
            accounts = r.json()
            accountId = accounts[0]["id"]

            for account in accounts[0]["balances"]:
                accountCcy = account["currency"]

                r = self.get_with_sca(
                    f"https://api.transferwise.com/v3/profiles/{profileId}/borderless-accounts/{accountId}/statement.json",
                    params={
                        "currency": accountCcy,
                        "intervalStart": startDate,
                        "intervalEnd": endDate,
                    },
                    headers=headers,
                    private_pem_path=config["privatePemPath"]
                )

                transactions = r.json()

                for transaction in transactions["transactions"]:
                    metakv = {
                        "ref": transaction["referenceNumber"],
                    }
                    meta = data.new_metadata("", 0, metakv)
                    entry = data.Transaction(
                        meta,
                        dateutil.parser.parse(transaction["date"]).date(),
                        "*",
                        "",
                        transaction["details"]["description"],
                        data.EMPTY_SET,
                        data.EMPTY_SET,
                        [
                            data.Posting(
                                profileCfg["account"],
                                amount.Amount(
                                    D(str(transaction["amount"]["value"])),
                                    transaction["amount"]["currency"],
                                ),
                                None,
                                None,
                                None,
                                None,
                            ),
                        ],
                    )
                    entries.append(entry)

        return entries

    def get_with_sca(self, url, params, headers, private_pem_path):
        r = requests.get(url, params=params, headers=headers)

        if r.status_code == 200 or r.status_code == 201:
            return r
        elif r.status_code == 403 and r.headers["x-2fa-approval"] is not None:
            one_time_token = r.headers["x-2fa-approval"]
            signature = self.do_sca_challenge(one_time_token, private_pem_path)
            return self.get_with_sca(
                url,
                params=params,
                headers=dict({
                    "x-2fa-approval": one_time_token,
                    "X-Signature": signature
                }, **headers),
                private_pem_path=private_pem_path
            )
        else:
            print('failed: ', r.status_code)
            print(r.content)
            sys.exit(0)

    def do_sca_challenge(self, one_time_token, private_pem_path):
        # Read the private key file as bytes.
        with open(private_pem_path, 'rb') as f:
            private_key_data = f.read()

        private_key = rsa.PrivateKey.load_pkcs1(private_key_data, 'PEM')

        # Use the private key to sign the one-time-token that was returned
        # in the x-2fa-approval header of the HTTP 403.
        signed_token = rsa.sign(
            one_time_token.encode('ascii'),
            private_key,
            'SHA-256')

        # Encode the signed message as friendly base64 format for HTTP
        # headers.
        signature = base64.b64encode(signed_token).decode('ascii')

        return signature