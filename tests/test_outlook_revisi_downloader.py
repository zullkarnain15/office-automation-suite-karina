from types import SimpleNamespace

from outlook.downloader import OutlookComClient


class _Recipients:
    def __init__(self, recipients) -> None:
        self._recipients = recipients
        self.Count = len(recipients)

    def Item(self, index: int):
        return self._recipients[index - 1]


def test_cc_resolver_uses_smtp_address_instead_of_display_name() -> None:
    cc_recipient = SimpleNamespace(
        Type=2,
        Name="Kiyan Resto",
        Address="kiyanresto@gmail.com",
        AddressEntry=None,
    )
    to_recipient = SimpleNamespace(
        Type=1,
        Name="Mailbox",
        Address="mailbox@example.com",
        AddressEntry=None,
    )
    item = SimpleNamespace(
        CC="Kiyan Resto",
        Recipients=_Recipients([to_recipient, cc_recipient]),
    )
    client = OutlookComClient("mailbox@example.com")

    assert client._get_cc_emails(item) == "kiyanresto@gmail.com"


def test_cc_resolver_falls_back_to_mailitem_cc_value() -> None:
    item = SimpleNamespace(CC="cc@example.com", Recipients=_Recipients([]))
    client = OutlookComClient("mailbox@example.com")

    assert client._get_cc_emails(item) == "cc@example.com"
