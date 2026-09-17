import json
import os

config_path = os.path.expanduser('~/.railway/config.json')
with open(config_path, 'r') as f:
    cfg = json.load(f)

deploy_dir = r'd:\Desktop\antigravity\POLYBOT\polybot\batch_fok_deploy'
deploy_dir_norm = os.path.normpath(deploy_dir)

cfg['projects'][deploy_dir_norm] = {
    'environment': '8a457c42-0b85-401d-8aae-556195014077',
    'environmentName': 'production',
    'name': 'polybot-97-scalper',
    'project': '68c99960-82ce-4e00-a23b-0cb28bf4d227',
    'projectPath': deploy_dir_norm,
    'service': '525ef0fa-717d-43a2-a4ba-d5df02a8dee4'
}

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)

print('Successfully mapped batch_fok_deploy in ~/.railway/config.json')
