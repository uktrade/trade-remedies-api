# ADR-00n: ADR Title

## Status

[![Generic badge](https://badgen.net/badge/ADR/approved/green/)](https://github.com/uktrade/trade-remedies-api/adr/README.md)

## Context

There is a requirement to save all emails that the TRS sends to users. This is part of a wider audit chain that will be
used to ensure that the TRS is compliant. We currently use GOV.NOTIFY to send all email communication which only saves
logs for 7 days, this is not enough, we want a permanent record of all emails sent.

The question is how do we achieve this? There are a number of options:

- Save the logs to a database
- Save the logs to a file
- Send copies of emails to a dedicated mailbox

The issue with the first two options is accessibility and ease of access, the email logs would have to be saved in a
custom format which may not be easily understood by humans. The 3rd option avoids this problem by relying on email
clients that are widely used and which most people are comfortable using. It is also the easiest to implement and the
solution with the lowest maintenance cost.

## Decision

We will use Amazon SES to send a copy of all emails sent from the TRS. Amazon SES was chosen as it allows us to send
HTML emails and does not restrict us to using templates like GOV.NOTIFY. This is useful as we want to send carbon copies
of the emails sent to the audit mailbox whilst also prepending metadata
to the emails. This metadata will be used to store various bits of information, like the user
who requested it, the delivery status, and date/time when the email was sent.

## Consequences

- A reliable, secure, and easy to understand audit log is created for all emails sent from the TRS
