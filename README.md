# ChangeKeeper - IT Change Management System

A lightweight, secure web application for K–12 IT teams to record, track, and report on operational changes. Built with FastAPI and designed for easy deployment using Docker Compose.

## Features

- **Quick Log** - Log routine changes in 30 seconds (title, category, impact, systems, status)
- **Full Change Wizard** - Guided 4-step form for complex changes with risk assessment and backout plans
- **Smart Escalation** - Selecting "High" impact on a Quick Log auto-expands to full change fields
- **Promotion** - Promote any Quick Log to a Full Change later, preserving the original record
- **Calendar View** - Monthly calendar showing changes color-coded by impact level, click to drill into daily details
- **Microsoft Entra ID (Azure AD) SSO** - Secure authentication using OIDC
- **Google Workspace SSO** - Optional Google sign-in alongside Microsoft
- **Role-based Access Control** - Admin, Auditor, and User roles
- **Search and Filtering** - Find changes by category, system, impact, date, type, etc.
- **PDF Export** - Generate professional change record PDFs
- **CSV Export** - Download reports for date ranges (admin only)
- **Secret Detection** - Prevent accidental credential exposure
- **Audit Logging** - Track all create, edit, promote, and export actions
- **Email Notifications** - Optional email summaries (pluggable module)

## Tech Stack

- **Backend:** FastAPI + Pydantic
- **Database:** PostgreSQL with SQLAlchemy 2.0
- **Templates:** Jinja2 (server-side rendering)
- **Auth:** Authlib (OIDC)
- **PDF:** ReportLab
- **Deployment:** Docker + Docker Compose

## Prerequisites

- Docker and Docker Compose
- Microsoft Entra ID (Azure AD) tenant
- Entra ID App Registration (see setup below)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd changekeeper
cp .env.example .env
```

### 2. Configure Microsoft Entra ID

#### Create App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click "New registration"
3. Name: `ChangeKeeper`
4. Supported account types: `Accounts in this organizational directory only`
5. Redirect URI: `Web` → `http://localhost:8000/auth/callback`
6. Click "Register"

#### Get Credentials

