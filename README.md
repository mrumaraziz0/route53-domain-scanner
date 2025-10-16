# Route53 Domain Scanner

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-black?logo=flask)
![AWS](https://img.shields.io/badge/AWS-Route53-orange?logo=amazonaws)
![License](https://img.shields.io/badge/License-MIT-green)

**Real-time AWS Route53 domain and subdomain scanner with live status detection, multi-threaded scanning, and professional PDF reporting.**

![Dashboard Preview](screenshots/dashboard.png)
![Report Sample](screenshots/report_sample.png)

## ✨ Features

- **Multi-threaded scanning** (10x faster than sequential)
- **Real-time progress tracking** with live updates
- **Live/Non-Live status detection** for domains & subdomains
- **Professional PDF reports** with 3 specialized charts:
  - Overall status distribution
  - Domain vs Subdomain breakdown
  - Per-domain subdomain analysis
- **Email delivery** of reports
- **Responsive web interface** (works on mobile/desktop)
- **No external dependencies** (pure Python solution)

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/route53-domain-scanner.git
cd route53-domain-scanner
