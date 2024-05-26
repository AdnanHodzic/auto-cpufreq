from os import chdir
from requests import exceptions, get
from subprocess import check_output

from auto_cpufreq.globals import APP_VERSION, GITHUB
from auto_cpufreq.prints import print_block, print_error, print_info

def check_for_update() -> bool:
    try:
        if (res := get(GITHUB.replace('github.com', 'api.github.com/repos') + '/releases/latest')).status_code == 200:
            if (latest_version := res.json().get('tag_name')) is not None:
                if latest_version[1:] > APP_VERSION:
                    print_block(
                        'Updates are available',
                        f'Current version: v{APP_VERSION}',
                        'Latest version: '+latest_version,
                        'Note that your previous custom settings might be erased with the following update'
                    )
                    return True
                else: print('auto-cpufreq is up to date')
            else: print_error('Malformed Released data! Reinstall manually or open an issue on GitHub for help!')
        else:
            message = res.json().get('message')
            if message is not None and message.startswith('API rate limit exceeded'):
                print_error('GitHub Rate limit exceeded. Please try again later within 1 hour or use different network/VPN.')
            else: print_error('Unexpected status code:', res.status_code)
    except (exceptions.ConnectionError, exceptions.Timeout, exceptions.RequestException, exceptions.HTTPError):
        print_error('Connecting to server!')
        
    return False

def update() -> None:
    try:
        chdir('/tmp')
        print_info('Cloning the latest release')
        check_output(f'git clone {GITHUB}.git', shell=True)
        chdir('auto-cpufreq')
        check_output(['./auto-cpufreq-installer', '-i'], encoding='utf-8')
        check_output('rm -rf /tmp/auto-cpufreq', shell=True)
        check_output(['auto-cpufreq', '--install'])
        print('auto-cpufreq is installed with the latest version')
    except:
        print_error('Unable to update auto-cpufreq')
        exit(1)