1. Copy **Application (client) ID** → This is your `ENTRA_CLIENT_ID`
2. Copy **Directory (tenant) ID** → This is your `ENTRA_TENANT_ID`
3. Go to "Certificates & secrets" → "New client secret"
4. Description: `ChangeKeeper Secret`
5. Expires: Choose expiration (12-24 months recommended)
6. Copy the **Value** → This is your `ENTRA_CLIENT_SECRET` (save it now, you can't see it again!)

#### Configure API Permissions

1. Go to "API permissions"
2. Click "Add a permission" → "Microsoft Graph" → "Delegated permissions"
3. Add these permissions:
   - `openid`
   - `email`
   - `profile`
   - `User.Read`
   - `GroupMember.Read.All` (if using group-based roles)
4. Click "Grant admin consent" (requires admin privileges)

#### Configure Token Claims (Optional - for group-based roles)

1. Go to "Token configuration"
2. Click "Add groups claim"
3. Select "Security groups"
4. For ID tokens: Check "Group ID"
5. Click "Add"

### 3. Configure Environment Variables

Edit `.env` file:

```env
# Generate a secure secret key
SECRET_KEY=<run: openssl rand -hex 32>

# Microsoft Entra ID Configuration
ENTRA_CLIENT_ID=<your-client-id>
ENTRA_CLIENT_SECRET=<your-client-secret>
ENTRA_TENANT_ID=<your-tenant-id>
REDIRECT_URI=http://localhost:8000/auth/callback

# Database (already configured for Docker Compose)
DATABASE_URL=postgresql://changekeeper_user:changekeeper_password@db:5432/changekeeper

# Email (Optional - leave disabled for MVP)
ENABLE_EMAIL=false
```

### 4. Configure Roles (Optional)

Edit `roles.yaml` to map Entra ID groups to roles:

```yaml
roles:
  admin:
    groups:
      - "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # Admin group Object ID
  
  auditor:
    groups:
      - "f9e8d7c6-b5a4-3210-9876-543210fedcba"  # Auditor group Object ID

default_role: user
```

**How to find Group Object IDs:**
1. Azure Portal → Azure Active Directory → Groups
2. Select your group
3. Copy the "Object ID"

### 5. Start the Application

```bash
# Build and start containers
docker-compose up --build

# The app will be available at http://localhost:8000
```

The application will automatically:
- Start PostgreSQL database
- Run Alembic migrations
- Start the FastAPI application

### 6. Access the Application

1. Open browser to `http://localhost:8000`
2. Click "Sign in with Microsoft"
3. Authenticate with your Microsoft account
4. Start creating change records!

## Production Deployment

### Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Docker and Docker Compose installed
- Domain name with DNS configured
- SSL/TLS certificate (Let's Encrypt recommended)

### Production Setup

1. **Prepare the server:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose -y

# Create application directory
sudo mkdir -p /opt/changekeeper
cd /opt/changekeeper
```

2. **Clone and configure:**

```bash
# Clone repository
git clone <repository-url> .

# Copy and edit environment
cp .env.example .env
nano .env
```

**Production `.env` changes:**
```env
SECRET_KEY=<generate-new-secure-key>
REDIRECT_URI=https://changekeeper.yourdomain.com/auth/callback
# ... other settings
```

3. **Update Entra ID Redirect URI:**

Go to Azure Portal → App registrations → ChangeKeeper → Authentication
- Add redirect URI: `https://changekeeper.yourdomain.com/auth/callback`

4. **Configure reverse proxy (Nginx):**

```nginx
# /etc/nginx/sites-available/changekeeper
server {
    listen 80;
    server_name changekeeper.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name changekeeper.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/changekeeper.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/changekeeper.yourdomain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 10M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/changekeeper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

5. **Start application:**

```bash
# Start in production mode
docker-compose up -d

# Check logs
docker-compose logs -f app
```

6. **Setup automatic backups:**

```bash
# Create backup script
sudo nano /opt/changekeeper/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backup/changekeeper"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T db pg_dump -U changekeeper_user changekeeper | gzip > $BACKUP_DIR/changekeeper_$DATE.sql.gz

# Keep last 30 days
find $BACKUP_DIR -name "changekeeper_*.sql.gz" -mtime +30 -delete
```

```bash
sudo chmod +x /opt/changekeeper/backup.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
# Add: 0 2 * * * /opt/changekeeper/backup.sh
```

### Production Security Checklist

- [ ] SSL/TLS certificate configured
- [ ] Firewall configured (allow only 80, 443, 22)
- [ ] Secret key is unique and secure (32+ random bytes)
- [ ] Database password is strong and unique
- [ ] Regular backups scheduled
- [ ] Server OS is updated regularly
- [ ] Docker images are updated regularly
- [ ] Entra ID app uses production redirect URI
- [ ] Session cookies use `secure` flag (HTTPS only)
- [ ] Rate limiting configured on reverse proxy
- [ ] Monitoring/alerting configured

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Setup local PostgreSQL (or use Docker for DB only)
# Update DATABASE_URL in .env to point to local PostgreSQL

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Create New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Review the generated migration file in alembic/versions/

# Apply migration
alembic upgrade head
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

## Usage Guide

### User Roles

- **User** (default): Can create and view change records
- **Auditor**: Read-only access to all changes
- **Admin**: Full access + CSV export + can edit implementer field

### Quick Log (Routine Changes)

1. Click "Quick Log" in navigation
2. Enter: title, category, impact level, systems affected, status
3. If impact is **High**, additional fields expand automatically (backout plan, detailed description, etc.)
4. Click "Save Quick Log"

Quick logs can be **promoted** to full changes later from the change detail page.

### Full Change (Complex Changes)

1. Click "Full Change" in navigation
2. Complete the 4-step wizard:
   - **Step 1 - Basics:** Title, category, systems, timing, implementer
   - **Step 2 - Risk:** Impact level, user impact, maintenance window, backout plan
   - **Step 3 - Work Details:** What changed, ticket ID, links
   - **Step 4 - Completion:** Status, outcome, post-change issues
3. Review secret detection warnings (if any)
4. Click "Create Change Record"

### Calendar View

1. Click "Calendar" in navigation
2. Browse months with Previous/Next buttons
3. Changes appear as color-coded dots: green (Low), yellow (Medium), red (High)
4. Click any day to see all changes for that date
5. Click a change to view its full detail

### Searching Changes

Use the dashboard filters to search by:
- Text search (title, description, ticket ID)
- Category
- Impact level
- Status
- Change type (Quick Log / Full Change)
- Date range
- Implementer
- System tag

### Exporting Data

**PDF (single change):**
- View change detail page
- Click "Download PDF"

**CSV (date range - admin only):**
- Click "Export CSV" in navigation
- Select date range
- Click "Export"

## Email Configuration (Optional)

To enable email notifications:

1. Edit `.env`:
```env
ENABLE_EMAIL=true
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=changekeeper@yourdomain.com
SMTP_PASSWORD=<app-password>
SMTP_FROM=changekeeper@yourdomain.com
```

2. Restart application:
```bash
docker-compose restart app
```

3. Users can now check "Email me a copy" when creating changes

**Supported SMTP providers:**
- Microsoft 365 / Outlook
- Gmail (use app password)
- SendGrid
- Any standard SMTP server

## Troubleshooting

### Authentication Issues

**"Invalid state parameter"**
- Clear browser cookies and try again
- Verify `REDIRECT_URI` matches exactly in both .env and Azure

**"Invalid nonce"**
- This is usually a timing issue; try again
- Check server clock is synchronized (NTP)

**Users can't log in**
- Verify app permissions granted in Azure
- Check user is in the Entra ID tenant
- Review app logs: `docker-compose logs app`

### Database Issues

**"Database connection failed"**
```bash
# Check database is running
docker-compose ps

# View database logs
docker-compose logs db

# Verify connection
docker-compose exec db psql -U changekeeper_user -d changekeeper
```

**Reset database (⚠️ destroys data):**
```bash
docker-compose down -v
docker-compose up -d
```

### Migration Issues

**"Target database is not up to date"**
```bash
# Check current revision
docker-compose exec app alembic current

# Upgrade to latest
docker-compose exec app alembic upgrade head
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
1. Check this README
2. Review logs: `docker-compose logs`
3. Create an issue in the repository

## Roadmap

Future enhancements:
- [ ] File attachments support
- [ ] Advanced approval workflows
- [ ] Scheduled changes calendar view
- [ ] Custom fields configuration
- [ ] Integration with ticketing systems (ServiceNow, Jira)
- [ ] Mobile app
- [ ] Slack/Teams notifications
- [ ] Change templates
- [ ] Metrics dashboard
- [ ] GraphQL API option
