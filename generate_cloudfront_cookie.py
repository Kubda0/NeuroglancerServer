import base64
import json
import time
import rsa
import re
import logging

# Configure logging
log_file = "/var/log/gen_set_cookie.log"
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Full Path to private key (.pem file)
private_key_path = "/etc/nginx/ngcloud.pem"

# CloudFront Key Pair ID
#REPLACE
key_pair_id = "K2BOYVN17TEKOL"  # REPLACE with your CloudFront Key Pair ID

# CloudFront distribution URL
#REPLACE
cloudfront_url = "https://cfdist.alunazee.net/*"  # REPLACE with your CloudFront URL

# Expiration time (1 week from now)
expires = int(time.time()) + 604800  # Expiry time in seconds

# Define CloudFront policy
policy = {"Statement": [{"Resource": cloudfront_url, "Condition": {"DateLessThan": {"AWS:EpochTime": expires}}}]}

try:
    # Load the private key
    with open(private_key_path, "r") as key_file:
        private_key = rsa.PrivateKey.load_pkcs1(key_file.read())

    logging.info("Private key loaded successfully.")
except Exception as e:
    logging.error(f"Error loading private key: {e}")
    exit(1)

# Convert the policy to JSON, then base64 encode it
policy_json = json.dumps(policy, separators=(",", ":"))
base64_policy = base64.b64encode(policy_json.encode('utf-8')).decode('utf-8')

# Sign the policy with the private key using RSA-SHA1
signed_policy = base64.b64encode(rsa.sign(policy_json.encode('utf-8'), private_key, 'SHA-1')).decode('utf-8')

# Prepare Nginx headers to set CloudFront cookies
header_directives = "\n".join([
    #REPLACE “Domain=” with “Domain=.your_domain.net”
    f'add_header Set-Cookie "{key}={value}; Path=/; Domain=.alunazee.net; Secure; HttpOnly" always;'
    for key, value in {
        'CloudFront-Policy': base64_policy,
        'CloudFront-Signature': signed_policy,
        'CloudFront-Key-Pair-Id': key_pair_id
    }.items()
])

# Path to the Nginx site configuration
nginx_config_path = "/etc/nginx/sites-available/neuroglancer"

try:
    # Read the existing config file
    with open(nginx_config_path, "r") as nginx_file:
        config_content = nginx_file.read()
    logging.info("Nginx config file read successfully.")
except Exception as e:
    logging.error(f"Error reading nginx config file: {e}")
    exit(1)

# Remove any previously injected CloudFront cookies
config_content = re.sub(r'add_header Set-Cookie "CloudFront-[^"]+" always;\n?', '', config_content)

# Inject new add_header directives after index.html
updated_config = re.sub(r'(index index\.html;)', r'\1\n' + header_directives, config_content, count=1)

try:
    # Write the updated config back to the file
    with open(nginx_config_path, "w") as nginx_file:
        nginx_file.write(updated_config.strip() + "\n")
    logging.info("Cookies written to nginx config file successfully")
except Exception as e:
    logging.error(f"Error writing to nginx config file: {e}")
    exit(1)
