-- 0003_departments.sql — the department taxonomy.
--
-- This is schema, not data: the 12 slugs are a closed set (build.md D3) and
-- `description` is fed verbatim into the Phase 3 department-classifier prompt.

CREATE TABLE IF NOT EXISTS departments (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    mailbox      TEXT NOT NULL,
    description  TEXT NOT NULL
);

INSERT INTO departments (id, name, mailbox, description) VALUES
    ('warranty', 'Warranty', 'warranty@example.com',
     'Warranty coverage, claims, repairs and replacements for products still under warranty; warranty period disputes and proof-of-purchase issues.'),
    ('billing', 'Billing', 'billing@example.com',
     'Invoices, duplicate or incorrect charges, refunds, payment failures, subscription and pricing disputes.'),
    ('shipping', 'Shipping', 'shipping@example.com',
     'Delivery delays, lost or damaged-in-transit parcels, wrong address, tracking problems and courier escalations.'),
    ('product_safety', 'Product Safety', 'safety@example.com',
     'Injury, fire, overheating, electrical or chemical hazards, and any recall-related report. Highest urgency; may trigger regulatory duties.'),
    ('returns', 'Returns', 'returns@example.com',
     'Return authorisations, exchanges, restocking fees, return-window exceptions and refund-on-return status.'),
    ('tech_support', 'Technical Support', 'support@example.com',
     'Product not working as expected: setup, configuration, firmware, connectivity, error codes and troubleshooting.'),
    ('qa', 'Quality Assurance', 'qa@example.com',
     'Recurring defects, batch or manufacturing quality patterns, and root-cause investigation of product faults.'),
    ('legal', 'Legal', 'legal@example.com',
     'Legal threats, consumer-rights and regulatory claims, data-protection requests, disputes involving liability or compensation.'),
    ('sales', 'Sales', 'sales@example.com',
     'Pre-sales questions, quotes, order changes, bulk and B2B enquiries, promotions and price-match requests.'),
    ('manufacturing', 'Manufacturing', 'manufacturing@example.com',
     'Production defects traced to a specific plant, batch or component; supply and assembly issues.'),
    ('retention', 'Retention', 'retention@example.com',
     'Cancellation requests, churn risk, goodwill gestures and loyalty or compensation offers to keep a customer.'),
    ('spare_parts', 'Spare Parts', 'parts@example.com',
     'Availability, ordering, compatibility and shipment of replacement parts and accessories.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- RLS — read-only taxonomy; writes are migrations (service role)
-- ---------------------------------------------------------------------------

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS departments_select_all ON departments;
CREATE POLICY departments_select_all ON departments
    FOR SELECT TO authenticated
    USING (true);
