#!/usr/bin/env python3
"""Install this checkout as a Codex skill and add an idempotent user cron job."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BEGIN = '# BEGIN keep-me-update (managed)'
END = '# END keep-me-update (managed)'


def cron_block(existing, config, config_path, log):
    hour, minute = map(int, config.get('delivery_time', '08:00').split(':'))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError('delivery_time must be HH:MM')
    zone = config.get('timezone', 'Asia/Shanghai')
    ZoneInfo(zone)
    if not re.fullmatch(r'[A-Za-z0-9_+./-]+', zone):
        raise ValueError('Invalid timezone')
    # Restore the previously effective timezone after our block.
    old_zones = re.findall(r'^CRON_TZ=(.*)$', existing, flags=re.M)
    local_zone = str(Path('/etc/localtime').resolve()).split('/zoneinfo/')[-1]
    restore = old_zones[-1] if old_zones else local_zone
    ZoneInfo(restore.strip('"\''))
    command = shlex.join([sys.executable, str(ROOT / 'scripts/daily_report.py'), '--config', str(config_path)])
    # Cron interprets percent before invoking the shell, even inside quotes.
    command = command.replace('%', r'\%')
    redirect = f' >> {shlex.quote(str(log)).replace(chr(37), chr(92)+chr(37))} 2>&1'
    return '\n'.join([BEGIN, f'CRON_TZ={zone}',
        f'{minute} {hour} * * * {command}{redirect}',
        f'@reboot sleep 60; {command} --catch-up{redirect}',
        f'CRON_TZ={restore}', END])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.expanduser().read_text())
    path = Path.home() / '.config/keep-me-update/config.json'
    output = Path(config['output_dir']).expanduser().resolve()
    config['output_dir'] = str(output)
    config.setdefault('codex_bin', shutil.which('codex') or str(Path.home() / '.local/bin/codex'))
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if result.returncode and 'no crontab' not in result.stderr.lower():
        raise RuntimeError(result.stderr.strip())
    previous = result.stdout
    cleaned = re.sub(r'(?m)^' + re.escape(BEGIN) + r'\n.*?^' + re.escape(END) + r'\n?', '', previous, flags=re.S)
    block = cron_block(cleaned, config, path, output / '.运行记录/cron.log')
    updated = cleaned.rstrip() + '\n\n' + block + '\n'
    print(updated)
    if args.dry_run:
        return
    skill = Path.home() / '.codex/skills/keep-me-update'
    if skill.exists() and skill.resolve() != ROOT:
        raise RuntimeError(f'Existing skill at {skill}; choose how to migrate it before replacing')
    output.mkdir(parents=True, exist_ok=True)
    (output / '.运行记录').mkdir(exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    os.chmod(path, 0o600)
    backup = path.parent / 'crontab.before-keep-me-update'
    if not backup.exists():
        backup.write_text(previous)
    skill.parent.mkdir(parents=True, exist_ok=True)
    if not skill.exists():
        skill.symlink_to(ROOT, target_is_directory=True)
    subprocess.run(['crontab', '-'], input=updated, text=True, check=True)
    print(f'Installed: {skill}\nConfig: {path}\nReports: {output}')


if __name__ == '__main__':
    main()
