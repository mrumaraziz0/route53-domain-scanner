# Route53 Live Domain Scanner

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-black?logo=flask)
![AWS](https://img.shields.io/badge/AWS-Route53-orange?logo=amazonaws)
![License](https://img.shields.io/badge/License-MIT-green)

**Real-time AWS Route53 domain and subdomain scanner with live status detection, multi-threaded scanning, and professional PDF reporting.**

[Dashboard Preview]

<img width="1540" height="800" alt="image" src="https://github.com/user-attachments/assets/c9db9936-6161-4f6b-87cc-1f35021fe965" />

<img width="1212" height="442" alt="image" src="https://github.com/user-attachments/assets/1aec04e7-e142-40f2-8d52-a02358283ba4" />

[Email Feature]

<img width="1493" height="321" alt="image" src="https://github.com/user-attachments/assets/8edda8ce-5130-418f-bfb1-8f6d675f44fa" />

[Report Sample]

<img width="791" height="481" alt="image" src="https://github.com/user-attachments/assets/8df316ac-4e41-46ac-8147-9d2d652b834a" />

<img width="780" height="797" alt="image" src="https://github.com/user-attachments/assets/178e6500-e902-4476-b8f0-8f11ef45986b" />

<img width="798" height="659" alt="image" src="https://github.com/user-attachments/assets/40be7440-2565-452d-95b8-45ef590a5ac6" />


## ✨ Features

- **Multi-threaded scanning** (faster than sequential)
- **Real-time progress tracking** with live updates
- **Live/Non-Live status detection** for domains & subdomains
- **Professional PDF reports** with 3 specialized charts:
  - Overall status distribution
  - Domain vs Subdomain breakdown
  - Per-domain subdomain analysis
- **Email delivery** of reports
- **Responsive web interface** (works on mobile/desktop)
- **No external dependencies** (pure Python solution)

📊 Report Features
Generated PDF reports include:

Executive summary with key metrics
Overall status distribution pie chart
Domain vs subdomain comparative bar chart
Individual per-domain subdomain analysis charts
Detailed domain/subdomain status table
Professional styling with corporate branding

- 
# In app.py - REPLACE THESE VALUES

**AWS_ACCESS_KEY_ID = "YOUR_ACCESS_KEY"

AWS_SECRET_ACCESS_KEY = "YOUR_SECRET_KEY"

AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"**

**SMTP_SERVER = "smtp.gmail.com"  # Gmail example

EMAIL_USERNAME = "your_email@gmail.com"

EMAIL_PASSWORD = "your_app_password"  # SMTP  Password**



## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/route53-domain-scanner.git
cd route53-domain-scanner

🐧 Linux/Ubuntu Installation Commands
# 1. Update system packages
sudo apt update

# 2. Install system dependencies for WeasyPrint
sudo apt install -y build-essential python3-dev python3-pip libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# 3. Install Python packages
pip install -r requirements.txt

# 4. Verify installation
python -c "from weasyprint import HTML; print('WeasyPrint OK')"

# 5. Verify installation
python3 app.py OR python app.py
🍎 macOS Installation Commands
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install system dependencies
brew install python3 cairo pango gdk-pixbuf libffi

# 3. Install Python packages
pip3 install -r requirements.txt

# 4. Verify installation
python3 -c "from weasyprint import HTML; print('WeasyPrint OK')"

🪟 Windows Installation Commands
# 1. Install Python from https://python.org (check "Add to PATH")

# 2. Install Microsoft C++ Build Tools
#    Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# 3. Install GTK3 runtime
#    Download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

# 4. Install Python packages
pip install -r requirements.txt

# 5. Verify installation
python -c "from weasyprint import HTML; print('WeasyPrint OK')"
