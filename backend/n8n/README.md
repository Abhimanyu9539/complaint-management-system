# Incoming email

n8n reads the support mailbox and posts each message to `POST /api/v1/emails/inbound`.
It makes no decisions and stores nothing: the API decides whether an email is a new
complaint, a department's answer, a customer's reply, or something to ignore, and records
every email in `inbound_emails`.

```
GreenMail (IMAP, support@example.com)
  └─ n8n: Email Trigger (IMAP) → Normalise → Post to API (X-Inbound-Secret)
       └─ POST /api/v1/emails/inbound
```

In development, GreenMail is the inbox and Mailpit still catches everything the API
sends, so the two are separate mailboxes. In production they are the same shared one.

## Setup

1. **Pick a secret** and put it in `backend/.env`. The API and docker compose both read it
   from there:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # INBOUND_EMAIL_SECRET=<that value>
   ```

   Restart the API. Until the secret is set, the endpoint answers 503.

2. **Apply migration** `backend/supabase/migrations/0026_inbound_emails.sql`.

3. **Start the services** from `backend/`: `docker compose up -d greenmail n8n`.

4. **Import the workflow:** open http://localhost:5678, create the owner account, then
   *Workflows → Import from file →* `backend/n8n/inbound-email.json`.

5. **Add the IMAP credential** (credentials are not exported): open *Email Trigger (IMAP)*,
   create a new credential with host `greenmail`, port `3143`, user `support`, password
   `password`, and SSL/TLS off.

6. **Publish** the workflow.

## Try it

Write an email to a file and send it to GreenMail. Keep the `Message-ID`: the API
needs one, and it is how a re-posted email is recognised as a duplicate.

```bash
cat > complaint.eml <<'EOF'
From: Triage Test <triage.test@example.com>
To: support@example.com
Subject: [TEST] Kettle stopped heating
Message-ID: <test-1@example.com>

My kettle stopped heating after two weeks. Order 12345.
EOF

curl smtp://localhost:3025 --mail-from triage.test@example.com \
  --mail-rcpt support@example.com --upload-file complaint.eml
```

A ticket with source `email` appears in the workbench and gets drafted. To answer as a
department, send from its mailbox (e.g. `safety@example.com`) with `[T-n]` in the subject;
to reply as the customer, send from the ticket's address with `[T-n]` in the subject.

## Good to know

- Messages already in the mailbox when the workflow is published are picked up when the
  next one arrives.
- Each message is marked read when n8n fetches it. If the API stays down through the three
  retries, re-run the failed execution from *Executions*, or mark the message unread.
- A failure after the API has recorded the email is not retried (a retry is a duplicate);
  the row in `inbound_emails` holds the error.
