from flask import Flask, render_template_string, jsonify, send_file, request
import boto3
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Use WeasyPrint for reliable PDF generation
try:
    from weasyprint import HTML
    USE_WEASYPRINT = True
except ImportError:
    print("⚠️  WeasyPrint not installed. Install with: pip install weasyprint")
    USE_WEASYPRINT = False

app = Flask(__name__)

# Your AWS credentials
AWS_ACCESS_KEY_ID = "REPLACE WITH YOUR KEY"
AWS_SECRET_ACCESS_KEY = "REPLACE WITH YOUR KEY"
AWS_SESSION_TOKEN = "REPLACE WITH YOUR KEY"

# Email configuration (UPDATE THESE!)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USERNAME = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"

# Global scan state
scan_state = {
    'status': 'idle',
    'domains': [],
    'total_zones': 0,
    'processed_zones': 0,
    'error': None
}
scan_lock = threading.Lock()

def is_live(domain):
    try:
        socket.setdefaulttimeout(2)
        socket.gethostbyname(domain)
        return True
    except:
        return False

def scan_single_domain(zone):
    domain = zone['Name'].rstrip('.')
    domain_live = is_live(domain)
    
    client = boto3.client(
        'route53',
        region_name='us-east-1',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN
    )
    
    records = client.list_resource_record_sets(
        HostedZoneId=zone['Id'],
        MaxItems='50'
    )
    
    subdomains = []
    for rec in records['ResourceRecordSets']:
        name = rec['Name'].rstrip('.')
        if name != domain:
            subdomains.append({
                'name': name,
                'live': is_live(name)
            })
    
    return {
        "domain": domain,
        "live": domain_live,
        "subdomains": sorted(subdomains, key=lambda x: x['name'])
    }

def background_scan():
    global scan_state
    with scan_lock:
        scan_state.update({
            'status': 'scanning',
            'domains': [],
            'total_zones': 0,
            'processed_zones': 0,
            'error': None
        })
    
    try:
        client = boto3.client(
            'route53',
            region_name='us-east-1',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN
        )
        
        zones = client.list_hosted_zones()['HostedZones']
        total = len(zones)
        
        with scan_lock:
            scan_state['total_zones'] = total
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            future_to_zone = {executor.submit(scan_single_domain, zone): zone for zone in zones}
            
            for future in as_completed(future_to_zone):
                try:
                    result = future.result()
                    with scan_lock:
                        scan_state['domains'].append(result)
                        scan_state['processed_zones'] += 1
                except Exception as e:
                    print(f"Error scanning domain: {e}")
        
        with scan_lock:
            scan_state['status'] = 'completed'
            
    except Exception as e:
        with scan_lock:
            scan_state['status'] = 'error'
            scan_state['error'] = str(e)

def generate_overall_status_chart(domains):
    if not domains:
        return ""
        
    all_items = []
    for d in domains:
        all_items.append(d['live'])
    for d in domains:
        for sub in d['subdomains']:
            all_items.append(sub['live'])
    
    live_count = sum(all_items)
    non_live_count = len(all_items) - live_count
    
    plt.figure(figsize=(8, 6))
    plt.pie([live_count, non_live_count], 
            labels=['Live', 'Non-Live'], 
            colors=['#28a745', '#dc3545'],
            autopct='%1.1f%%',
            startangle=90)
    plt.title('Overall Status Distribution', fontsize=14, pad=20)
    
    img = io.BytesIO()
    plt.savefig(img, format='PNG', bbox_inches='tight', dpi=150)
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf-8')

def generate_domain_breakdown_chart(domains):
    if not domains:
        return ""
    
    domain_lives = sum(1 for d in domains if d['live'])
    domain_deads = sum(1 for d in domains if not d['live'])
    sub_lives = sum(1 for d in domains for s in d['subdomains'] if s['live'])
    sub_deads = sum(1 for d in domains for s in d['subdomains'] if not s['live'])
    
    labels = ['Live Domains', 'Non-Live Domains', 'Live Subdomains', 'Non-Live Subdomains']
    sizes = [domain_lives, domain_deads, sub_lives, sub_deads]
    colors = ['#28a745', '#dc3545', '#20c997', '#fd7e14']
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, sizes, color=colors)
    plt.title('Domain vs Subdomain Status Breakdown', fontsize=14, pad=20)
    plt.ylabel('Count')
    plt.xticks(rotation=45, ha='right')
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom')
    
    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='PNG', dpi=150)
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf-8')

