import json
import os
import subprocess

config_path = os.path.expanduser('~/.railway/config.json')
with open(config_path, 'r') as f:
    cfg = json.load(f)

deploy_dir = r'd:\Desktop\antigravity\POLYBOT\polybot\batch_fok_deploy'
deploy_dir_norm = os.path.normpath(deploy_dir)

# Map batch_fok_deploy to the active polybot-97-scalper service
cfg['projects'][deploy_dir_norm] = {
    'environment': '8a457c42-0b85-401d-8aae-556195014077',
    'environmentName': 'production',
    'name': 'polybot-97-scalper',
    'project': '68c99960-82ce-4e00-a23b-0cb28bf4d227',
    'projectPath': deploy_dir_norm,
    'service': '92085ee6-62ab-463d-a313-cab77706a35c'
}

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)

print('Updated Railway config mapping to service 92085ee6-62ab-463d-a313-cab77706a35c')

# Now trigger railway up --detach
res = subprocess.run(['railway', 'up', '--detach'], cwd=deploy_dir, capture_output=True, text=True, shell=True, encoding='utf-8', errors='ignore')
print('UP STDOUT:\n', res.stdout)
print('UP STDERR:\n', res.stderr)
print('UP RETURN CODE:', res.returncode)
