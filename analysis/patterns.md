# App Research Patterns

- oauth2 is the most common auth method (65 mentions).
- 37 of 100 apps are gated beyond free/trial access.
- Top blocker: paid plan required (18 apps).
- 50 apps look like easy toolkit wins.
- 9 apps likely need outreach or partnership access.

## Auth Method Distribution

- oauth2: 65
- token: 65
- other: 26
- api_key: 16
- basic: 14

## Access Tier Distribution

- self_serve_free: 56
- paid_plan_required: 20
- admin_approval_required: 12
- self_serve_trial: 7
- partner_gated_contact_sales: 5

## Top Blockers

- paid plan required: 18 apps (Pipedrive, Freshdesk, Pylon, Plain, Help Scout)
- auth/access setup ambiguity: 13 apps (LiveAgent, Lark (Larksuite), Google Ads, systeme.io, Magento (Adobe Commerce))
- partner/contact-sales or approval gate: 12 apps (Salesforce, Copper, Gladly, LinkedIn Ads, Meta Ads)

## Easy Wins

- Fathom (AI, Research and Media-native)
- Reducto (AI, Research and Media-native)
- YouTube Transcript (AI, Research and Media-native)
- Attio (CRM and Sales)
- Close (CRM and Sales)
- HubSpot (CRM and Sales)
- Podio (CRM and Sales)
- Twenty (CRM and Sales)
- Zoho CRM (CRM and Sales)
- Discord (Communications and Messaging)
- Pumble (Communications and Messaging)
- Slack (Communications and Messaging)
- Telegram (Communications and Messaging)
- Twilio (Communications and Messaging)
- Vonage (Communications and Messaging)
- WhatsApp Business (Communications and Messaging)
- Zoho Cliq (Communications and Messaging)
- Apify (Data, SEO and Scraping)
- Bright Data (Data, SEO and Scraping)
- DataForSEO (Data, SEO and Scraping)
- Firecrawl (Data, SEO and Scraping)
- MrScraper (Data, SEO and Scraping)
- Datadog (Developer, Infra and Data platforms)
- GitHub (Developer, Infra and Data platforms)
- MongoDB Atlas (Developer, Infra and Data platforms)
- Neo4j (Developer, Infra and Data platforms)
- Netlify (Developer, Infra and Data platforms)
- Sentry (Developer, Infra and Data platforms)
- Supabase (Developer, Infra and Data platforms)
- Vercel (Developer, Infra and Data platforms)
- BigCommerce (Ecommerce)
- Gumroad (Ecommerce)
- Shopify (Ecommerce)
- WooCommerce (Ecommerce)
- Brex (Finance and Fintech)
- Stripe (Finance and Fintech)
- iPayX (Finance and Fintech)
- Klaviyo (Marketing, Ads, Email and Social)
- Mailchimp (Marketing, Ads, Email and Social)
- SendGrid (Marketing, Ads, Email and Social)
- Airtable (Productivity and Project Management)
- Asana (Productivity and Project Management)
- ClickUp (Productivity and Project Management)
- Coda (Productivity and Project Management)
- Harvest (Productivity and Project Management)
- Jira (Productivity and Project Management)
- Linear (Productivity and Project Management)
- Notion (Productivity and Project Management)
- Front (Support and Helpdesk)
- Intercom (Support and Helpdesk)

## Needs Outreach

- Otter AI (AI, Research and Media-native): API access appears restricted to the Enterprise plan, requiring paid upgrade/sales motion before building against the official API.
- Copper (CRM and Sales): OAuth app registration appears to require contacting Copper via partners@copper.com, though API-key access is documented for paid customers.
- Salesforce (CRM and Sales): Public developer docs and OAuth-based API documentation are available, but practical toolkit coverage depends on having a suitable Salesforce edition/org with API access rather than universally available free self-serve access.
- Waterfall.io (Data, SEO and Scraping): API access appears to require sales/contact-gated onboarding rather than a verifiable self-serve developer signup flow.
- Salesforce Commerce Cloud (Ecommerce): Public developer docs and documented OAuth-based auth exist, but tenant/product access appears enterprise-oriented rather than clearly self-serve from the evidence gathered, so toolkit development likely requires an existing Commerce Cloud environment or manual enterprise setup.
- Paygent Connect (Finance and Fintech): Toolkit build appears possible against underlying NMI APIs, but the exact official Paygent Connect first-party app identity, access path, and branded API scope were not verified from gathered evidence.
- PitchBook (Finance and Fintech): No self-serve developer access or documented authentication details were found in the gathered first-party evidence, so building a reliable toolkit today appears blocked by sales-gated access and thin public technical docs.
- Plaid (Finance and Fintech): Public docs and self-serve sandbox are sufficient to prototype, but production use and some higher tiers appear to involve sales-gated plans, and MCP availability was not verified on a first-party Plaid page.
- Gladly (Support and Helpdesk): Sales-gated platform access/pricing means a first toolkit appears technically feasible from the public REST docs, but practical build access likely requires manual vendor engagement.