def generate_domain_subdomain_charts(domains):
    charts = []
    for domain in domains:
        if not domain['subdomains']:
            continue
            
        live_subs = sum(1 for s in domain['subdomains'] if s['live'])
        dead_subs = len(domain['subdomains']) - live_subs
        
        if live_subs + dead_subs == 0:
            continue
            
        plt.figure(figsize=(6, 4))
        plt.pie([live_subs, dead_subs], 
                labels=['Live', 'Non-Live'], 
                colors=['#28a745', '#dc3545'],
                autopct='%1.1f%%' if (live_subs + dead_subs) > 1 else None,
                startangle=90)
        plt.title(f"Subdomain Status", fontsize=10, pad=10)
        
        img = io.BytesIO()
        plt.savefig(img, format='PNG', bbox_inches='tight', dpi=120)
        img.seek(0)
        plt.close()
        charts.append({
            'domain': domain['domain'],
            'chart': base64.b64encode(img.getvalue()).decode('utf-8')
        })
    
    return charts

def generate_pdf_report(domains):
    if not USE_WEASYPRINT:
        raise Exception("WeasyPrint not installed. Run: pip install weasyprint")
    
    overall_chart = generate_overall_status_chart(domains)
    breakdown_chart = generate_domain_breakdown_chart(domains)
    domain_charts = generate_domain_subdomain_charts(domains)
    
    total_domains = len(domains)
    total_subdomains = sum(len(d['subdomains']) for d in domains)
    live_domains = sum(1 for d in domains if d['live'])
    live_subdomains = sum(1 for d in domains for s in d['subdomains'] if s['live'])
    
    table_rows = ""
    for domain in domains:
        domain_status = "Live" if domain['live'] else "Non-Live"
        domain_class = "live" if domain['live'] else "dead"
        live_subs = sum(1 for s in domain['subdomains'] if s['live'])
        total_subs = len(domain['subdomains'])
        
        if total_subs == 0:
            subdomain_html = "<span class='text-muted'>None</span>"
        else:
            sub_names = [sub['name'] for sub in domain['subdomains']]
            formatted_subs = []
            for i in range(0, len(sub_names), 4):
                chunk = sub_names[i:i+4]
                formatted_subs.append(", ".join(chunk))
            subdomain_html = "<div class='subdomain-list'>" + "<br>".join(formatted_subs) + "</div>"
        
        table_rows += f"""
        <tr>
            <td class="domain-col">{domain['domain']}</td>
            <td class="status-col"><span class="{domain_class}">{domain_status}</span></td>
            <td class="subdomains-col">{subdomain_html}</td>
        </tr>
        """
    
    domain_charts_html = ""
    if domain_charts:
        for chart_data in domain_charts:
            domain_name = chart_data['domain']
            target_domain = next((d for d in domains if d['domain'] == domain_name), None)
            if target_domain:
                live_count = sum(1 for s in target_domain['subdomains'] if s['live'])
                total_count = len(target_domain['subdomains'])
                chart_title = f"{domain_name} ({live_count}/{total_count} Live)"
            else:
                chart_title = domain_name
                
            domain_charts_html += f"""
            <div class="domain-chart-item">
                <h4>{chart_title}</h4>
                <img src="data:image/png;base64,{chart_data['chart']}" alt="Subdomain Chart">
            </div>
            """
    else:
        domain_charts_html = '<p style="color: #6c757d; text-align: center;">No subdomains found to generate charts.</p>'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm 10mm 15mm 10mm;
            }}
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0;
                padding: 0;
                background: white;
                color: #333;
                line-height: 1.3;
                font-size: 9pt;
            }}
            .container {{
                width: 100%;
                max-width: none;
                margin: 0;
                padding: 0 5mm;
            }}
            .header {{ 
                background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%); 
                color: white; 
                padding: 20mm 0;
                text-align: center; 
                margin-bottom: 10mm;
                page-break-inside: avoid;
            }}
            .header h1 {{
                font-size: 18pt;
                margin: 0;
                padding: 0 10mm;
            }}
            .header p {{
                font-size: 12pt;
                margin-top: 5mm;
                padding: 0 10mm;
            }}
            .summary {{ 
                display: flex; 
                justify-content: space-between; 
                flex-wrap: wrap;
                gap: 8mm;
                margin: 8mm 0 12mm;
                page-break-inside: avoid;
            }}
            .stat-card {{ 
                background: white; 
                padding: 6mm;
                border: 1px solid #e9ecef;
                border-radius: 4mm; 
                text-align: center; 
                min-width: 40mm;
                flex: 1;
                box-sizing: border-box;
            }}
            .stat-number {{ 
                font-size: 16pt; 
                font-weight: bold; 
                color: #0d6efd; 
                margin-bottom: 2mm;
            }}
            .chart-container {{ 
                background: white;
                padding: 8mm;
                border: 1px solid #e9ecef;
                border-radius: 4mm;
                margin: 8mm 0;
                page-break-inside: avoid;
            }}
            .chart-container h2 {{
                text-align: center; 
                margin: 0 0 6mm 0;
                font-size: 12pt;
                color: #495057;
            }}
            .chart-container img {{ 
                max-width: 100%; 
                height: auto; 
                display: block;
                margin: 0 auto;
            }}
            table {{ 
                width: 100% !important; 
                border-collapse: collapse; 
                margin: 10mm 0; 
                background: white; 
                font-size: 8.5pt;
                table-layout: fixed;
            }}
            th, td {{ 
                padding: 4mm 3mm;
                text-align: left; 
                border: 1px solid #e9ecef;
                vertical-align: top;
                word-wrap: break-word;
                line-height: 1.2;
            }}
            th {{ 
                background: #f8f9fa; 
                font-weight: bold; 
                color: #495057;
                font-size: 9pt;
                text-align: center;
            }}
            .domain-col {{ width: 30%; }}
            .status-col {{ width: 20%; text-align: center; }}
            .subdomains-col {{ width: 50%; }}
            .live {{ 
                color: #28a745; 
                font-weight: bold; 
                white-space: nowrap;
            }}
            .dead {{ 
                color: #dc3545; 
                font-weight: bold; 
                white-space: nowrap;
            }}
            .subdomain-list {{
                font-size: 8pt;
                line-height: 1.3;
            }}
            .text-muted {{
                color: #6c757d;
                font-style: italic;
            }}
            .footer {{ 
                text-align: center; 
                margin-top: 10mm; 
                color: #6c757d; 
                font-size: 8pt;
                padding-top: 5mm;
                border-top: 1px solid #e9ecef;
            }}
            tr {{
                page-break-inside: avoid;
            }}
            .domain-charts-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 6mm;
                justify-content: center;
            }}
            .domain-chart-item {{
                flex: 1;
                min-width: 80mm;
                max-width: 120mm;
                background: white;
                padding: 6mm;
                border: 1px solid #e9ecef;
                border-radius: 4mm;
                text-align: center;
                page-break-inside: avoid;
            }}
            .domain-chart-item h4 {{
                margin: 0 0 4mm 0;
                font-size: 10pt;
                color: #495057;
            }}
            .domain-chart-item img {{
                max-width: 100%;
                height: auto;
                border-radius: 2mm;
            }}
            .section-heading {{
                margin: 12mm 0 6mm 0;
                font-size: 12pt;
                color: #495057;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .live-count-badge {{
                background: #e9ecef;
                padding: 2mm 4mm;
                border-radius: 3mm;
                font-size: 9pt;
                color: #495057;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Route53 Live Domain Report</h1>
                <p>Comprehensive Domain & Subdomain Analysis</p>
            </div>
            
            <div class="summary">
                <div class="stat-card">
                    <div class="stat-number">{total_domains}</div>
                    <div>Total Domains</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_subdomains}</div>
                    <div>Total Subdomains</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{live_domains}</div>
                    <div>Live Domains</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{live_subdomains}</div>
                    <div>Live Subdomains</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h2>Overall Status Distribution</h2>
                <img src="data:image/png;base64,{overall_chart}" alt="Overall Status Chart">
            </div>
            
            <div class="chart-container">
                <h2>Domain vs Subdomain Breakdown</h2>
                <img src="data:image/png;base64,{breakdown_chart}" alt="Breakdown Chart">
            </div>
            
            <div class="chart-container">
                <h2>Per-Domain Subdomain Analysis</h2>
                <div class="domain-charts-container">
                    {domain_charts_html}
                </div>
            </div>
            
            <div class="section-heading">
                <span>Detailed Domain Analysis</span>
                <span class="live-count-badge">{live_subdomains}/{total_subdomains} Live Subdomains</span>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Status</th>
                        <th>Subdomains</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            
            <div class="footer">
                <p>Report generated on {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>Ma href="https://github.com/mrumaraziz0/">Route53 Domain Scanner </a></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    pdf_path = "/tmp/route53_report.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_email_with_pdf(recipient_email, pdf_path):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USERNAME
        msg['To'] = recipient_email
        msg['Subject'] = "Route53 Live Domain Report - Advanced Analytics"
        
        body = """
        Hello,
        
        Attached is your comprehensive Route53 Live Domain Report featuring:
        
        • Overall status distribution chart
        • Domain vs Subdomain breakdown analysis
        • Individual per-domain subdomain charts
        • Detailed live/non-live status for all entries
        
        This report provides complete visibility into your DNS infrastructure health.
        
        Best regards,
        Route53 Domain Scanner
        """
        msg.attach(MIMEText(body, 'plain'))
        
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename=route53_security_report_advanced.pdf'
        )
        msg.attach(part)
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_USERNAME, recipient_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Route53 Live Domain Scanner</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #f8f9fa; padding-top: 2rem; }
            .card { box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,.075); margin-bottom: 1.5rem; }
            .live { color: #198754; font-weight: bold; }
            .dead { color: #dc3545; font-weight: bold; }
            #progressBar { transition: width 0.3s ease; height: 20px; }
            .hidden { display: none !important; }
            .speed-badge { background: linear-gradient(45deg, #0d6efd, #6f42c1); color: white; }
            .pdf-btn { background: linear-gradient(45deg, #d63384, #dc3545); border: none; }
            .email-btn { background: linear-gradient(45deg, #0dcaf0, #0d6efd); border: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1>Route53 Live Domain Scanner Scanner</h1>
                <span class="badge speed-badge">Advanced Analytics</span>
            </div>
            
            <div class="d-flex gap-2 mb-4 flex-wrap">
                <button id="startBtn" class="btn btn-primary">Start Scan</button>
                <button id="resetBtn" class="btn btn-outline-secondary">Reset</button>
                <button id="pdfBtn" class="btn pdf-btn" disabled>
                    <i class="fas fa-file-pdf"></i> Generate PDF
                </button>
                <button id="emailBtn" class="btn email-btn" disabled data-bs-toggle="modal" data-bs-target="#emailModal">
                    <i class="fas fa-envelope"></i> Email Report
                </button>
            </div>
            
            <div class="modal fade" id="emailModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Send Report via Email</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="emailInput" class="form-label">Recipient Email</label>
                                <input type="email" class="form-control" id="emailInput" placeholder="Enter email address">
                                <div id="emailError" class="text-danger mt-2" style="display:none;"></div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn email-btn" id="sendEmailBtn">Send Report</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="progressSection" class="hidden">
                <div class="card">
                    <div class="card-body">
                        <h5>Scanning in Parallel...</h5>
                        <div class="progress mt-3">
                            <div id="progressBar" class="progress-bar bg-success" role="progressbar" style="width: 0%"></div>
                        </div>
                        <p id="progressText" class="mt-2 mb-0">Initializing...</p>
                        <p class="text-muted small mt-2">Using 10 parallel threads for maximum speed</p>
                    </div>
                </div>
            </div>
            
            <div id="results"></div>
            <div id="error" class="alert alert-danger hidden"></div>
            <div id="completed" class="alert alert-success hidden">
                <h5>✅ Scan Completed!</h5>
                <p id="completionStats"></p>
            </div>
            <div id="emailSuccess" class="alert alert-success hidden">
                <h5>📧 Email Sent Successfully!</h5>
                <p>Report has been sent to <span id="sentEmail"></span></p>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://kit.fontawesome.com/a076d05399.js" crossorigin="anonymous"></script>
        <script>
        let scanInterval = null;
        let isScanning = false;
        
        async function startScan() {
            if (isScanning) return;
            
            document.getElementById('results').innerHTML = '';
            document.getElementById('error').classList.add('hidden');
            document.getElementById('completed').classList.add('hidden');
            document.getElementById('emailSuccess').classList.add('hidden');
            document.getElementById('progressSection').classList.remove('hidden');
            document.getElementById('startBtn').disabled = true;
            document.getElementById('pdfBtn').disabled = true;
            document.getElementById('emailBtn').disabled = true;
            isScanning = true;
            
            try {
                await fetch('/api/start-scan', { method: 'POST' });
                scanInterval = setInterval(fetchResults, 300);
            } catch (err) {
                showError('Failed to start scan: ' + err.message);
            }
        }
        
        async function fetchResults() {
            try {
                const response = await fetch('/api/scan-status');
                const data = await response.json();
                
                updateProgress(data);
                showNewDomains(data.domains);
                
                if (data.status === 'completed' || data.status === 'error') {
                    clearInterval(scanInterval);
                    isScanning = false;
                    document.getElementById('startBtn').disabled = false;
                    
                    if (data.status === 'error') {
                        showError(data.error);
                    } else {
                        showCompletion(data);
                        document.getElementById('pdfBtn').disabled = false;
                        document.getElementById('emailBtn').disabled = false;
                    }
                }
            } catch (err) {
                console.error('Fetch error:', err);
            }
        }
        
        function updateProgress(data) {
            const progress = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            
            if (data.total_zones > 0) {
                const percent = Math.min(100, Math.floor((data.processed_zones / data.total_zones) * 100));
                progress.style.width = percent + '%';
                progressText.textContent = `Completed ${data.processed_zones}/${data.total_zones} domains`;
            }
        }
        
        function showNewDomains(newDomains) {
            const resultsDiv = document.getElementById('results');
            const existingDomains = new Set();
            resultsDiv.querySelectorAll('.domain-card').forEach(card => {
                existingDomains.add(card.dataset.domain);
            });
            
            const sortedNew = [...newDomains].sort((a, b) => a.domain.localeCompare(b.domain));
            
            sortedNew.forEach(domain => {
                if (!existingDomains.has(domain.domain)) {
                    const card = createDomainCard(domain);
                    resultsDiv.appendChild(card);
                }
            });
        }
        
        function createDomainCard(domain) {
            const card = document.createElement('div');
            card.className = 'card domain-card';
            card.dataset.domain = domain.domain;
            
            const domainStatus = domain.live ? 
                '<span class="live">● Live</span>' : 
                '<span class="dead">● Non-Live</span>';
            
            let subsHtml = '<ul class="mb-0">';
            if (domain.subdomains.length === 0) {
                subsHtml += '<li class="text-muted">No subdomains</li>';
            } else {
                domain.subdomains.forEach(sub => {
                    const subStatus = sub.live ? 
                        '<span class="live">Live</span>' : 
                        '<span class="dead">Non-Live</span>';
                    subsHtml += `<li>${sub.name} [${subStatus}]</li>`;
                });
            }
            subsHtml += '</ul>';
            
            card.innerHTML = `
                <div class="card-body">
                    <h5 class="card-title">${domain.domain}</h5>
                    <p><strong>Status:</strong> ${domainStatus}</p>
                    <p><strong>Subdomains:</strong></p>
                    ${subsHtml}
                </div>
            `;
            return card;
        }
        
        function showCompletion(data) {
            document.getElementById('progressSection').classList.add('hidden');
            document.getElementById('completed').classList.remove('hidden');
            
            const totalSubs = data.domains.reduce((sum, d) => sum + d.subdomains.length, 0);
            document.getElementById('completionStats').textContent = 
                `Scanned ${data.domains.length} domains with ${totalSubs} subdomains in record time!`;
        }
        
        function showError(message) {
            document.getElementById('progressSection').classList.add('hidden');
            document.getElementById('error').textContent = 'Error: ' + message;
            document.getElementById('error').classList.remove('hidden');
            document.getElementById('startBtn').disabled = false;
        }
        
        function resetScan() {
            clearInterval(scanInterval);
            isScanning = false;
            document.getElementById('results').innerHTML = '';
            document.getElementById('error').classList.add('hidden');
            document.getElementById('completed').classList.add('hidden');
            document.getElementById('emailSuccess').classList.add('hidden');
            document.getElementById('progressSection').classList.add('hidden');
            document.getElementById('startBtn').disabled = false;
            document.getElementById('pdfBtn').disabled = true;
            document.getElementById('emailBtn').disabled = true;
        }
        
        document.getElementById('sendEmailBtn').addEventListener('click', async () => {
            const email = document.getElementById('emailInput').value;
            const errorDiv = document.getElementById('emailError');
            
            if (!email || !email.includes('@')) {
                errorDiv.textContent = 'Please enter a valid email address';
                errorDiv.style.display = 'block';
                return;
            }
            
            errorDiv.style.display = 'none';
            document.getElementById('sendEmailBtn').disabled = true;
            document.getElementById('sendEmailBtn').textContent = 'Sending...';
            
            try {
                const response = await fetch('/api/send-email', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email})
                });
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('sentEmail').textContent = email;
                    document.getElementById('emailSuccess').classList.remove('hidden');
                    document.getElementById('emailModal').querySelector('.btn-close').click();
                } else {
                    errorDiv.textContent = result.error || 'Failed to send email';
                    errorDiv.style.display = 'block';
                }
            } catch (err) {
                errorDiv.textContent = 'Network error: ' + err.message;
                errorDiv.style.display = 'block';
            } finally {
                document.getElementById('sendEmailBtn').disabled = false;
                document.getElementById('sendEmailBtn').textContent = 'Send Report';
            }
        });
        
        document.getElementById('startBtn').addEventListener('click', startScan);
        document.getElementById('resetBtn').addEventListener('click', resetScan);
        document.getElementById('pdfBtn').addEventListener('click', () => {
            window.open('/api/generate-pdf', '_blank');
        });
        </script>
    </body>
    </html>
    """)

@app.route('/api/start-scan', methods=['POST'])
def start_scan():
    if scan_state['status'] == 'scanning':
        return jsonify({"error": "Scan already in progress"}), 400
    
    thread = threading.Thread(target=background_scan)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "started"})

@app.route('/api/scan-status')
def scan_status():
    with scan_lock:
        state_copy = {
            'status': scan_state['status'],
            'error': scan_state['error'],
            'domains': scan_state['domains'].copy(),
            'total_zones': scan_state['total_zones'],
            'processed_zones': scan_state['processed_zones']
        }
    
    return jsonify(state_copy)

@app.route('/api/generate-pdf')
def generate_pdf():
    try:
        with scan_lock:
            domains = scan_state['domains'].copy()
        
        if not domains:
            return jsonify({"error": "No scan data available"}), 400
        
        pdf_path = generate_pdf_report(domains)
        return send_file(pdf_path, as_attachment=True, download_name='route53_report_advanced.pdf')
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500

@app.route('/api/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        recipient_email = data.get('email')
        
        if not recipient_email or '@' not in recipient_email:
            return jsonify({"error": "Invalid email address"}), 400
        
        with scan_lock:
            domains = scan_state['domains'].copy()
        
        if not domains:
            return jsonify({"error": "No scan data available"}), 400
        
        pdf_path = generate_pdf_report(domains)
        
        if send_email_with_pdf(recipient_email, pdf_path):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to send email. Check SMTP configuration."}), 500
            
    except Exception as e:
        return jsonify({"error": f"Email sending failed: {str(e)}"}), 500

if __name__ == '__main__':
    if not USE_WEASYPRINT:
        print("❌ FATAL: WeasyPrint is required for PDF generation!")
        print("   Install it with: pip install weasyprint")
        print("   Then install system dependencies:")
        print("   Ubuntu/Debian: sudo apt-get install build-essential python3-dev python3-pip libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info")
        exit(1)
    
    print("🚀 Route53 Scanner with Advanced Analytics")
    print("   • Multi-threaded scanning")
    print("   • 3 specialized charts in PDF")
    print("   • Per-domain subdomain analysis")
    print("   • Email delivery")
    print("\n📧 EMAIL CONFIGURATION REQUIRED:")
    print(f"   SMTP_SERVER: {SMTP_SERVER}")
    print(f"   EMAIL_USERNAME: {EMAIL_USERNAME}")
    print("   EMAIL_PASSWORD: your_app_password")
    print("\n   Visit: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
